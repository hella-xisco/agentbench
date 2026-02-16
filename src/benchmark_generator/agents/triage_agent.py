from pathlib import Path
from typing import Any
import json

from benchmark_generator import Agent
from benchmark_generator.pull_request import PullRequestInstance
from benchmark_generator.constants import TRIAGE_PROMPT_TEMPLATE

from agentbench.utils.io_utils import save_traj
from agentbench.utils.log import logger


def render_triage_task(
    pr: PullRequestInstance, decision_path: str
) -> str:
    body = (pr.body or "").strip() or "(no description provided)"
    patch_excerpt = pr.patch
    lines = patch_excerpt.strip().splitlines()
    if len(lines) > 400:
        lines = lines[:400]
        lines.append("... [diff truncated]")
    excerpt = "\n".join(lines)
    return TRIAGE_PROMPT_TEMPLATE.format(
        pr_number=pr.number,
        repo_full_name=pr.base_repo,
        title=pr.title,
        author=pr.author,
        merged_at=pr.merged_at,
        body=body,
        excerpt=excerpt,
        decision_path=decision_path,
    )

def extract_decision_from_patch(model_patch: str, decision_path: str) -> dict[str, Any]:
    # The pattern is: +content after +++ b/AGENTS.md
    lines = model_patch.split("\n")

    in_proposed_changes = False
    plan_lines = []

    for line in lines:
        # Start capturing when we see the decision file
        if line.startswith(f"+++ b/{decision_path}"):
            in_proposed_changes = True
            continue

        # Stop capturing when we hit another file (starts with diff --git or +++)
        if in_proposed_changes and (
            line.startswith("diff --git")
            or (line.startswith("+++") and (decision_path not in line))
        ):
            break

        # Capture content lines (those starting with +)
        if in_proposed_changes and line.startswith("+"):
            # Remove the leading + and add to plan
            plan_lines.append(line[1:])

    return "\n".join(plan_lines).strip()




class TriageAgent(Agent):
    """Agent that triages PRs for suitability for benchmark generation."""


    def __init__(self, model: Any, env: Any, generator: Any) -> None:
        self.model = model
        self.env = env
        self.generator = generator

    def _rule_based_checks(self, pr: PullRequestInstance) -> bool:

        rule_based_decision = pr.is_valid_pr()

        for check, passed in rule_based_decision.items():
            if not passed:
                # Update PR instance with triage results
                pr.is_suitable = False
                pr.risk_factors = [f"Failed check: {check}"]
                pr.rationale = f"PR did not pass the rule-based check: {check}."
                pr.needs_manual_review = False
                pr.key_files = []
                return False
        return True


    def process_pr(self, pr: PullRequestInstance, output_path: Path) -> PullRequestInstance:
        """Triage the PR based on rule-based checks."""

        # First apply rule-based checks
        if not self._rule_based_checks(pr):
            return pr
        
        task = render_triage_task(pr, decision_path=f"triage_pr_{pr.number}.json")

        exit_status, result = self.generator.run(task)

        save_traj(
            generator=self.generator,
            path=output_path / "triageAgent_traces" / f"{pr.number}.traj.json",
            exit_status=exit_status,
            result=result,
            instance_id=pr.number,
        )
            
        result_data = extract_decision_from_patch(
            result, decision_path=f"triage_pr_{pr.number}.json"
        )


        # Parse the JSON content
        try:
            decision_json = json.loads(result_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output for PR #{pr.number}: {e}")
            logger.error(f"Output was: {result_data}")
            decision_json = {
                "pr_number": pr.number,
                "suitable": False,
                "needs_manual_review": True,
                "decision": "manual_review",
                "rationale": f"Failed to parse JSON output: {e}",
                "key_files": [],
                "risk_factors": ["json_parse_error"],
            }


        # Update PR instance with triage results
        pr.is_suitable = decision_json.get("suitable", False)
        pr.risk_factors = decision_json.get("risk_factors", [])
        pr.rationale = decision_json.get("rationale", "")
        pr.needs_manual_review = decision_json.get("needs_manual_review", False)
        pr.key_files = decision_json.get("key_files", [])

        # Add the test patch 
        _, test_patch, _ = pr.split_patch()
        pr.pr_test_patch = test_patch

        return pr
