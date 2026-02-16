from pathlib import Path
import json
import threading
import textwrap
import traceback

from benchmark_generator import Agent
from benchmark_generator.pull_request import PullRequestInstance
from benchmark_generator.constants import SETUP_AGENT_PROMPT_TEMPLATE
from benchmark_generator.agents.triage_agent import extract_decision_from_patch

from agentbench.utils.io_utils import save_traj
from agentbench.utils.log import logger


LOCK = threading.Lock()

EXAMPLE_FILE_PROMPT = textwrap.dedent(
    """
    Below is an example of files that worked for a similar repository:
    ```
    # {decision_path} content
    {{
      "setup_commands": {setup_commands_example},
      "test_commands": {test_commands_example}
    }}
    
    # run_tests.py content
    {run_tests_example}
    ```
    """
).strip()

def render_statement_task(
    decision_path: str = "setup_info.json",
    example_files_section: str = "",
) -> str:
    
    return SETUP_AGENT_PROMPT_TEMPLATE.format(
        decision_path=decision_path,
        example_files_section=example_files_section,
    )

class SetupAgent(Agent):
    """Agent that enhances problem description."""

    def __init__(self, model, env, generator) -> None:
        self.model = model
        self.env = env
        self.generator = generator

    def _fetch_prior_solution(self, output_path: Path) -> tuple[dict[str, list[str] | str], bool]:
        """Fetch prior solutions from other PRs in the statement phase."""
        statement_pr_dir = output_path / "statements"
        valid_prs = statement_pr_dir.glob("*.json")
        valid_prs = sorted(valid_prs)
        
        # Select the most recent valid PR (pr names are id.json)
        output = {
            "setup_commands_example": [],
            "test_commands_example": [],
            "run_tests_example": "# No example available",
        }
        found = False

        if valid_prs:
            logger.info(f"Found valid PRs {valid_prs[-1]} to use as setup examples.")
            with open(valid_prs[-1], "r", encoding="utf-8") as f:
                example_data = json.load(f)
            setup_commands_example = example_data.get("setup_commands", [])
            test_commands_example = example_data.get("repo_test_commands", [])
            run_tests_example = example_data.get("repo_test_runner", "# No example available")
            output = {
                "setup_commands_example": setup_commands_example,
                "test_commands_example": test_commands_example,
                "run_tests_example": run_tests_example,
            }
            found = True
        
        return output, found

    def _fetch_example_files(self, output_path: Path) -> str:

        prior_decision, found = self._fetch_prior_solution(output_path)
        if found:
            example = EXAMPLE_FILE_PROMPT.format(
                decision_path="setup_info.json",
                setup_commands_example=json.dumps(
                    prior_decision["setup_commands_example"], indent=2
                ),
                test_commands_example=json.dumps(
                    prior_decision["test_commands_example"], indent=2
                ),
                run_tests_example=prior_decision["run_tests_example"],
            )
            return example
        return ""
            
    def _verify_setup(self, pr: PullRequestInstance, decision_json: dict, test_script: str, checkout_command: str) -> None:
        
        is_valid_setup = True
        
        try:
            self.env.reset()

            self.env.execute(checkout_command)
            self.env.execute("git reset --hard")

            for cmd in decision_json.get("setup_commands", []):
                self.env.execute(cmd, timeout=False)

            self.env.execute("rm -f run_tests.py", timeout=False)
            self.env.write_file("run_tests.py", test_script)

            self.env.execute("rm -f test_results.json", timeout=False)
            for cmd in decision_json.get("test_commands", []):
                self.env.execute(cmd, timeout=False)

            test_results = self.env.read_file("test_results.json")
            test_results = json.loads(test_results)

            if not any(test_results.values()):
                logger.warning(
                    f"Invalid setup -- No tests are successful for instance {pr.instance_id}."
                )
                is_valid_setup = False
        except Exception as e:
            logger.error(f"Error while verifying setup for PR #{pr.number}: {e}")
            logger.error(traceback.format_exc())
            is_valid_setup = False

        return is_valid_setup



    def process_pr(self, pr: PullRequestInstance, output_path: Path) -> PullRequestInstance:
        """Enhance the problem description of the PR."""

        commit = pr.base_sha
        checkout_command = f"git checkout {commit}"

        # First try if there is a prior solution that already works
        prior_solution, found = self._fetch_prior_solution(output_path)
        if found:
            logger.info(f"Found prior setup solution for PR #{pr.number}, verifying...")
            is_valid = self._verify_setup(
                pr,
                {
                    "setup_commands": prior_solution["setup_commands_example"],
                    "test_commands": prior_solution["test_commands_example"],
                },
                prior_solution["run_tests_example"],
                checkout_command,
            )
            if is_valid:
                logger.info(f"Using prior setup solution for PR #{pr.number}.")
                pr.setup_commands = prior_solution["setup_commands_example"]
                pr.repo_test_commands = prior_solution["test_commands_example"]
                pr.repo_test_runner = prior_solution["run_tests_example"]
                return pr
            else:
                logger.info(f"Prior setup solution invalid for PR #{pr.number}, generating new setup.")


        decision_path = "setup_info.json"

        example = self._fetch_example_files(output_path)

        task = render_statement_task(decision_path=decision_path, example_files_section=example)
        
        # Checkout the base commit in the environment and delete the future git history
        self.env.execute(checkout_command)
        self.env.execute("git reset --hard")

        exit_status, result = self.generator.run(task)

        save_traj(
            generator=self.generator,
            path=output_path / "setupAgent_traces" / f"{pr.number}.traj.json",
            exit_status=exit_status,
            result=result,
            instance_id=pr.number,
        )
        
        # Parse the diff
        result_data = extract_decision_from_patch(
            result, decision_path=decision_path
        )
        test_script = extract_decision_from_patch(
            result, decision_path="run_tests.py"
        )

        # Parse the JSON content
        try:
            decision_json = json.loads(result_data)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output for PR #{pr.number}: {e}")
            logger.error(f"Output was: {result_data}")
            decision_json = {
                "setup_commands": None,
                "test_commands": None,
            }

        # Actually run the repo tests after applying the patch
        setup_valid = self._verify_setup(
            pr,
            decision_json,
            test_script,
            checkout_command,
        )
        if not setup_valid:
            logger.error(f"Generated setup is invalid for PR #{pr.number}.")
            return pr


        # Update the PR instance
        pr.setup_commands = decision_json.get("setup_commands")
        pr.repo_test_commands = decision_json.get("test_commands")
        pr.repo_test_runner = test_script

        # If the example file is not

        return pr
