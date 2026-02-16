from pathlib import Path

from benchmark_generator import Agent
from benchmark_generator.pull_request import PullRequestInstance
from benchmark_generator.constants import STATEMENT_GENERATION_PROMPT_TEMPLATE

from agentbench.utils.io_utils import save_traj
from agentbench.utils.log import logger

def render_statement_task(
    pr: PullRequestInstance,
    metadata_relpath: str = "ISSUE_DESCRIPTION.md",
) -> str:
    
    issues_title = [issue["title"] for issue in pr.referenced_issues]
    issues_body = [issue["body"] for issue in pr.referenced_issues]

    referenced_issues_text = ""
    for title, body in zip(issues_title, issues_body):
        referenced_issues_text += f"- Title: {title}\n  Description: {body}\n"
    
    key_files_text = "\n".join(f"- {file}" for file in pr.key_files) if pr.key_files else "None"

    pr_patch,_, _ = pr.split_patch()

    # Cut the patch if too long
    lines = pr_patch.strip().splitlines()
    if len(lines) > 400:
        lines = lines[:400]
        lines.append("... [diff truncated]")
        pr_patch = "\n".join(lines)

    return STATEMENT_GENERATION_PROMPT_TEMPLATE.format(
        pr_number=pr.number,
        repo=pr.base_repo,
        commit_sha=pr.base_sha,
        pr_description=pr.body or "No description provided.",
        referenced_issues_text=referenced_issues_text,
        pr_patch=pr_patch,
        pr_test_patch=pr.pr_test_patch,
        key_files_text=key_files_text,
        metadata_relpath=metadata_relpath,
    )


def extract_created_file_content(diff: str, file_name: str) -> str:
    lines = diff.splitlines()
    content_lines = []
    in_target = False
    found = False

    for line in lines:
        if line.startswith("+++ "):
            path = line[4:].strip()

            if path.startswith("a/") or path.startswith("b/"):
                path = path[2:]

            if path == file_name or path.endswith("/" + file_name):
                in_target = True
                found = True
                content_lines = []
                continue
            else:
                if in_target:
                    break
                in_target = False
                continue

        if not in_target:
            continue

        if line.startswith("diff --git "):
            break

        if line.startswith("@@") or line.startswith("--- "):
            continue

        if line.startswith("+") and not line.startswith("+++ "):
            content_lines.append(line[1:])
        elif line.startswith(" "):
            content_lines.append(line[1:])

    if not found:
        raise ValueError(f"File {file_name!r} not found as a created file in diff.")

    return "\n".join(content_lines)

class StatementAgent(Agent):
    """Agent that enhances problem description."""

    def __init__(self, model, env, generator) -> None:
        self.model = model
        self.env = env
        self.generator = generator

    def process_pr(self, pr: PullRequestInstance, output_path: Path) -> PullRequestInstance:
        """Enhance the problem description of the PR."""

        metadata_relpath = "ISSUE_DESCRIPTION.md"


        task = render_statement_task(pr, metadata_relpath=metadata_relpath)

        # Setup the environment to the base state of the PR
        pr.setup_env(self.env)

        exit_status, result = self.generator.run(task)

        save_traj(
            generator=self.generator,
            path=output_path / "statementAgent_traces" / f"{pr.number}.traj.json",
            exit_status=exit_status,
            result=result,
            instance_id=pr.number,
        )

        # Add the problem description file content
        try:
            issue_description = extract_created_file_content(
                result, metadata_relpath
            )
        except ValueError as e:
            logger.error(
                "Failed to extract created file content for PR %s: %s",
                pr.number,
                e,
            )
            return pr


        # Update PR instance with triage results
        pr.problem_description = issue_description

        return pr
