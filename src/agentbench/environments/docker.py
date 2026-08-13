# Forked from: https://github.com/SWE-agent/mini-swe-agent

import errno
import logging
import os
import shlex
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
import posixpath

from agentbench import Environment


class BaseDockerEnvironment:
    """Base class for Docker environments that provides apply_patch script setup."""
    
    def __init__(self):
        self.logger = logging.getLogger("agentbench.environment")
    
    def _get_apply_patch_script_path(self) -> Path | None:
        """Get the path to the apply_patch script."""
        script_path = Path(__file__).parent / "extra" / "apply_patch.py"
        if not script_path.exists():
            self.logger.warning(f"apply_patch script not found at {script_path}")
            return None
        return script_path
    
    def _setup_apply_patch_script(self):
        """Copy the apply_patch script to the container and make it available in PATH.
        Must be implemented by subclasses based on their container access method.
        """
        raise NotImplementedError("Subclasses must implement _setup_apply_patch_script")


def _default_run_args() -> list[str]:
    """Default `docker run` args, including per-container resource caps.

    Without caps, the number of harness workers is the only throttle: a single
    pytest run can take every core on the host. That matters on a shared
    machine. Both the generation path (agent containers) and the evaluation
    path (test containers) construct environments through this config, so the
    caps belong here rather than at one call site.

    Tunable per run without code changes:
        AGENTBENCH_CONTAINER_CPUS    (default 8; set to 0 or "" to uncap)
        AGENTBENCH_CONTAINER_MEMORY  (default 16g; set to "" to uncap)
    """
    args = ["--rm"]
    cpus = os.getenv("AGENTBENCH_CONTAINER_CPUS", "8")
    memory = os.getenv("AGENTBENCH_CONTAINER_MEMORY", "16g")
    if cpus and float(cpus) > 0:
        args.append(f"--cpus={cpus}")
    if memory:
        args.append(f"--memory={memory}")
    return args


@dataclass
class DockerEnvironmentConfig:
    image: str
    cwd: str = "/project/testbed"
    """Working directory in which to execute commands."""
    env: dict[str, str] = field(default_factory=dict)
    """Environment variables to set in the container."""
    forward_env: list[str] = field(default_factory=list)
    """Environment variables to forward to the container.
    Variables are only forwarded if they are set in the host environment.
    In case of conflict with `env`, the `env` variables take precedence.
    """
    timeout: int = 30
    """Timeout for executing commands in the container."""
    executable: str = os.getenv("MSWEA_DOCKER_EXECUTABLE", "docker")
    """Path to the docker/container executable."""
    run_args: list[str] = field(default_factory=_default_run_args)
    """Additional arguments to pass to the docker/container executable.
    Defaults to ["--rm"] plus CPU/memory caps -- see `_default_run_args`.
    """
    container_timeout: str = "2h"
    """Max duration to keep container running. Uses the same format as the sleep command."""


class DockerEnvironment(BaseDockerEnvironment, Environment):
    def __init__(self, *, config_class: type = DockerEnvironmentConfig, logger=None, **kwargs):
        """This class executes bash commands in a Docker container using direct docker commands.
        See `DockerEnvironmentConfig` for keyword arguments.
        """
        self._container_path: str | None = None
        BaseDockerEnvironment.__init__(self)
        self.logger = logger or logging.getLogger("agentbench.environment")
        self.container_id: str | None = None
        self.config = config_class(**kwargs)
        self._start_container()

    def get_template_vars(self) -> dict[str, Any]:
        return asdict(self.config)

    def _start_container(self):
        """Start the Docker container and return the container ID."""
        container_name = f"agentbench-{uuid.uuid4().hex[:8]}"
        cmd = [
            self.config.executable,
            "run",
            "-d",
            #"--add-host=host.docker.internal:172.17.0.1",
            "--network=host",
            "--name",
            container_name,
            "-w",
            self.config.cwd,
            *self.config.run_args,
            self.config.image,
            "sleep",
            self.config.container_timeout,
        ]
        self.logger.info(f"Starting container with command: {shlex.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60*60,  # docker pull might take a while
            check=True,
        )
        self.logger.info(f"Started container {container_name} with ID {result.stdout.strip()}")
        self.container_id = result.stdout.strip()

        # copy /testbed to /projects/main
        if self.config.cwd == "/project/testbed":
            output = self.execute("mkdir -p /project && mv /testbed /project", timeout=False)
            self.logger.info(f"Moved /testbed to /project/testbed: {output['output']}")
        self._capture_container_environment()
        # Copy apply_patch script to container and make it executable
        # self._setup_apply_patch_script()

    def _setup_apply_patch_script(self):
        """Copy the apply_patch script to the container and make it available in PATH."""
        if not self.container_id:
            return
        
        script_path = self._get_apply_patch_script_path()
        if not script_path:
            return
        
        try:
            # Copy script to /usr/local/bin in the container
            copy_cmd = [
                self.config.executable,
                "cp",
                str(script_path),
                f"{self.container_id}:/usr/local/bin/apply_patch"
            ]
            subprocess.run(copy_cmd, check=True, capture_output=True)
            
            # Make it executable
            chmod_cmd = [
                self.config.executable,
                "exec",
                self.container_id,
                "chmod",
                "+x",
                "/usr/local/bin/apply_patch"
            ]
            subprocess.run(chmod_cmd, check=True, capture_output=True)
            
            self.logger.debug("Successfully installed apply_patch script in container")
        except subprocess.CalledProcessError as e:
            self.logger.warning(f"Failed to install apply_patch script: {e}")

    def _capture_container_environment(self) -> None:
        """Capture useful environment settings from the container."""
        if not self.container_id:
            return
        try:
            cmd = [
                self.config.executable,
                "exec",
                self.container_id,
                "env",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            for line in result.stdout.splitlines():
                if line.startswith("PATH="):
                    self._container_path = line[len("PATH=") :]
                    break
        except subprocess.CalledProcessError as exc:
            self.logger.debug(f"Failed to capture container environment: {exc}")

    def _prepare_shell_command(self, command: str) -> str:
        shell_command = command
        if self._container_path:
            safe_path = self._container_path.replace('"', r'\"')
            shell_command = f'export PATH="{safe_path}:$PATH"; {command}'
        return shell_command

    def _build_exec_command(
        self,
        cwd: str,
        *,
        use_stdin: bool,
        shell_command: str | None = None,
    ) -> list[str]:
        cmd = [self.config.executable, "exec"]
        if use_stdin:
            cmd.append("-i")
        cmd.extend(["-w", cwd])
        for key in self.config.forward_env:
            if (value := os.getenv(key)) is not None:
                cmd.extend(["-e", f"{key}={value}"])
        for key, value in self.config.env.items():
            cmd.extend(["-e", f"{key}={value}"])
        cmd.append(self.container_id)
        if use_stdin:
            cmd.extend(["bash", "-l", "-s"])
        else:
            if shell_command is None:
                raise ValueError("shell_command must be provided when use_stdin is False")
            cmd.extend(["bash", "-lc", shell_command])
        return cmd

    def _should_use_stdin(self, cmd: list[str]) -> bool:
        arg_max: int | None = None
        if hasattr(os, "sysconf"):
            try:
                arg_max = os.sysconf("SC_ARG_MAX")
            except (AttributeError, OSError, ValueError):
                arg_max = None
        if not arg_max:
            arg_max = 2 * 1024 * 1024
        cmd_length = sum(len(arg) + 1 for arg in cmd)
        env_length = 0
        for key, value in os.environ.items():
            env_length += len(os.fsencode(key)) + len(os.fsencode(value)) + 2
        return cmd_length + env_length >= arg_max - 4096

    def _stdin_payload(self, shell_command: str) -> str:
        if shell_command.endswith("\n"):
            return shell_command
        return f"{shell_command}\n"

    def execute(self, command: str, cwd: str = "", timeout=True) -> dict[str, Any]:
        """Execute a command in the Docker container and return the result as a dict."""
        cwd = cwd or self.config.cwd
        assert self.container_id, "Container not started"

        shell_command = self._prepare_shell_command(command)
        cmd = self._build_exec_command(cwd, use_stdin=False, shell_command=shell_command)
        use_stdin = self._should_use_stdin(cmd)
        if use_stdin:
            cmd = self._build_exec_command(cwd, use_stdin=True)
            exec_input = self._stdin_payload(shell_command)
            self.logger.debug(
                "Executing command in container %s via stdin: %s",
                self.container_id,
                shlex.join(cmd),
            )
        else:
            exec_input = None
            self.logger.debug(
                "Executing command in container %s: %s",
                self.container_id,
                shlex.join(cmd),
            )
        try:
            result = subprocess.run(
                cmd,
                text=True,
                timeout=self.config.timeout if timeout else 60*60*2,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                input=exec_input,
            )
        except OSError as exc:
            if exc.errno != errno.E2BIG or use_stdin:
                raise
            cmd = self._build_exec_command(cwd, use_stdin=True)
            exec_input = self._stdin_payload(shell_command)
            self.logger.warning(
                "Command too long for exec args in container %s; retrying via stdin",
                self.container_id,
            )
            self.logger.debug(
                "Executing command in container %s via stdin: %s",
                self.container_id,
                shlex.join(cmd),
            )
            result = subprocess.run(
                cmd,
                text=True,
                timeout=self.config.timeout if timeout else 60*60*2,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                input=exec_input,
            )
        self.logger.debug(f"Command output in container {self.container_id}: {result.stdout}")

        return {"output": result.stdout, "returncode": result.returncode}

    def execute_stream(
        self,
        command: str,
        cwd: str = "",
        timeout=True,
        on_output: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Execute a command in the Docker container and stream its output."""
        cwd = cwd or self.config.cwd
        assert self.container_id, "Container not started"

        shell_command = self._prepare_shell_command(command)
        cmd = self._build_exec_command(cwd, use_stdin=False, shell_command=shell_command)
        use_stdin = self._should_use_stdin(cmd)
        if use_stdin:
            cmd = self._build_exec_command(cwd, use_stdin=True)
            stdin_payload = self._stdin_payload(shell_command)
            self.logger.debug(
                "Executing command in container %s via stdin: %s",
                self.container_id,
                shlex.join(cmd),
            )
        else:
            stdin_payload = None
            self.logger.debug(
                "Executing command in container %s: %s",
                self.container_id,
                shlex.join(cmd),
            )
        try:
            process = subprocess.Popen(
                cmd,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                stdin=subprocess.PIPE if use_stdin else None,
            )
        except OSError as exc:
            if exc.errno != errno.E2BIG or use_stdin:
                raise
            use_stdin = True
            cmd = self._build_exec_command(cwd, use_stdin=True)
            stdin_payload = self._stdin_payload(shell_command)
            self.logger.warning(
                "Command too long for exec args in container %s; retrying via stdin",
                self.container_id,
            )
            self.logger.debug(
                "Executing command in container %s via stdin: %s",
                self.container_id,
                shlex.join(cmd),
            )
            process = subprocess.Popen(
                cmd,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                stdin=subprocess.PIPE,
            )
        output_lines: list[str] = []

        def reader() -> None:
            if process.stdout is None:
                return
            for line in process.stdout:
                output_lines.append(line)
                if on_output:
                    on_output(line)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        if use_stdin and process.stdin:
            try:
                process.stdin.write(stdin_payload)
                process.stdin.close()
            except Exception as exc:
                self.logger.debug("Failed to send stdin payload: %s", exc)
        try:
            if timeout:
                process.wait(timeout=self.config.timeout)
            else:
                process.wait(timeout=60*60*2)
        except subprocess.TimeoutExpired:
            self.logger.warning("Command timed out in container %s", self.container_id)
            process.kill()
            process.wait(timeout=5)
        thread.join(timeout=1)
        if process.stdout:
            try:
                process.stdout.close()
            except Exception:
                pass

        return {"output": "".join(output_lines), "returncode": process.returncode}

    def read_file(self, filename: str) -> str:
        """Read a file from the container and return its content.
        
        Args:
            filename: The path to the file to read.
            
        Returns:
            The content of the file as a string, or an empty string if the file does not exist.
        """
        result = self.execute(f"cat {shlex.quote(filename)}")
        if result["returncode"] != 0:
            self.logger.warning(f"Failed to read file {filename} in container {self.container_id}")
            return ""
        return result["output"]

    def write_file(self, path: str, file_content: str) -> None:
        """Write content to a file in the container.
        
        Args:
            path: The path to the file to write.
            file_content: The content to write.
        """
        # Resolve path to absolute using posixpath to ensure Linux separators
        if not posixpath.isabs(path):
            container_path = posixpath.join(self.config.cwd, path)
        else:
            container_path = path

        # Create parent directory if needed
        parent_dir = posixpath.dirname(container_path)
        if parent_dir:
            self.execute(f"mkdir -p {shlex.quote(parent_dir)}")

        self.execute(f"echo {shlex.quote(file_content)} > {shlex.quote(container_path)}")

    def cleanup(self):
        """Stop and remove the Docker container."""
        if getattr(self, "container_id", None) is not None:  # if init fails early, container_id might not be set
            cmd = f"(timeout 60 {self.config.executable} stop {self.container_id} || {self.config.executable} rm -f {self.container_id}) >/dev/null 2>&1 &"
            subprocess.Popen(cmd, shell=True)

    def __del__(self):
        """Cleanup container when object is destroyed."""
        self.cleanup()

    def reset(self) -> None:
        """Reset the environment by stopping and removing the container, then starting a new one."""
        self.cleanup()
        self.container_id = None
        self._start_container()
