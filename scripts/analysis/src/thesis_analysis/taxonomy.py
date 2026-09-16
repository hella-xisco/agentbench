"""Strict, two-axis normalization of experiment outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class UnknownOutcomeError(ValueError):
    """Raised when a raw status combination is not covered by the taxonomy."""


@dataclass(frozen=True)
class NormalizedOutcome:
    config_name: str
    model: str
    cell: str
    task: str
    repetition: str
    trajectory_path: str | None
    report_path: str | None
    exit_status: str | None
    evaluation_status: str
    evaluation_error: str | None
    resolved_present: bool
    resolved: bool | None
    model_responses: int | None
    tool_calls: int | None
    submission_present: bool | None
    category: str
    origin: str
    measurement_status: str
    measurable: bool
    outcome: int | None
    tokens: float | None
    api_calls: float | None
    wall_seconds: float | None


def normalize_outcome(raw: dict[str, Any]) -> NormalizedOutcome:
    """Map one planned run to category, origin and measurement status.

    Missing files remain explicit rows. Unknown exit states or internally
    inconsistent successful evaluations abort instead of being guessed.
    """
    if raw.get("evaluation_error"):
        evaluation_status = "error"
    elif raw.get("report_path") and raw.get("resolved_present"):
        evaluation_status = "completed"
    else:
        evaluation_status = "missing"
    common = {
        "config_name": raw["config_name"],
        "model": raw["model"],
        "cell": raw["cell"],
        "task": raw["task"],
        "repetition": raw["repetition"],
        "trajectory_path": raw.get("trajectory_path"),
        "report_path": raw.get("report_path"),
        "exit_status": raw.get("exit_status"),
        "evaluation_status": evaluation_status,
        "evaluation_error": None if not raw.get("evaluation_error") else str(raw.get("evaluation_error")),
        "resolved_present": bool(raw.get("resolved_present", False)),
        "resolved": raw.get("resolved") if raw.get("resolved_present") else None,
        "model_responses": raw.get("model_responses"),
        "tool_calls": raw.get("tool_calls"),
        "submission_present": bool(raw.get("submission")) if "submission" in raw else None,
        "tokens": raw.get("tokens"),
        "api_calls": raw.get("api_calls"),
        "wall_seconds": raw.get("wall_seconds"),
    }

    def make(category: str, origin: str, measurable: bool, outcome: int | None) -> NormalizedOutcome:
        return NormalizedOutcome(
            **common,
            category=category,
            origin=origin,
            measurement_status="measurable" if measurable else "not_measurable",
            measurable=measurable,
            outcome=outcome,
        )

    if not raw.get("trajectory_path"):
        return make("missing_artifact", "measurement_pipeline", False, None)
    if raw.get("evaluation_error"):
        return make("evaluation_error", "measurement_pipeline", False, None)

    exit_status = raw.get("exit_status")
    responses = int(raw.get("model_responses") or 0)
    if exit_status == "APIError" or (exit_status == "ExecutionFailed" and responses == 0):
        return make("serving_error", "measurement_pipeline", False, None)
    if exit_status == "ExecutionFailed" and responses > 0:
        return make("timeout", "agent", True, 0)
    if exit_status != "Submitted":
        raise UnknownOutcomeError(
            f"Unknown exit status {exit_status!r} for {raw['cell']}/{raw['task']}/{raw['repetition']}"
        )
    if not raw.get("report_path") or not raw.get("resolved_present"):
        return make("missing_artifact", "measurement_pipeline", False, None)
    if not isinstance(raw.get("resolved"), bool):
        raise UnknownOutcomeError(
            f"Non-boolean resolved status for {raw['cell']}/{raw['task']}/{raw['repetition']}"
        )
    if raw["resolved"]:
        return make("solved", "agent", True, 1)
    if int(raw.get("tool_calls") or 0) == 0:
        return make("no_action", "agent", True, 0)
    if not raw.get("submission"):
        return make("empty_patch", "agent", True, 0)
    return make("failed_patch", "agent", True, 0)


TAXONOMY_ROWS = [
    {"category": "solved", "origin": "agent", "measurement_status": "measurable", "outcome": 1,
     "definition": "Evaluation completed and resolved=true."},
    {"category": "failed_patch", "origin": "agent", "measurement_status": "measurable", "outcome": 0,
     "definition": "A non-empty patch was submitted but did not solve the task."},
    {"category": "empty_patch", "origin": "agent", "measurement_status": "measurable", "outcome": 0,
     "definition": "The agent used tools but submitted no patch."},
    {"category": "no_action", "origin": "agent", "measurement_status": "measurable", "outcome": 0,
     "definition": "The run completed without an agent tool call."},
    {"category": "timeout", "origin": "agent", "measurement_status": "measurable", "outcome": 0,
     "definition": "ExecutionFailed after at least one model response; a time-budget failure."},
    {"category": "evaluation_error", "origin": "measurement_pipeline", "measurement_status": "not_measurable", "outcome": "",
     "definition": "The evaluation pipeline reported an evaluation error."},
    {"category": "serving_error", "origin": "measurement_pipeline", "measurement_status": "not_measurable", "outcome": "",
     "definition": "The model-serving/API layer failed before a measurable agent run."},
    {"category": "missing_artifact", "origin": "measurement_pipeline", "measurement_status": "not_measurable", "outcome": "",
     "definition": "A planned trajectory or required evaluation artefact is missing."},
]
