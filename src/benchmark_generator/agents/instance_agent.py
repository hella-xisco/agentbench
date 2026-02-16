from pathlib import Path
import json
from typing import Any
import shlex

from benchmark_generator import Agent
from benchmark_generator.pull_request import PullRequestInstance
from benchmark_generator.constants import INSTANCE_GENERATION_PROMPT_TEMPLATE
from agentbench.utils.diff_file import DiffFile

from agentbench.utils.io_utils import save_traj
from agentbench.utils.log import logger


def render_instance_task(
    pr: PullRequestInstance,
    env,
    metadata_relpath: str,
) -> str:

    pr_patch,_, _ = pr.split_patch()

    # Cut the patch if too long
    # Add it to a file in the environment
    env.execute(f'echo {shlex.quote(pr_patch)} > pr_patch.diff', timeout=False)

    lines = pr_patch.strip().splitlines()
    if len(lines) > 400:

        lines = lines[:400]
        lines.append("... [diff truncated]")
        lines.append("")
        lines.append("# Note: The full patch is available in the file 'pr_patch.diff' in the working directory.")
        pr_patch = "\n".join(lines)
    else:
        f"The diff file is available in 'pr_patch.diff' in the working directory. We also provide the diff below for reference.\n\n{pr_patch}"

    return INSTANCE_GENERATION_PROMPT_TEMPLATE.format(
        pr_number=pr.number,
        repo=pr.base_repo,
        commit_sha=pr.base_sha,
        problem_description=pr.problem_description,
        pr_patch=pr_patch,
        pr_test_patch=pr.pr_test_patch,
        metadata_relpath=metadata_relpath,
    )


class InstanceAgent(Agent):
    """Agent that generates the test instances."""

    def __init__(self, model: Any, env: Any, generator: Any) -> None:
        self.model = model
        self.env = env
        self.generator = generator

    def process_pr(self, pr: PullRequestInstance, output_path: Path) -> PullRequestInstance:
        """Generate the test instances for the PR."""
        metadata_relpath = "generated_test_metadata.json"


        task = render_instance_task(pr, env=self.env, metadata_relpath=metadata_relpath)

        # Setup the environment to the base state of the PR
        logger.info(f"Setting up environment for PR #{pr.number}...")
        pr.setup_env(self.env)

        logger.info(f"Generating instance for PR #{pr.number}...")
        exit_status, result = self.generator.run(task)

        save_traj(
            generator=self.generator,
            path=output_path / "instanceAgent_traces" / f"{pr.number}.traj.json",
            exit_status=exit_status,
            result=result,
            instance_id=pr.number,
        )
        # Get the command from the diff
        metadata = DiffFile.from_text(result, clean_diff=False)
        metadata = metadata.extract_created_file_content(filename=metadata_relpath)
        metadata = json.loads(metadata)

        # Get the test files created
        test_file_names = metadata.get("test_files", [])
        test_files_contents = [metadata.extract_created_file_content(filename=fname) for fname in test_file_names]

        # Get the test file runner
        test_file_runner = metadata.extract_created_file_content(filename="run_pr_tests.py")

        # Get the test commands
        test_commands = metadata.get("test_commands", [])

        # Update the PR instance
        clean_pr_patch, _, _ = pr.split_patch()
        pr.clean_pr_patch = clean_pr_patch
        pr.test_file_names = test_file_names
        pr.test_file_contents = test_files_contents
        pr.test_file_runner = test_file_runner
        pr.test_commands = test_commands

        return pr
