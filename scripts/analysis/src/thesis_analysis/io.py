"""Configuration, manifest and raw experiment I/O."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from .taxonomy import NormalizedOutcome, normalize_outcome


REPO_ROOT = Path(__file__).resolve().parents[4]


class AnalysisInputError(RuntimeError):
    """Raised when the configured analysis matrix is incomplete or ambiguous."""


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    config["_config_path"] = str(config_path)
    return config


def read_manifest(path: str | Path) -> list[str]:
    manifest = resolve_repo_path(path)
    tasks = [
        line.strip()
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not tasks:
        raise AnalysisInputError(f"Task manifest is empty: {manifest}")
    if len(tasks) != len(set(tasks)):
        raise AnalysisInputError(f"Task manifest contains duplicates: {manifest}")
    return tasks


def _tool_call_count(messages: list[Any]) -> int:
    count = 0
    for message in messages:
        if isinstance(message, dict) and message.get("role") == "assistant":
            count += len(message.get("tool_calls") or [])
    return count


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _trajectory_record(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    info = data.get("info") or {}
    responses = data.get("responses") or []
    tokens = sum(
        ((response or {}).get("usage") or {}).get("total_tokens") or 0
        for response in responses
    )
    return {
        "trajectory_path": _display_path(path),
        "exit_status": info.get("exit_status"),
        "submission": (info.get("submission") or "").strip(),
        "model_responses": len(responses),
        "tool_calls": _tool_call_count(data.get("messages") or []),
        "api_calls": (info.get("model_stats") or {}).get("api_calls", 0),
        "wall_seconds": info.get("wall_time_seconds"),
        "tokens": tokens,
    }


def _report_record(path: Path, task: str) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        report = json.load(handle)
    if task in report:
        entry = report[task]
    elif len(report) == 1:
        entry = next(iter(report.values()))
    else:
        raise AnalysisInputError(f"Cannot identify task {task!r} in {path}")
    if not isinstance(entry, dict):
        raise AnalysisInputError(f"Malformed report entry in {path}")
    return {
        "report_path": _display_path(path),
        "resolved_present": "resolved" in entry,
        "resolved": entry.get("resolved"),
        "evaluation_error": entry.get("evaluation_error") or entry.get("eval_error"),
    }


def _selected_files(root: Path, kind: str, cells: list[str], repetitions: list[str]) -> Iterable[Path]:
    pattern = "*.traj.json" if kind == "trajectory" else "report.json"
    base = root / ("agentbench" if kind == "trajectory" else "swebench")
    if not base.exists():
        return []
    selected: list[Path] = []
    cell_set, repetition_set = set(cells), set(repetitions)
    for path in base.rglob(pattern):
        parts = set(path.parts)
        if parts.intersection(cell_set) and parts.intersection(repetition_set):
            selected.append(path)
    return selected


def _key_from_path(path: Path, cells: list[str], repetitions: list[str]) -> tuple[str, str, str]:
    matches_cell = [cell for cell in cells if cell in path.parts]
    matches_rep = [rep for rep in repetitions if rep in path.parts]
    if len(matches_cell) != 1 or len(matches_rep) != 1:
        raise AnalysisInputError(f"Ambiguous configured cell/repetition in path: {path}")
    task = path.parent.name
    return matches_cell[0], task, matches_rep[0]


def load_matrix(config: dict[str, Any]) -> tuple[list[NormalizedOutcome], list[str]]:
    """Load every manifest×cell×repetition row, including missing artefacts."""
    root = resolve_repo_path(config["run_directory"])
    tasks = read_manifest(config["task_manifest"])
    cells = list(config["cells"])
    repetitions = list(config["repetitions"])
    expected_tasks = set(tasks)

    trajectories: dict[tuple[str, str, str], Path] = {}
    reports: dict[tuple[str, str, str], Path] = {}
    extras: list[tuple[str, str, str, str]] = []

    for kind, target in (("trajectory", trajectories), ("report", reports)):
        for path in _selected_files(root, kind, cells, repetitions):
            key = _key_from_path(path, cells, repetitions)
            cell, task, repetition = key
            if task not in expected_tasks:
                extras.append((kind, cell, task, repetition))
                continue
            if key in target:
                raise AnalysisInputError(
                    f"Duplicate {kind} for cell={cell}, task={task}, repetition={repetition}: "
                    f"{target[key]} and {path}"
                )
            target[key] = path

    if extras:
        preview = ", ".join("/".join(item) for item in extras[:5])
        raise AnalysisInputError(f"Additional task-run combinations found ({len(extras)}): {preview}")

    expected_keys = {
        (cell, task, repetition)
        for cell in cells
        for task in tasks
        for repetition in repetitions
    }
    missing_trajectories = sorted(expected_keys - set(trajectories))
    if missing_trajectories:
        preview = ", ".join("/".join(item) for item in missing_trajectories[:5])
        raise AnalysisInputError(
            f"Missing planned trajectory combinations ({len(missing_trajectories)}): {preview}"
        )

    outcomes: list[NormalizedOutcome] = []
    for cell in cells:
        for task in tasks:
            for repetition in repetitions:
                key = (cell, task, repetition)
                raw: dict[str, Any] = {
                    "config_name": config["name"],
                    "model": config["model"]["name"],
                    "cell": cell,
                    "task": task,
                    "repetition": repetition,
                }
                if key in trajectories:
                    raw.update(_trajectory_record(trajectories[key]))
                if key in reports:
                    raw.update(_report_record(reports[key], task))
                outcomes.append(normalize_outcome(raw))
    return outcomes, tasks


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def outcome_rows(outcomes: list[NormalizedOutcome]) -> list[dict[str, Any]]:
    return [asdict(outcome) for outcome in outcomes]
