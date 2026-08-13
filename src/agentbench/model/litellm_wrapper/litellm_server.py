from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from openai import OpenAI
import logging
import socket

from agentbench import Model
from agentbench.utils.others import retry
from agentbench.utils.trace import MODEL_PRICES, TokenUsage
from .litellm_logger import LOG_PATH


@dataclass
class LitellmServerConfig:
    model_name: str
    api_base: str | None = None
    model_kwargs: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> LitellmServerConfig:
        return LitellmServerConfig(
            model_name=d["model_name"],
            api_base=d.get("api_base"),
            model_kwargs=d.get("model_kwargs", {}) or {},
        )

def _ensure_dir(p: str | Path) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_primary_ip(fallback: str = "127.0.0.1") -> str:
    
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return fallback
    finally:
        s.close()


class LitellmServer(Model):
    """
    Simple wrapper that:
      1) Launches a LiteLLM OpenAI-compatible proxy on localhost
      2) Lets you query the configured model directly via litellm
      3) Record the traces independently of the agents used
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 18080,
        log_dir: str = "logs/litellm_server",
        startup_wait_s: float = 5.0,
        auto_cost_updates: bool = True,
        cost_poll_interval_s: float = 0.5,
        **kwargs: Any,
    ) -> None:
        self.config = LitellmServerConfig(**kwargs)
        self.cost: float = 0.0
        self.n_calls: int = 0
        self.responses: list[dict[str, Any]] = []

        self._host = host
        self._bind_host = get_primary_ip() if host == "0.0.0.0" else host
        self._port = port
        self._startup_wait_s = startup_wait_s

        self._log_dir = _ensure_dir(log_dir)
        self._server_cfg_path: str | None = None
        self._server_proc: subprocess.Popen | None = None
        self._server_log_fp = None
        self._proxy_url = f"http://{self._bind_host}:{self._port}/v1"

        self._api_key = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=64))
        self._auto_cost_updates = auto_cost_updates
        self._cost_poll_interval_s = cost_poll_interval_s
        self._cost_lock = threading.Lock()
        self._cost_watcher_stop_event = threading.Event()
        self._cost_watcher_thread: threading.Thread | None = None

        self.logger = logging.getLogger("agentbench.model.litellm_server")

        atexit.register(self.stop)

    def update_port(self, new_port: int) -> None:
        """Update the port used by the server (must be called before serve())."""
        self._port = new_port
        self._proxy_url = f"http://{self._bind_host}:{self._port}/v1"

    def get_api_key(self) -> str:
        return self._api_key

    def get_traces_path(self) -> Path:
        return Path(LOG_PATH) / f"{self._api_key}.json"

    def delete_traces(self) -> None:
        self.logger.debug(f"Deleting traces for API key: {self._api_key}")
        traces_path = self.get_traces_path()
        if traces_path.exists():
            try:
                os.remove(traces_path)
            except OSError:
                pass

    # ------------- public API -------------
    def serve(self) -> None:
        """
        Start a LiteLLM proxy on localhost using a generated config.
        The proxy will expose an OpenAI-compatible API at: http://host:port/v1
        """
        if self._server_proc and self._server_proc.poll() is None:
            return

        alias = self.config.model_name
        self.logger.debug(f"Model '{self.config.model_name}' as alias '{alias}'")
        proxy_cfg = {
            # A single-model list mapping to your configured model
            "model_list": [
                {
                    # Alias exposed by the proxy. Using the same string is convenient,
                    # but you could also put a friendly alias here.
                    "model_name": alias,
                    "litellm_params": {
                        "model": self.config.model_name,
                        **({"api_base": self.config.api_base} if self.config.api_base else {}),
                        **(self.config.model_kwargs or {}),
                    },
                },
                {
                    "model_name": "claude-haiku-4-5-20251001",
                    "litellm_params": {
                        "model": "claude-haiku-4-5-20251001",
                        **({"api_base": self.config.api_base} if self.config.api_base else {}),
                        **(self.config.model_kwargs or {}),
                    },
                }
            ],
            "general_settings": {"drop_params": True, "disable_responses_id_security": True},
            "litellm_settings": {
                "json_logs": True,
                "callbacks": "litellm_logger.file_logger",
            },
        }

        # Write to a temp file (next to logs for convenience)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", dir=str(self._log_dir)
        )
        json.dump(proxy_cfg, tmp, indent=2)
        tmp.flush()
        tmp.close()
        self._server_cfg_path = tmp.name

        # Copy the callback to the log dir so LiteLLM can import it
        logger_src = Path(__file__).with_name("litellm_logger.py")
        logger_dest = self._log_dir / "litellm_logger.py"
        shutil.copy(logger_src, logger_dest)

        # Open a log file for the proxy process
        log_path = self._log_dir / f"proxy_{self._port}.log"
        self._server_log_fp = open(log_path, "a", buffering=1)

        cmd = ["litellm", "--config", self._server_cfg_path,
                   "--host", self._host, "--port", str(self._port)]
        
        self.logger.debug(f"Starting LiteLLM proxy with command: {' '.join(cmd)}")
        self._server_proc = subprocess.Popen(
            cmd,
            stdout=self._server_log_fp,
            stderr=self._server_log_fp,
            close_fds=True,
        )
        self.logger.debug(f"LiteLLM proxy started with PID: {self._server_proc.pid}")

        # Ensure litellm process is started (else get connection errors)
        self._wait_until_ready()
        self._start_cost_watcher()

    def _wait_until_ready(self, timeout_s: float = 120.0) -> None:
        """Block until the proxy accepts connections, or raise.

        Upstream slept `startup_wait_s` seconds here and continued regardless of the
        outcome. A proxy that died on import -- or was merely slower than the sleep --
        left the port closed, and every agent in the run failed with
        `ConnectionRefused` at zero API calls. In the results those instances are
        indistinguishable from an agent that genuinely could not solve the task, so
        the failure does not surface as an error but as a lower resolve rate. For a
        benchmark that is a data-integrity problem, not a nuisance: fail loudly here
        instead of silently mismeasuring.
        """
        budget_s = max(timeout_s, self._startup_wait_s)
        deadline = time.time() + budget_s
        log_hint = f"see {self._log_dir}/proxy_{self._port}.log"
        while time.time() < deadline:
            if self._server_proc is not None and self._server_proc.poll() is not None:
                raise RuntimeError(
                    f"LiteLLM proxy exited with code {self._server_proc.returncode} "
                    f"before becoming ready; {log_hint}"
                )
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(1.0)
                if probe.connect_ex((self._bind_host, self._port)) == 0:
                    self.logger.debug(
                        f"LiteLLM proxy ready on {self._bind_host}:{self._port}"
                    )
                    return
            time.sleep(0.5)
        raise RuntimeError(
            f"LiteLLM proxy not ready on {self._bind_host}:{self._port} "
            f"after {budget_s:.0f}s; {log_hint}"
        )

    def stop(self) -> None:
        """Stop the proxy and clean up temp files."""

        self._stop_cost_watcher()
        self.delete_traces()

        if self._server_proc:
            self.logger.debug(f"Stopping LiteLLM proxy with PID: {self._server_proc.pid}")
        if self._server_proc and self._server_proc.poll() is None:
            try:
                self._server_proc.terminate()
                try:
                    self._server_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._server_proc.kill()
            finally:
                self._server_proc = None

        if self._server_log_fp:
            try:
                self._server_log_fp.flush()
            finally:
                self._server_log_fp.close()
            self._server_log_fp = None

        if self._server_cfg_path and os.path.exists(self._server_cfg_path):
            try:
                os.remove(self._server_cfg_path)
            except OSError:
                pass
            self._server_cfg_path = None

    def get_openai_args(self) -> dict[str, Any]:
        api_key = self.get_api_key()
        base_url = self.proxy_url
        model_name = self.config.model_name
        return {"api_key": api_key, "base_url": base_url, "model": model_name}

    @retry(n_attempts=5) # For API errors / timeouts
    def query(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        openai_args = self.get_openai_args()

        model_name = openai_args.pop("model")

        client = OpenAI(**openai_args)
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content

    def get_cost(self) -> float:
        traces_path = self.get_traces_path()
        try:
            with open(traces_path) as f:
                lines = f.readlines()
        except FileNotFoundError:
            with self._cost_lock:
                self.cost = 0.0
                self.n_calls = 0
            return self.cost

        traces = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError:
                self.logger.debug("Skipping malformed trace line in %s", traces_path)

        success_traces = [trace for trace in traces if trace.get("event") == "success"]
        usage_by_model: dict[str, TokenUsage] = {}
        for trace in success_traces:
            response = trace.get("response")
            if not isinstance(response, dict):
                continue
            usage = response.get("usage")
            if not isinstance(usage, dict):
                continue
            model = response.get("model") or trace.get("model") or "unknown_model"
            model_name = str(model).split("/")[-1]
            usage_by_model.setdefault(model_name, TokenUsage()).add(usage)

        total_cost = 0.0
        for model_name, usage in usage_by_model.items():
            prices = MODEL_PRICES.get(model_name)
            if prices is None:
                continue
            input_price, output_price, cache_price, cache_creation_price = prices
            total_cost += usage.price(
                input_token_price=input_price,
                output_token_price=output_price,
                cache_token_price=cache_price,
                cache_creation_token_price=cache_creation_price,
            )

        with self._cost_lock:
            self.cost = total_cost
            self.n_calls = len(success_traces)
        return total_cost

    def get_template_vars(self) -> dict[str, Any]:
        return asdict(self.config) | {"n_model_calls": self.n_calls, "model_cost": self.cost}

    # ------------- convenience -------------
    @property
    def proxy_url(self) -> str | None:
        """Returns http://HOST:PORT/v1 if serve() has been called."""
        return self._proxy_url

    def _start_cost_watcher(self) -> None:
        if not self._auto_cost_updates:
            return
        if self._cost_watcher_thread and self._cost_watcher_thread.is_alive():
            return
        self._cost_watcher_stop_event.clear()
        self._cost_watcher_thread = threading.Thread(
            target=self._cost_watcher_loop,
            name="litellm-cost-watcher",
            daemon=True,
        )
        self._cost_watcher_thread.start()

    def _stop_cost_watcher(self) -> None:
        if not self._cost_watcher_thread:
            return
        self._cost_watcher_stop_event.set()
        self._cost_watcher_thread.join(timeout=2)
        self._cost_watcher_thread = None

    def _cost_watcher_loop(self) -> None:
        traces_path = self.get_traces_path()
        last_size = 0
        while not self._cost_watcher_stop_event.is_set():
            try:
                if traces_path.exists():
                    current_size = traces_path.stat().st_size
                    if current_size < last_size:
                        last_size = 0
                    if current_size > last_size:
                        last_size = current_size
                        self.get_cost()
                else:
                    last_size = 0
            except OSError:
                pass
            self._cost_watcher_stop_event.wait(self._cost_poll_interval_s)

    def __del__(self) -> None:
        self.stop()
        
