from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any
import shlex

from benchmark_generator.utils import split_patch_by_test_files, patch_change_python_files

from agentbench.benchmarks.agentbench import AgentbenchInstance

def _coerce_author(data: dict[str, Any]) -> str:
    """Best-effort extraction of author information from cached PR data."""
    explicit = data.get("author")
    if explicit:
        return str(explicit)
    user = data.get("user")
    if isinstance(user, dict) and user.get("login"):
        return str(user["login"])
    return ""


def _normalize_issues(raw_issues: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Retain only the fields needed downstream."""
    normalized: list[dict[str, str]] = []
    for issue in raw_issues:
        title = str(issue.get("title") or "")
        body = str(issue.get("body") or "")
        normalized.append({"title": title, "body": body})
    return normalized

@dataclass
class IssueInstance:
    """Minimal representation of an issue for the generation pipeline."""

    number: int
    title: str
    body: str
    state: str
    html_url: str

@dataclass
class PullRequestInstance:
    """Minimal representation of a pull request for the generation pipeline."""

    # Fetch from GitHub API
    number: int
    url: str
    title: str
    body: str
    author: str
    base_repo: str
    head_repo: str
    base_sha: str
    patch: str
    referenced_issues: list[IssueInstance] 
    merged_at: str | None
    created_at: str | None
    updated_at: str | None
    cache_updated_at: str | None = None

    # After triage
    is_suitable: bool | None = None
    pr_test_patch: str | None = None
    risk_factors: list[str] = field(default_factory=list)
    rationale: str | None = None
    needs_manual_review: bool = False
    key_files: list[str] = field(default_factory=list)

    # After setup
    setup_commands: list[str] | None = None
    repo_test_commands: list[str] | None = None
    repo_test_runner: str | None = None

    # After statement generation
    problem_description: str | None = None

    # After instance generation
    clean_pr_patch: str | None = None
    test_file_names: list[str] | None = None
    test_file_contents: list[str] | None = None
    test_commands: list[str] | None = None
    test_file_runner: str | None = None

    # After instance filtering
    repo_test_after_pr_patch: dict[str, Any] | None = None

    def is_valid_pr(self) -> dict[str, bool]:
        """Rule based check for PR validity."""

        has_issue_reference = len(self.referenced_issues) > 0
        python_file_changed = patch_change_python_files(self.patch or "")

        decision = {
            "has_issue_reference": has_issue_reference,
            "python_file_changed": python_file_changed,
        }

        return decision

    def setup_env(self, env: Any) -> None:
        """Setup the environment to the base state of the PR."""
        commit = self.base_sha

        # Fetch the base commit in the environment
        checkout_command = f"git checkout {commit}"
        env.execute(checkout_command)
        env.execute("git reset --hard")

        # Setup the environment
        if self.setup_commands:
            for cmd in self.setup_commands:
                env.execute(cmd)

        # Write the test script if available
        if self.repo_test_runner:
            env.execute(f"echo {shlex.quote(self.repo_test_runner)} > run_tests.py")

            
    @property
    def instance_id(self) -> str:
        return f"{self.head_repo.replace('/', '_')}-{self.number}"

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize to a cache-friendly dictionary.
        Uses asdict to automatically include any new fields added to the dataclass.
        """
        return dataclasses.asdict(self)

    def split_patch(self) -> tuple[str, str, str]:
        """Split the stored patch into non-test, test, and unclassified sections."""
        if self.patch is None:
            return "", "", ""
        non_test, test, other = split_patch_by_test_files(self.patch)
        return non_test, test, other

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PullRequestInstance":
        known_fields = {f.name for f in dataclasses.fields(cls)}
        filtered_args = {k: v for k, v in data.items() if k in known_fields}
        
        return cls(**filtered_args)

    def to_agentbench(self, docker_image: str) -> AgentbenchInstance:
        """Convert to a AgentbenchInstance."""
        return AgentbenchInstance(
            instance_id=str(self.number),
            repo=self.base_repo,
            task=self.problem_description,
            patch=self.clean_pr_patch,
            docker_image=docker_image,
            commit=self.base_sha,
            setup_commands=self.setup_commands,
            repo_test_commands=self.repo_test_commands,
            repo_test_runner=self.repo_test_runner,
            test_file_names=self.test_file_names,
            test_file_contents=self.test_file_contents,
            test_file_runner=self.test_file_runner,
            test_commands=self.test_commands,
            repo_test_after_pr_patch=self.repo_test_after_pr_patch or {},
        )
    