import concurrent.futures
from pathlib import Path
from typing import Any, Dict
import shlex
import re
from dataclasses import dataclass, field
import logging
from datasets import load_dataset
import random
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
import json
import traceback
import textwrap
import os

from configs import CLEANUP_COMMANDS

from agentbench import Environment, Instance, Benchmark
from agentbench.environments import get_environment
from agentbench.utils.diff_file import DiffFile

logger = logging.getLogger("agentbench.agentbench")

HEADER_RE = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.MULTILINE)

DEBUG = os.environ.get("AGENTBENCH_DEBUG", "0") == "1"

@dataclass
class AgentbenchInstance(Instance):

    instance_id: str
    repo: str
    task: str
    patch: str  # The solution of the instance
    docker_image: str
    commit: str # The commit to checkout for the instance

    # Repo test information
    setup_commands: list[str] # The commands to setup the repo
    repo_test_commands: list[str] # The commands to run the repo tests
    repo_test_runner: str # The repo test runner script

    # Instance test information
    test_file_names: list[str] # The test files corresponding to the instance
    test_file_contents: list[str] # The contents of the test files
    test_file_runner: str # The test file runner script
    test_commands: list[str] # The commands to run the tests
    
    # Repo test after patch 
    repo_test_after_pr_patch: dict[str, str] = field(default_factory=dict) # We compare the model generated patch repo test against this

    def get_dir(self, base_dir: Path) -> Path:
        instance_id = self.instance_id
        instance_dir = base_dir / instance_id
        instance_dir.mkdir(parents=True, exist_ok=True)
        return instance_dir
    
    def remove_agents_md_files(self, env: Environment) -> None:
        env.execute(
            r'find . -type f \( -name "AGENTS.md" -o -name "CLAUDE.md" \) -print -delete',
            timeout=False,
        )
        env.execute("rm -rf .github", timeout=False) # Copilot agents.md files

    def remove_docs(self, env: Environment) -> None:
        """Remove documentation files and folders from the repo, but keep AGENTS.md/CLAUDE.md."""

        logger.info(f"Removing documentation files for instance {self.instance_id}")

        # First we back up AGENTS.md and CLAUDE.md if they exist
        agent_md = env.read_file("AGENTS.md") 
        claude_md = env.read_file("CLAUDE.md")

        # Now we execute the cleanup commands
        repo = self.repo.replace("/", "_").lower()
        cleanup_commands = CLEANUP_COMMANDS.get(repo, [])
        for cmd in cleanup_commands:
            env.execute(cmd, timeout=False)

        # Finally we restore AGENTS.md and CLAUDE.md
        if agent_md:
            env.write_file("AGENTS.md", agent_md)
        if claude_md:
            env.write_file("CLAUDE.md", claude_md)

    def setup(self, env_config: dict[str, Any], setup_repo: bool = True) -> Environment:
        env_config["image"] = self.docker_image
        env_config["cwd"] = "/testbed" # Otherwise some PATH issues may occur
        env_config["timeout"] = 1800  # 30 minutes timeout

        env = get_environment(env_config, default_type="docker")

        # Setting the repo at the right commit and deleting future history
        checkout_command = f"git checkout {self.commit}"
        env.execute(checkout_command)
        env.execute("git reset --hard")

        # Setup the repo
        if setup_repo:
            for cmd in self.setup_commands:
                env.execute(cmd)
        else:
            logger.info(f"Skipping repo setup for instance {self.instance_id}")
            
        return env

    def _clean_git_history(self, env: Environment) -> None:
        # Remove remotes and any commits after the current checkout time.
        remotes_output = env.execute("git remote").get("output", "")
        remotes = [line.strip() for line in remotes_output.splitlines() if line.strip()]
        for remote in remotes:
            env.execute(f"git remote remove {shlex.quote(remote)}", timeout=False)

        head_ts_output = env.execute("git show -s --format=%ct HEAD").get("output", "").strip()
        try:
            cutoff_ts = int(head_ts_output)
        except ValueError:
            return

        branch_refs_output = env.execute(
            "git for-each-ref --format='%(refname)' refs/heads"
        ).get("output", "")
        branch_refs = [line.strip() for line in branch_refs_output.splitlines() if line.strip()]
        for ref in branch_refs:
            commit_output = env.execute(
                f"git rev-list -n 1 --before=@{cutoff_ts} {shlex.quote(ref)}"
            ).get("output", "")
            commit = commit_output.strip()
            if commit:
                env.execute(f"git update-ref {shlex.quote(ref)} {commit}", timeout=False)
            else:
                env.execute(f"git update-ref -d {shlex.quote(ref)}", timeout=False)

        tag_refs_output = env.execute(
            "git for-each-ref --format='%(refname)' refs/tags"
        ).get("output", "")
        tag_refs = [line.strip() for line in tag_refs_output.splitlines() if line.strip()]
        for ref in tag_refs:
            target_output = env.execute(
                f"git rev-parse {shlex.quote(ref)}^{{}}"
            ).get("output", "")
            target = target_output.strip()
            if not target:
                continue
            tag_ts_output = env.execute(
                f"git show -s --format=%ct {shlex.quote(target)}"
            ).get("output", "")
            tag_ts_str = tag_ts_output.strip()
            try:
                tag_ts = int(tag_ts_str)
            except ValueError:
                continue
            if tag_ts > cutoff_ts:
                env.execute(f"git update-ref -d {shlex.quote(ref)}", timeout=False)

        env.execute("git reflog expire --expire=now --all", timeout=False)
        env.execute("git gc --prune=now --quiet", timeout=False)

    def _setup_repo_test(self, env: Environment) -> None:
        # Write the repo test runner script
        env.execute("rm -f run_tests.py", timeout=False)
        env.write_file("run_tests.py", self.repo_test_runner)

    def _run_repo_test(self, env: Environment) -> dict[str, bool]:
        # Delete previous test results if any
        env.execute("rm -f test_results.json", timeout=False)

        # Execute the repo test command
        outputs = []
        for cmd in self.repo_test_commands:
            outputs.append((cmd, env.execute(cmd, timeout=False)))

        # Fetch the test_results.json file created by the test runner in the environment
        test_results = env.read_file("test_results.json")
        return self._parse_test_results(test_results, "test_results.json", outputs)

    @staticmethod
    def _parse_test_results(raw: str, filename: str, outputs: list) -> dict:
        """Parse a test runner's JSON output, or fail with the runner's own output.

        The test commands' stdout/stderr used to be discarded, so a runner that
        crashed left only `JSONDecodeError: Expecting value: line 1 column 1` --
        which says that the file is empty, but nothing about why. The tail of the
        actual command output is what identifies the cause (missing dependency,
        collection error, OOM kill under the container memory cap, ...).
        """
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            detail = "\n".join(
                f"$ {cmd}\n{str((res or {}).get('output', ''))[-2000:]}"
                for cmd, res in outputs
            )
            raise RuntimeError(
                f"Test runner produced no usable {filename} "
                f"({type(exc).__name__}: {exc}). Command output was:\n{detail}"
            ) from exc

    def _setup_instance_test(self, env: Environment) -> None:
        # Write the test files
        for fname, content in zip(self.test_file_names, self.test_file_contents):
            env.execute(f"rm -f {fname}", timeout=False)
            env.write_file(fname, content)

        # Write the test file runner script
        env.execute("rm -f run_pr_tests.py", timeout=False)
        env.execute(f"echo {shlex.quote(self.test_file_runner)} > run_pr_tests.py")

    def _run_instance_test(self, env: Environment) -> tuple[bool, dict[str, Any]]:
        # Delete previous test results if any
        env.execute("rm -f pr_test_results.json", timeout=False)

        # Execute the instance test commands
        outputs = []
        for cmd in self.test_commands:
            outputs.append((cmd, env.execute(cmd, timeout=False)))

        # Fetch the test_results.json file created by the test runner in the environment
        test_results = env.read_file("pr_test_results.json")
        return self._parse_test_results(test_results, "pr_test_results.json", outputs)

    def _parse_task(self) -> Dict[str, str]:

        matches = list(HEADER_RE.finditer(self.task))
        sections: Dict[str, str] = {}

        for i, m in enumerate(matches):
            title = m.group("title")
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(self.task)
            body = self.task[start:end].strip()

            sections[title] = body

        return sections

    def harden_task(self) -> None:
        """Harden the task description."""

        logger.info(f"Hardening task for instance {self.instance_id}")
        
        new_task = textwrap.dedent(
        """### Description
        
        {description}

        ### Specification (if applicable)

        {specification}

        ### Additional Information

        In this docker environment, if you need specific linux packages, you can install them using apt-get.
        First run `apt-get update` to update the package lists, then use `apt-get install -y <package_name>` to install the required packages.

        {additional_information}
        """).strip().format(
            description=self._parse_task().get("Description", ""),
            specification=self._parse_task().get("Specification (if applicable)'", ""),
            additional_information=self._parse_task().get("Additional Information", ""),
        )
        self.task = new_task
        


    def _run_repo_test_only(self, env: Environment) -> dict[str, Any]:
        self._setup_repo_test(env)
        repo_test_results = self._run_repo_test(env)
        return repo_test_results

    def solve(self, patch_diff: str, base_dir: Path, run_id: int, run_repo_test: bool = True) -> bool:


        model_patch = DiffFile.from_text(patch_diff).get_cleaned_diff()

        logger.info(f"Solving instance {self.instance_id} in repo {self.repo} at commit {self.commit}")

        evaluation_error: str | None = None

        try:
            env = self.setup({})

            # We add the proposed solution patch
            # First we remove the modifications to test files from the patch 
            apply_patch_cmd = f"echo {shlex.quote(model_patch)} | git apply --whitespace=nowarn -"
            env.execute(apply_patch_cmd)

            if run_repo_test:
                self._setup_repo_test(env)
                repo_test_after = self._run_repo_test(env)

                # Truncate keys to match those in repo_test_after_pr_patch
                repo_test_after = {k[-50:]: v for k, v in repo_test_after.items()}

                repo_test_pass = True
                # Results should be the same as repo_test_after_pr_patch (or better)
                repo_test_after_pr_patch = self.repo_test_after_pr_patch or {}
                for test_name, result_before in repo_test_after_pr_patch.items():
                    result_after = repo_test_after.get(test_name[-50:], True)
                    if result_before and not result_after:
                        logger.warning(
                            "Rejecting instance %s: repo test %s broke because of the patch.",
                            self.instance_id,
                            test_name,
                        )
                        repo_test_pass = False
                        break
            else:
                repo_test_pass = True
                repo_test_after_pr_patch = {}
                repo_test_after = {}

            # We add the proposed test patch
            self._setup_instance_test(env)
            instance_test_results = self._run_instance_test(env)
            base_passed = all(instance_test_results.get(test, False) for test in instance_test_results)

        except Exception as e:
            logger.error(f"Error during solving instance {self.instance_id}: {e}")
            logger.error(traceback.format_exc())
            base_passed = False
            repo_test_pass = False
            repo_test_after = {}
            repo_test_after_pr_patch = {}
            # Ein Evaluationsfehler ist keine nicht geloeste Aufgabe. Ohne diese
            # Unterscheidung schreibt jeder Container-, Timeout- oder Testrunner-Fehler
            # ein resolved=False in den Report und senkt still die Resolve-Rate,
            # anstatt als Fehler aufzufallen. Der Grund wird deshalb mitgeschrieben und
            # muss bei der Auswertung von den echten Misserfolgen getrennt werden.
            evaluation_error = f"{type(e).__name__}: {e}"

        # Save the results
        output_file = base_dir / f"{self.instance_id}" / "report.json"

        res = {}
        resolved = base_passed and repo_test_pass
        res[self.instance_id] = {
            "resolved": resolved,
            "instance_test_passed": base_passed,
            "repo_test_passed": repo_test_pass,
            "evaluation_error": evaluation_error,
            "model_patch": model_patch,
            "repo_test_after_pr_patch": repo_test_after_pr_patch,
            "repo_test_after": repo_test_after,
        }
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:

            json.dump(res, f, indent=2)

        return resolved
    

@dataclass
class AgentbenchConfig:
    dataset_name: str = "eth-sri/agentbench"
    filter_spec: str = ""
    slice_spec: str = ""
    split: str = "test"
    shuffle: bool = False

class AgentbenchBenchmark(Benchmark):
    """Benchmark for Agentbench instances."""

    def __init__(self, **kwargs: Any) -> None:
        self.config = AgentbenchConfig(**kwargs)

        self.instances = self.get_instances()
        self.instance_map = {inst.instance_id: inst for inst in self.instances}

    def get_single_instance(self, instance_id: str) -> AgentbenchInstance:
        return self.instance_map[instance_id]
    
    def get_instances(self) -> list[AgentbenchInstance]:
        instances = list(load_dataset(self.config.dataset_name, split=self.config.split))
        instances = filter_instances(
            instances, filter_spec=self.config.filter_spec, slice_spec=self.config.slice_spec, shuffle=self.config.shuffle
        )
        return [self._get_instance_from_row(row) for row in instances]

    def _get_instance_from_row(self, row: dict[str, Any]) -> AgentbenchInstance:

        repo_test_after_pr_patch = row.get("repo_test_after_pr_patch", {})
        if isinstance(repo_test_after_pr_patch, str):
            repo_test_after_pr_patch = json.loads(repo_test_after_pr_patch)


        instance = AgentbenchInstance(
            instance_id=row["instance_id"],
            repo=row["base_repo"],
            task=row["problem_description"],
            patch=row["clean_pr_patch"],
            docker_image=row["docker_image"],
            commit=row["base_sha"],
            setup_commands=row["setup_commands"],
            repo_test_commands=row["repo_test_commands"],
            repo_test_runner=row["repo_test_runner"],
            test_file_names=row["test_file_names"],
            test_file_contents=row["test_file_contents"],
            test_file_runner=row["test_file_runner"],
            test_commands=row["test_commands"],
            repo_test_after_pr_patch=repo_test_after_pr_patch,
        )
        return instance
    
    def solve(self, patch_diffs: dict[str,str], base_dir: Path, run_id: int, workers: int = 8) -> dict[str, bool]:

        preds = {}
        for instance_id, patch_dict in patch_diffs.items():
            preds[instance_id] = {"model_patch": patch_dict["model_patch"], "instance_id": instance_id, "model_name_or_path": "model"}
        
        # Get the instance ids from the instance attributes intersected with the prediction keys
        instance_ids = list(self.instance_map.keys())
        instance_ids = [id for id in instance_ids if id in preds]
        logger.info(f"Evaluating {len(instance_ids)} instances with SWE-bench")
        pending_instance_ids = []
        skipped_instance_ids = []
        for instance_id in instance_ids:
            report_file = base_dir / instance_id / "report.json"
            if report_file.exists():
                skipped_instance_ids.append(instance_id)
                continue
            pending_instance_ids.append(instance_id)
        if skipped_instance_ids:
            logger.info(
                "Skipping %d instances with existing report.json",
                len(skipped_instance_ids),
            )

        def process_futures(future_to_id: dict[concurrent.futures.Future, str]) -> None:
            total = len(future_to_id)
            if total == 0:
                return
            success_count = 0
            failure_count = 0
            with logging_redirect_tqdm():
                with tqdm(
                    total=total,
                    desc="Solving",
                    unit="instance",
                    leave=True,
                    dynamic_ncols=True,
                ) as pbar:
                    pbar.set_postfix_str("Pass 0 / Fail 0", refresh=True)
                    for future in concurrent.futures.as_completed(future_to_id):
                        resolved = False
                        try:
                            run_succeeded = future.result()
                            resolved = bool(run_succeeded)
                            
                        except concurrent.futures.CancelledError:
                            logger.warning(
                                "Generation worker for PR %s was cancelled.",
                                future_to_id[future],
                            )
                        except Exception as exc:
                            logger.error(
                                "Unhandled exception in generation worker for PR %s: %s",
                                future_to_id[future],
                                exc,
                                exc_info=True,
                            )
                        finally:
                            if resolved:
                                success_count += 1
                            else:
                                failure_count += 1
                            pbar.update(1)
                            pbar.set_postfix_str(
                                f"Pass {success_count} / Fail {failure_count}", refresh=True
                            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_id = {
                executor.submit(
                    self.instance_map[instance_id].solve,
                    patch_diffs[instance_id]["model_patch"],
                    base_dir,
                    run_id,
                ): instance_id
                for instance_id in pending_instance_ids
            }
            process_futures(future_to_id)

        # Final results
        results = {}
        for instance_id in instance_ids:
            report_file = base_dir / instance_id / "report.json"
            try:
                with open(report_file, "r") as f:
                    report_data = json.load(f)
                    results[instance_id] = report_data[instance_id]["resolved"]
            except Exception as e:
                logger.error(f"Error reading report for instance {instance_id}: {e}")
                results[instance_id] = False

        return results


def filter_instances(
    instances: list[dict],
    *,
    filter_spec: str,
    slice_spec: str = "",
    shuffle: bool = False,
) -> list[dict]:
    """Filter and slice a list of SWEBench instances."""
    if shuffle:
        instances = sorted(instances.copy(), key=lambda x: x["instance_id"])
        random.seed(42)
        random.shuffle(instances)
    before_filter = len(instances)
    instances = [
        instance
        for instance in instances
        if re.match(filter_spec, instance["instance_id"])
    ]
    if (after_filter := len(instances)) != before_filter:
        logger.info(f"Instance filter: {before_filter} -> {after_filter} instances")
    if slice_spec:
        values = [int(x) if x else None for x in slice_spec.split(":")]
        instances = instances[slice(*values)]
        if (after_slice := len(instances)) != before_filter:
            logger.info(f"Instance slice: {before_filter} -> {after_slice} instances")
    return instances
