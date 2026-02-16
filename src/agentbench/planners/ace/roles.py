"""Generator, Reflector, and Curator components."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .delta import DeltaBatch


def safe_json_loads(text: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        debug_path = Path("logs/json_failures.log")
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        with debug_path.open("a", encoding="utf-8") as fh:
            fh.write("----\n")
            fh.write(repr(text))
            fh.write("\n")
        raise ValueError(f"LLM response is not valid JSON: {exc}\n{text}") from exc
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object from LLM.")
    return data


def _format_optional(value: Optional[str]) -> str:
    return value or "(none)"

@dataclass
class BulletTag:
    id: str
    tag: str


@dataclass
class ReflectorOutput:
    reasoning: str
    error_identification: str
    root_cause_analysis: str
    correct_approach: str
    key_insight: str
    bullet_tags: List[BulletTag]
    raw: Dict[str, Any]

@dataclass
class CuratorOutput:
    delta: DeltaBatch
    raw: Dict[str, Any]