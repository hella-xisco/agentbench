"""Trajectory behaviour summaries used by the thesis reporting layer."""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any


PHASES = ("explore", "edit", "validate", "other")
SKILL_PATH_RE = re.compile(r"(\.pi|\.claude|\.agents)/skills/[^\s\"']*SKILL\.md|/skills/[^\s\"']+/SKILL\.md")
VALIDATE_RE = re.compile(
    r"\b(pytest|py\.test|unittest|tox|make (?:test|check|lint|fixup)|ansible-test|"
    r"mypy|ruff|pylint|flake8|pre-commit|prek|pdm run (?:test|lint)|"
    r"uv run (?:pytest|ty|ruff|prek)|npm test|cargo test|go test)\b"
)
EXPLORE_RE = re.compile(
    r"^\s*(cat|ls|grep|rg|find|head|tail|wc|tree|git (?:log|show|diff|status|grep)|pwd|which|stat)\b"
)
SETUP_RE = re.compile(r"\b(pip3? install|uv sync|uv pip|npm install|apt-get|conda install)\b")
CMD_PREFIX_RE = re.compile(r"^\s*(?:(?:cd\s+\S+\s*&&\s*)|(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+))+" )


def classify_call(name: str | None, arguments: str) -> str:
    if name == "read":
        return "explore"
    if name in {"edit", "write"}:
        return "edit"
    if name != "bash":
        return "other"
    try:
        command = json.loads(arguments or "{}").get("command", "")
    except json.JSONDecodeError:
        command = arguments or ""
    command = CMD_PREFIX_RE.sub("", command or "")
    if VALIDATE_RE.search(command) or re.search(r"\bpython3?\b", command):
        return "validate"
    if EXPLORE_RE.search(command):
        return "explore"
    if SETUP_RE.search(command):
        return "other"
    return "other"


def read_trajectory(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        trajectory = json.load(handle)
    calls: list[tuple[str, str | None, str]] = []
    for message in trajectory.get("messages", []) or []:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        for tool_call in message.get("tool_calls", []) or []:
            function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
            name = function.get("name")
            arguments = function.get("arguments") or ""
            calls.append((classify_call(name, arguments), name, arguments))
    phases = Counter(phase for phase, _, _ in calls)
    skill_reads = sum(bool(SKILL_PATH_RE.search(arguments)) for _, _, arguments in calls)
    loop = any(
        left[1:] == middle[1:] == right[1:]
        for left, middle, right in zip(calls, calls[1:], calls[2:])
    )
    return {
        "calls": len(calls),
        "phases": {phase: phases[phase] for phase in PHASES},
        "skill_reads": skill_reads,
        "loop": loop,
    }


def summarize_behaviour(
    raw_rows: list[dict[str, str]],
    cell_labels: dict[str, str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, int]]]:
    acting: dict[str, list[dict[str, Any]]] = {label: [] for label in cell_labels.values()}
    loops: list[dict[str, Any]] = []
    activation = {label: {"offered": 0, "activated": 0, "read_and_quit": 0} for label in cell_labels.values()}
    category_counts = {label: Counter() for label in cell_labels.values()}
    for row in raw_rows:
        label = cell_labels[row["cell"]]
        category_counts[label][row["category"]] += 1
        path = Path(row["trajectory_path"])
        if not path.is_file():
            raise ValueError(f"Trajectory required for behaviour reporting is missing: {path}")
        record = read_trajectory(path)
        if label.endswith("s"):
            activation[label]["offered"] += 1
            if record["skill_reads"]:
                activation[label]["activated"] += 1
                if row["category"] == "empty_patch" and record["calls"] <= 3:
                    activation[label]["read_and_quit"] += 1
        if row["measurement_status"] != "measurable" or record["calls"] == 0:
            continue
        record["wall_seconds"] = float(row["wall_seconds"])
        record["task"] = row["task"]
        record["repetition"] = row["repetition"]
        record["outcome"] = row["category"]
        acting[label].append(record)
        if record["loop"]:
            loops.append({"cell": label, **record})
    summaries: dict[str, dict[str, Any]] = {}
    for label, records in acting.items():
        summaries[label] = {
            "acting_runs": len(records),
            "phase_means": {
                phase: statistics.mean(record["phases"][phase] for record in records)
                for phase in PHASES
            },
            "total_mean": statistics.mean(record["calls"] for record in records),
            "wall_mean_seconds": statistics.mean(record["wall_seconds"] for record in records),
            "loops": sum(record["loop"] for record in records),
            "no_action": category_counts[label]["no_action"],
            "timeout": category_counts[label]["timeout"],
            "skill_activation_acting": (
                sum(bool(record["skill_reads"]) for record in records) / len(records)
                if label.endswith("s") and records else None
            ),
        }
    return summaries, loops, activation
