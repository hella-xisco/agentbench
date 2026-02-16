# Add the repo root to the path
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

import json
import concurrent.futures
from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import count
from pathlib import Path
from typing import Callable, Sequence
import threading

import fire

from benchmark_generator.config import (
    DEFAULT_OUTPUT_DIR,
    FILTERED_INSTANCES_DIR_NAME,
    INSTANCES_DIR_NAME,
    PR_CACHE_DIR_NAME,
    SETUP_RESULTS_DIR_NAME,
    STATEMENTS_DIR_NAME,
    TRIAGE_RESULTS_DIR_NAME,
    maybe_get_repo_config,
)
from benchmark_generator.pull_request import PullRequestInstance
from configs import ALL_GENERATOR_CONFIGS, ALL_MODEL_CONFIGS
from agentbench.utils.log import logger

from scripts.benchmark_gen_scripts.build_pr_cache import build_cache
from scripts.benchmark_gen_scripts.filter_instances import (
    filter_instances as run_filter_instances,
)
from scripts.benchmark_gen_scripts.run_agent import (
    instance_filter,
    run_agent_on_prs,
    setup_filter,
    statement_filter,
)

StageFilter = Callable[[PullRequestInstance], bool]


@dataclass
class AgentSpec:
    agent_type: str
    config: dict
    workers: int
    output_dir_name: str
    next_filter: StageFilter | None = None


STAGE_ORDER = ("triage", "setup", "statement", "instance", "filtering")
_WEB_REFRESH_SECONDS = 2

_PORT_COUNTER = count(start=20000)
_PORT_LOCK = threading.Lock()


class PipelineStatus:
    def __init__(self, stages: Sequence[str]) -> None:
        self._lock = threading.Lock()
        self._stage_map = {stage: set() for stage in stages}
        now = datetime.utcnow()
        self._started_at = now
        self._last_update = now

    def mark_start(self, stage: str, pr_number: int) -> None:
        with self._lock:
            self._stage_map.setdefault(stage, set()).add(pr_number)
            self._last_update = datetime.utcnow()

    def mark_end(self, stage: str, pr_number: int) -> None:
        with self._lock:
            self._stage_map.setdefault(stage, set()).discard(pr_number)
            self._last_update = datetime.utcnow()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "started_at": self._started_at.isoformat(timespec="seconds") + "Z",
                "last_update": self._last_update.isoformat(timespec="seconds") + "Z",
                "stages": {
                    stage: sorted(self._stage_map.get(stage, set()))
                    for stage in self._stage_map
                },
            }


def _render_status_page(snapshot: dict) -> str:
    rows: list[str] = []
    for stage in STAGE_ORDER:
        prs = snapshot["stages"].get(stage, [])
        if prs:
            prs_label = ", ".join(str(pr) for pr in prs)
        else:
            prs_label = "-"
        rows.append(
            "<tr>"
            f"<td class=\"stage\">{stage}</td>"
            f"<td class=\"count\">{len(prs)}</td>"
            f"<td class=\"prs\">{prs_label}</td>"
            "</tr>"
        )

    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head>",
            "  <meta charset=\"utf-8\">",
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
            f"  <meta http-equiv=\"refresh\" content=\"{_WEB_REFRESH_SECONDS}\">",
            "  <title>Agentbench Pipeline Status</title>",
            "  <style>",
            "    :root {",
            "      --ink: #1f1a17;",
            "      --ink-muted: #5e5a54;",
            "      --paper: #f6f1e6;",
            "      --card: rgba(255, 255, 255, 0.92);",
            "      --accent: #c9682b;",
            "      --accent-2: #2f6b73;",
            "      --border: rgba(31, 26, 23, 0.18);",
            "      --shadow: rgba(31, 26, 23, 0.12);",
            "    }",
            "    * { box-sizing: border-box; }",
            "    body {",
            "      margin: 0;",
            "      color: var(--ink);",
            "      font-family: \"Palatino Linotype\", \"Palatino\", \"Book Antiqua\", serif;",
            "      background:",
            "        radial-gradient(circle at 10% 15%, #f1d7b2 0%, transparent 50%),",
            "        radial-gradient(circle at 85% 20%, #cbe7e2 0%, transparent 45%),",
            "        linear-gradient(120deg, #f7efe0 0%, #efe5d6 55%, #f5efe6 100%);",
            "      min-height: 100vh;",
            "      padding: 28px;",
            "    }",
            "    header {",
            "      display: flex;",
            "      flex-direction: column;",
            "      gap: 8px;",
            "      margin-bottom: 18px;",
            "    }",
            "    h1 {",
            "      margin: 0;",
            "      font-size: 26px;",
            "      letter-spacing: 0.6px;",
            "    }",
            "    .meta {",
            "      color: var(--ink-muted);",
            "      font-size: 14px;",
            "    }",
            "    .card {",
            "      background: var(--card);",
            "      border: 1px solid var(--border);",
            "      border-radius: 14px;",
            "      box-shadow: 0 12px 30px var(--shadow);",
            "      padding: 18px 22px;",
            "      max-width: 920px;",
            "    }",
            "    table {",
            "      width: 100%;",
            "      border-collapse: collapse;",
            "    }",
            "    thead th {",
            "      text-align: left;",
            "      font-size: 12px;",
            "      text-transform: uppercase;",
            "      letter-spacing: 1px;",
            "      color: var(--accent-2);",
            "      padding-bottom: 8px;",
            "      border-bottom: 1px solid var(--border);",
            "    }",
            "    tbody td {",
            "      padding: 10px 6px;",
            "      border-bottom: 1px solid rgba(0, 0, 0, 0.06);",
            "      vertical-align: top;",
            "    }",
            "    tbody tr:last-child td {",
            "      border-bottom: none;",
            "    }",
            "    .stage {",
            "      font-weight: 600;",
            "      color: var(--accent);",
            "      text-transform: capitalize;",
            "    }",
            "    .count {",
            "      font-weight: 600;",
            "      width: 80px;",
            "    }",
            "    .prs {",
            "      color: var(--ink-muted);",
            "      word-break: break-word;",
            "    }",
            "  </style>",
            "</head>",
            "<body>",
            "  <header>",
            "    <h1>Agentbench Pipeline Status</h1>",
            f"    <div class=\"meta\">Last update: {snapshot['last_update']}</div>",
            f"    <div class=\"meta\">Started: {snapshot['started_at']}</div>",
            "  </header>",
            "  <div class=\"card\">",
            "    <table>",
            "      <thead>",
            "        <tr><th>Stage</th><th>Count</th><th>Active PRs</th></tr>",
            "      </thead>",
            "      <tbody>",
            *rows,
            "      </tbody>",
            "    </table>",
            "  </div>",
            "</body>",
            "</html>",
        ]
    )


class _PipelineStatusHandler(BaseHTTPRequestHandler):
    server_version = "AgentbenchPipelineStatus/0.1"

    def log_message(self, format: str, *args: object) -> None:
        return

    @property
    def _state(self) -> PipelineStatus:
        return self.server.state  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0].rstrip("/")
        if path in ("", "/"):
            body = _render_status_page(self._state.snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/status.json":
            payload = json.dumps(self._state.snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(404)
        self.end_headers()


def _start_status_server(
    state: PipelineStatus, host: str, port: int
) -> ThreadingHTTPServer | None:
    if port <= 0:
        return None
    try:
        server = ThreadingHTTPServer((host, port), _PipelineStatusHandler)
    except OSError as exc:
        logger.warning("Failed to start status server on %s:%s: %s", host, port, exc)
        return None

    server.state = state  # type: ignore[attr-defined]
    thread = threading.Thread(
        target=server.serve_forever,
        name="pipeline-status-server",
        daemon=True,
    )
    thread.start()
    logger.info("Status server running at http://%s:%s", host, port)
    return server


def _stop_status_server(server: ThreadingHTTPServer | None) -> None:
    if not server:
        return
    server.shutdown()
    server.server_close()


def _allocate_port() -> int:
    with _PORT_LOCK:
        return next(_PORT_COUNTER)


def _parse_timestamp(ts: str | None) -> float:
    if not ts:
        return float("-inf")
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("-inf")


def _existing_numbers(dir_path: Path) -> set[int]:
    if not dir_path.exists():
        return set()
    return {int(p.stem) for p in dir_path.glob("*.json")}


def _select_ready_prs(
    dir_path: Path, pr_numbers: Sequence[int], predicate: StageFilter | None
) -> list[int]:
    ready: list[int] = []
    for pr_number in pr_numbers:
        pr_path = dir_path / f"{pr_number}.json"
        if not pr_path.exists():
            logger.debug("No output for PR #%s in %s, skipping.", pr_number, dir_path)
            continue
        try:
            if predicate is None:
                ready.append(pr_number)
                continue

            with pr_path.open("r", encoding="utf-8") as f:
                pr_data = json.load(f)
            pr_instance = PullRequestInstance.from_dict(pr_data)
            if predicate(pr_instance):
                ready.append(pr_number)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load PR #%s from %s: %s", pr_number, pr_path, exc
            )
    return ready


def _load_pr_queue(
    pr_cache_dir: Path, exclude_numbers: set[int], limit: int
) -> list[int]:
    entries: list[tuple[int, float]] = []
    for pr_path in pr_cache_dir.glob("*.json"):
        try:
            with pr_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping cached PR %s: %s", pr_path, exc)
            continue

        try:
            pr_number = int(data.get("number") or pr_path.stem)
        except (TypeError, ValueError):
            logger.warning("Unable to read PR number from %s, skipping.", pr_path)
            continue

        if pr_number in exclude_numbers:
            continue

        ts = _parse_timestamp(data.get("updated_at") or data.get("created_at"))
        entries.append((pr_number, ts))

    entries.sort(key=lambda item: (item[1], item[0]), reverse=True)
    ordered = [number for number, _ in entries]

    if limit > 0:
        return ordered[:limit]
    return ordered


def _build_component_config(model_name: str, generator_name: str) -> dict:
    model_cfg = deepcopy(ALL_MODEL_CONFIGS[model_name])
    generator_cfg = deepcopy(ALL_GENERATOR_CONFIGS[generator_name])

    if "model_class" not in model_cfg:
        model_cfg["model_class"] = "litellm_server"

    return {"model": model_cfg, "generator": generator_cfg}


def _run_agent_stage(
    spec: AgentSpec,
    repo: str,
    docker_image: str,
    base_output: Path,
    pr_numbers: list[int],
    force: bool,
    model_port: int,
) -> list[int]:
    if not pr_numbers:
        return []

    try:
        run_agent_on_prs(
            config=spec.config,
            repo=repo,
            docker_image=docker_image,
            output=base_output,
            limit=-1,
            force=force,
            workers=spec.workers,
            agent_type=spec.agent_type,
            pr_numbers=pr_numbers,
            model_port=model_port,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Agent %s failed for PRs %s: %s", spec.agent_type, pr_numbers, exc
        )
        return []

    return _select_ready_prs(
        base_output / spec.output_dir_name,
        pr_numbers,
        spec.next_filter,
    )


def _run_filter_stage(
    config: dict,
    docker_image: str,
    base_output: Path,
    pr_numbers: list[int],
    workers: int,
    model_port: int,
) -> set[int]:
    if not pr_numbers:
        return set()

    input_dir = base_output / INSTANCES_DIR_NAME
    output_dir = base_output / FILTERED_INSTANCES_DIR_NAME
    before = _existing_numbers(output_dir)

    try:
        run_filter_instances(
            config=config,
            docker_image=docker_image,
            input_dir=input_dir,
            output_dir=output_dir,
            force=False,
            workers=workers,
            limit=-1,
            pr_numbers=pr_numbers,
            model_port=model_port,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Filtering failed for PRs %s: %s", pr_numbers, exc)
        return set()

    after = _existing_numbers(output_dir)
    return after - before


def main(
    repo: str | None = None,
    output: str = DEFAULT_OUTPUT_DIR,
    triage_model: str = "gpt-5-codex",
    triage_generator: str = "codex",
    statement_model: str = "gpt-5-codex",
    statement_generator: str = "codex",
    instance_model: str = "gpt-5-codex",
    instance_generator: str = "codex",
    filter_model: str = "gpt-5-codex",
    filter_generator: str = "codex",
    triage_workers: int = 8,
    setup_workers: int = 8,
    statement_workers: int = 8,
    instance_workers: int = 4,
    filter_workers: int = 4,
    parallel_instances: int = 8,
    target_instances: int = 10,
    limit: int = -1,
    refetch: bool = True,
    force_cache: bool = False,
    only_merged: bool = True,
    force_agents: bool = False,
    repo_config: str | None = None,
    docker_image: str | None = None,
    web_host: str = "127.0.0.1",
    web_port: int = 8000,
) -> None:
    config_entry = maybe_get_repo_config(repo_config or repo)
    if config_entry:
        repo = repo or config_entry.repo
        docker_image = docker_image or config_entry.docker_image
        if output == DEFAULT_OUTPUT_DIR or not output:
            output = config_entry.output_dir

    if not repo:
        raise ValueError("You must provide a repository via --repo or --repo-config.")
    if not docker_image:
        raise ValueError("You must provide --docker_image or configure one in repo_config.")

    if parallel_instances <= 0:
        parallel_instances = 1
    if target_instances <= 0:
        logger.info("Target instances set to %s, nothing to do.", target_instances)
        return

    base_output = Path(output) / repo.replace("/", "_")
    base_output.mkdir(parents=True, exist_ok=True)

    status = PipelineStatus(STAGE_ORDER)
    status_server = _start_status_server(status, web_host, web_port)

    try:
        logger.info("Building PR cache for %s.", repo)

        pr_cache_dir = base_output / PR_CACHE_DIR_NAME
        if pr_cache_dir.exists() and not force_cache:
            logger.info("PR cache directory %s already exists.", pr_cache_dir)
        else:
            logger.info("Creating PR cache directory %s.", pr_cache_dir)

            build_cache(
                repo=repo,
                output=output,
                limit=limit,
                force=force_cache,
                only_merged=only_merged,
                refetch=refetch,
                repo_config=repo_config,
            )

        
        if not pr_cache_dir.exists():
            logger.error("PR cache directory %s does not exist.", pr_cache_dir)
            return

        filtered_dir = base_output / FILTERED_INSTANCES_DIR_NAME
        existing_filtered = _existing_numbers(filtered_dir)
        if len(existing_filtered) >= target_instances:
            logger.info(
                "Found %d filtered instances for %s, target %d already met.",
                len(existing_filtered),
                repo,
                target_instances,
            )
            return

        queue = deque(_load_pr_queue(pr_cache_dir, existing_filtered, limit))
        if not queue:
            logger.warning("No PRs available in cache for %s.", repo)
            return

        agent_specs = [
            AgentSpec(
                agent_type="triage",
                config=_build_component_config(triage_model, triage_generator),
                workers=triage_workers,
                output_dir_name=TRIAGE_RESULTS_DIR_NAME,
                next_filter=setup_filter,
            ),
            AgentSpec(
                agent_type="setup",
                config=_build_component_config(triage_model, triage_generator),
                workers=setup_workers,
                output_dir_name=SETUP_RESULTS_DIR_NAME,
                next_filter=statement_filter,
            ),
            AgentSpec(
                agent_type="statement",
                config=_build_component_config(statement_model, statement_generator),
                workers=statement_workers,
                output_dir_name=STATEMENTS_DIR_NAME,
                next_filter=instance_filter,
            ),
            AgentSpec(
                agent_type="instance",
                config=_build_component_config(instance_model, instance_generator),
                workers=instance_workers,
                output_dir_name=INSTANCES_DIR_NAME,
            ),
        ]

        filter_config = _build_component_config(filter_model, filter_generator)

        success_count = len(existing_filtered)
        success_lock = threading.Lock()
        logger.info(
            "Starting pipeline for %s with %d existing instances and target %d.",
            repo,
            success_count,
            target_instances,
        )

        filtered_dir_refresher = lambda: len(_existing_numbers(filtered_dir))

        def process_single_pr(pr_number: int) -> int:
            if pr_number in _existing_numbers(filtered_dir):
                return 0

            pipeline_port = _allocate_port()
            candidates = [pr_number]

            for spec in agent_specs:
                if not force_agents:
                    ready = _select_ready_prs(
                        base_output / spec.output_dir_name, candidates, spec.next_filter
                    )
                    if pr_number in ready:
                        candidates = ready
                        continue

                status.mark_start(spec.agent_type, pr_number)
                try:
                    candidates = _run_agent_stage(
                        spec=spec,
                        repo=repo,
                        docker_image=docker_image,
                        base_output=base_output,
                        pr_numbers=candidates,
                        force=force_agents,
                        model_port=pipeline_port,
                    )
                finally:
                    status.mark_end(spec.agent_type, pr_number)
                if not candidates:
                    return 0

            status.mark_start("filtering", pr_number)
            try:
                accepted = _run_filter_stage(
                    config=filter_config,
                    docker_image=docker_image,
                    base_output=base_output,
                    pr_numbers=candidates,
                    workers=filter_workers,
                    model_port=pipeline_port,
                )
            finally:
                status.mark_end("filtering", pr_number)

            return len(accepted)

        in_progress: dict[concurrent.futures.Future[int], int] = {}
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=parallel_instances
        ) as executor:
            while (queue or in_progress) and success_count < target_instances:
                while (
                    queue
                    and len(in_progress) < parallel_instances
                    and success_count < target_instances
                ):
                    pr_number = queue.popleft()
                    future = executor.submit(process_single_pr, pr_number)
                    in_progress[future] = pr_number

                if not in_progress:
                    break

                done, _ = concurrent.futures.wait(
                    in_progress.keys(),
                    return_when=concurrent.futures.FIRST_COMPLETED,
                    timeout=1.0,
                )

                if not done:
                    continue

                for future in done:
                    pr_number = in_progress.pop(future)
                    try:
                        future.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Pipeline failed for PR #%s: %s", pr_number, exc)

                    with success_lock:
                        success_count = filtered_dir_refresher()

                    logger.info(
                        "Progress after PR #%s: %d/%d instances.",
                        pr_number,
                        success_count,
                        target_instances,
                    )

                    if success_count >= target_instances:
                        queue.clear()
                        break

        success_count = filtered_dir_refresher()
        if success_count >= target_instances:
            logger.info(
                "Reached target of %d instances (current: %d). Stopping.",
                target_instances,
                success_count,
            )
        else:
            logger.info(
                "Finished with %d/%d instances after exhausting the queue.",
                success_count,
                target_instances,
            )
    finally:
        _stop_status_server(status_server)


if __name__ == "__main__":
    fire.Fire(main)
