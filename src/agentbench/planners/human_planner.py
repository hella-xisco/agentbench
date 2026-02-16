from dataclasses import dataclass
import shlex
from pathlib import Path
import threading
import json

from agentbench import Planner, Environment, Model, Instance

_PLAN_FILE_LOCK = threading.Lock()


@dataclass
class HumanPlannerConfig:
    storage_dir: str = "plans"
    plan_model: str = "dummy" # Not used
    generator_config: dict[str, str] = None 
    model_config: dict[str, str] = None

class HumanPlanner(Planner):
    """A planner that does nothing."""

    def __init__(self, **kwargs) -> None:
        self.config = HumanPlannerConfig(**kwargs)

    def plan(self, env: Environment, model: Model, instance: Instance) -> None:
        
        plan = self._fetch_plan_or_load(env, instance.repo, instance.instance_id)
        
        if hasattr(instance, "remove_agents_md_files"):
            instance.remove_agents_md_files(env)

        env.execute(f'echo {shlex.quote(plan)} > AGENTS.md', timeout=False)
        env.execute(f'echo {shlex.quote(plan)} > CLAUDE.md', timeout=False)

    def update_plan(self, **kwargs) -> None:
        pass

    def _fetch_plan_or_load(
        self, env: Environment, repo: str, instance_id: str
    ) -> str:
        
         # Try to load the AGENTS.md file if it exists
        agent_md = self._load_agent_md(instance_id)
        if agent_md is not None:
            return agent_md

        plan = self._fetch_plan(env, repo)

        self._store_agent_md(instance_id, plan)

        return plan

    def _fetch_plan(self, env: Environment, repo: str) -> str:


        # Fetch to make sure we have the latest refs
        self._git(env, "fetch --all --prune")

        current_commit = self._git(env, "rev-parse HEAD").strip()
        future_ref = self._find_future_ref(env, current_commit)

        for plan_file in ("AGENTS.md", "CLAUDE.md"):
            content = self._find_plan_file(env, current_commit, future_ref, plan_file)
            if content is not None:
                return content

        fallback_content = self._find_plan_in_main_history(env)
        if fallback_content is not None:
            return fallback_content

        if not future_ref:
            raise FileNotFoundError(
                f"Could not locate a future ref containing {current_commit} for {repo}"
            )

        raise FileNotFoundError(
            f"AGENTS.md or CLAUDE.md not found in {repo} after {current_commit}"
        )

    def _git(self, env: Environment, args: str) -> str:
        result = env.execute(f"git {args}")
        if result.get("returncode", 1) != 0:
            output = result.get("output", "").strip()
            raise RuntimeError(f"git {args} failed: {output}")
        return result.get("output", "")

    def _git_optional(self, env: Environment, args: str) -> str:
        result = env.execute(f"git {args}")
        if result.get("returncode", 1) != 0:
            return ""
        return result.get("output", "")

    def _find_future_ref(self, env: Environment, current_commit: str) -> str | None:
        candidates = []
        current_branch_ref = self._git_optional(env, "symbolic-ref --quiet HEAD").strip()
        branch_name = ""
        if current_branch_ref:
            if current_branch_ref.startswith("refs/heads/"):
                branch_name = current_branch_ref[len("refs/heads/") :]
        upstream = self._git_optional(
            env, "rev-parse --abbrev-ref --symbolic-full-name @{u}"
        ).strip()
        if branch_name:
            if upstream and upstream.endswith(f"/{branch_name}"):
                candidates.append(upstream)
            candidates.append(f"refs/remotes/origin/{branch_name}")
            candidates.append(f"origin/{branch_name}")
            candidates.append(current_branch_ref)
            candidates.append(branch_name)
        elif current_branch_ref:
            candidates.append(current_branch_ref)
        if upstream and upstream not in candidates:
            candidates.append(upstream)

        origin_head = self._git_optional(
            env, "symbolic-ref --quiet refs/remotes/origin/HEAD"
        ).strip()
        if origin_head:
            candidates.append(origin_head)
        candidates.extend(
            [
                "refs/remotes/origin/main",
                "refs/remotes/origin/master",
                "refs/remotes/origin/devel",
                "refs/heads/main",
                "refs/heads/master",
                "origin/main",
                "origin/master",
                "main",
                "master",
                "devel",
            ]
        )
        seen = set()
        for ref in candidates:
            if not ref or ref in seen:
                continue
            seen.add(ref)
            if self._is_ancestor(env, current_commit, ref):
                return ref

        refs_output = self._git_optional(
            env,
            f"for-each-ref --contains {shlex.quote(current_commit)} "
            "--format='%(refname)' refs/heads refs/remotes",
        )
        refs = [line.strip() for line in refs_output.splitlines() if line.strip()]
        if refs:
            preferred = [r for r in refs if r.startswith("refs/remotes/origin/")]
            preferred.extend(r for r in refs if not r.startswith("refs/remotes/origin/"))
            return preferred[0]
        return None

    def _is_ancestor(self, env: Environment, ancestor: str, ref: str) -> bool:
        result = env.execute(
            f"git merge-base --is-ancestor {shlex.quote(ancestor)} {shlex.quote(ref)}"
        )
        return result.get("returncode", 1) == 0

    def _find_plan_file(
        self,
        env: Environment,
        current_commit: str,
        future_ref: str | None,
        plan_file: str,
    ) -> str | None:
        if future_ref:
            commits = self._git(
                env,
                "log --reverse --first-parent --format=%H --diff-filter=A "
                f"{shlex.quote(current_commit)}..{shlex.quote(future_ref)} -- {shlex.quote(plan_file)}",
            )
            for commit in [line.strip() for line in commits.splitlines() if line.strip()]:
                content = self._show_file(env, commit, plan_file)
                if content is not None:
                    return content

        content = self._show_file(env, current_commit, plan_file)
        if content is not None:
            return content
        return None

    def _find_plan_in_main_history(self, env: Environment) -> str | None:
        branch_refs = self._main_branch_candidates(env)
        for plan_file in ("AGENTS.md", "CLAUDE.md"):
            content = self._find_plan_in_branch_history(env, plan_file, branch_refs)
            if content is not None:
                return content
        return None

    def _main_branch_candidates(self, env: Environment) -> list[str]:
        candidates = []
        origin_head = self._git_optional(
            env, "symbolic-ref --quiet refs/remotes/origin/HEAD"
        ).strip()
        if origin_head:
            candidates.append(origin_head)
        candidates.extend(
            [
                "refs/remotes/origin/main",
                "refs/remotes/origin/dev",
                "refs/heads/main",
                "refs/heads/dev",
                "origin/main",
                "origin/dev",
                "main",
                "dev",
                "refs/remotes/origin/master",
                "refs/heads/master",
                "origin/master",
                "master",
            ]
        )
        seen = set()
        ordered = []
        for ref in candidates:
            if not ref or ref in seen:
                continue
            seen.add(ref)
            ordered.append(ref)
        return ordered

    def _find_plan_in_branch_history(
        self,
        env: Environment,
        plan_file: str,
        branch_refs: list[str],
    ) -> str | None:
        for ref in branch_refs:
            if not self._git_optional(
                env, f"rev-parse --verify {shlex.quote(ref)}"
            ).strip():
                continue
            commits = self._git_optional(
                env,
                "log --first-parent --format=%H "
                f"{shlex.quote(ref)} -- {shlex.quote(plan_file)}",
            )
            for commit in [line.strip() for line in commits.splitlines() if line.strip()]:
                content = self._show_file(env, commit, plan_file)
                if content is not None:
                    return content
        return None

    def _show_file(self, env: Environment, commit: str, filename: str) -> str | None:
        result = env.execute(f"git show {shlex.quote(commit)}:{shlex.quote(filename)}")
        if result.get("returncode", 1) != 0:
            return None
        return result.get("output", "")

    def _store_agent_md(self, instance_id: str, agent_md: str) -> None:

        with _PLAN_FILE_LOCK:
            
            storage_dir = self._get_storage_path()
            extracted_plans = storage_dir / "extracted_plans.json"

            if extracted_plans.exists():
                with open(extracted_plans, "r") as f:
                    plans = json.load(f)
            else:
                plans = {}

            plans[instance_id] = agent_md

            with open(extracted_plans, "w") as f:
                json.dump(plans, f, indent=2)

    def _load_agent_md(self, instance_id: str) -> str | None:
        
        storage_dir = self._get_storage_path()
        extracted_plans = storage_dir / "extracted_plans.json"

        if not extracted_plans.exists():
            return None

        with open(extracted_plans, "r") as f:
            plans = json.load(f)

        return plans.get(instance_id, None)

    def _get_storage_path(self) -> Path:
        
        storage_dir = Path(self.config.storage_dir)
        storage_dir = storage_dir / "human_plans" 
        storage_dir.mkdir(parents=True, exist_ok=True)

        return storage_dir