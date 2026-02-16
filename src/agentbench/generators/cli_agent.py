import json
import shlex
from dataclasses import asdict, dataclass
from typing import List
import logging

from jinja2 import Template

from agentbench import Generator, Environment, Model
from agentbench.model.litellm_wrapper.litellm_server import LitellmServer


@dataclass
class CLIAgentConfig:
    launch_command: str
    install_commands: List[str]
    post_install_commands: List[str]
    post_exec_commands: List[str]
    cli_name: str
    instance_template: str = ("Please edit the codebase to address the following task:\n\n{{task}}")


class TerminatingException(Exception):
    """Raised for conditions that terminate the agent."""


class Submitted(TerminatingException):
    """Raised when the LM declares that the agent has finished its task."""

class APIError(TerminatingException):
    """Raised when the traces are empty due to an API error."""


class CLIAgent(Generator):
    """Wraps a CLI-based agent (e.g. qwen-code) to interact with AgentBench."""

    def __init__(
        self,
        model: Model,
        env: Environment,
        **kwargs,
    ):
        self.config = CLIAgentConfig(**kwargs)
        self.messages: list[dict] = []
        self.model = model
        self.env = env
        self.extra_template_vars = {}
        self.logger = logging.getLogger("agentbench.cli_agent")

    def _install(self):
        """Install the underlying CLI agent."""

        # Run the install commands
        for cmd in self.config.install_commands:
            self.env.execute(cmd, timeout=False)

        # Run the post-install commands
        for cmd in self.config.post_install_commands:
            self.env.execute(cmd, timeout=False)

    def _post_exec(self):
        """Run any post-execution commands."""
        for cmd in self.config.post_exec_commands:
            self.env.execute(cmd, timeout=False)

        # Clear the traces
        self.model.delete_traces()

    def _process_logs(self):
        traces_path = self.model.get_traces_path()

        
        try:
            with open(traces_path) as f:
                lines = f.readlines()
        except FileNotFoundError:
            return

        if len(lines) == 0:
            raise APIError("No traces found. Possible API error.")

        traces = [json.loads(line) for line in lines]
        traces = [trace for trace in traces if trace.get("event") == "success"]
        if len(traces) == 0:
            self.logger.error("No successful traces found. Possible API error.")
            return

        messages = traces[-1].get("request", [])

        try:
            traces[-1].get("response", {}).get("choices", [{}])[0].get("message", {})
        except AttributeError:
            raise APIError("Malformed response in traces. Possible API error.")

        messages.append(
            traces[-1].get("response", {}).get("choices", [{}])[0].get("message", {})
        )
        self.messages.extend(messages)
        for trace in traces:
            self.model.responses.append(trace["response"])

    def render_template(self, template: str, **kwargs) -> str:
        template_vars = (
            asdict(self.config)
            | self.env.get_template_vars()
            | self.model.get_template_vars()
        )
        return Template(template).render(
            **kwargs, **template_vars, **self.extra_template_vars
        )

    def add_message(self, role: str, content: str, **kwargs):
        self.messages.append({"role": role, "content": content, **kwargs})

    def _normalize_openai_args(self, kwargs: dict) -> dict:
        """Some models use different urls (e.g. Claude Code)"""

        url = kwargs.get("base_url")
        
        if self.config.cli_name == "claude_code" or self.config.cli_name == "gemini_cli":
            if url is not None:
                kwargs["base_url"] = url.replace("/v1", "")
        return kwargs

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """Run step() until agent is finished. Return exit status & message"""

        # Ensure the model is LiteLLM server
        assert isinstance(self.model, LitellmServer), (
            "AgentWrapper currently only supports LitellmServer model."
        )

        self.extra_template_vars |= {"task": task, **kwargs}
        self.messages = []
        prompt = self.render_template(self.config.instance_template)

        # Install the underlying CLI agent
        self._install()

        # Prepare the command
        openai_args = self.model.get_openai_args()
        openai_args = self._normalize_openai_args(openai_args)
        launch_command = self.config.launch_command.format(
            **openai_args, prompt=shlex.quote(prompt)
        )

        # Run the CLI
        exec_result = self.env.execute(launch_command, timeout=False)

        # Process the logs
        self._process_logs()

        # Clean the environment
        self._post_exec()

        if exec_result.get("returncode", 0) != 0:
            message = exec_result.get("output", "")
            return "ExecutionFailed", message

        final_command = "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && git add -A && git diff --cached"
        final_result = self.env.execute(final_command, timeout=False)

        try:
            self.has_finished(final_result)
        except TerminatingException as e:
            self.add_message("user", str(e))
            return type(e).__name__, str(e)

    def has_finished(self, output: dict[str, str]):
        """Raises Submitted exception with final output if the agent has finished its task."""
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        raise Submitted("".join(lines[1:]))
