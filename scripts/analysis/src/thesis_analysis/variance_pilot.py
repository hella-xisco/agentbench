"""CLI for the GLM and Qwen variance-pilot audit."""

from __future__ import annotations

import argparse
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from .io import load_config, load_matrix, outcome_rows, write_csv, write_json
from .stats import pilot_matrix_statistics
from .taxonomy import TAXONOMY_ROWS


def analyze(config: dict[str, Any]) -> dict[str, Any]:
    outcomes, tasks = load_matrix(config)
    expected_total = len(tasks) * len(config["cells"]) * len(config["repetitions"])
    if len(outcomes) != expected_total:
        raise RuntimeError(f"Internal matrix error: {len(outcomes)} rows, expected {expected_total}")
    nonmeasurable = [row for row in outcomes if not row.measurable]
    if nonmeasurable:
        preview = ", ".join(f"{r.task}/{r.repetition}:{r.category}" for r in nonmeasurable[:5])
        raise RuntimeError(f"Pilot matrix contains {len(nonmeasurable)} non-measurable runs: {preview}")

    by_key = {(row.task, row.repetition): row for row in outcomes}
    repetitions = list(config["repetitions"])
    first_ten = repetitions[:10]
    all_twenty = repetitions[:20]
    if len(tasks) != 10 or len(repetitions) != 20:
        raise RuntimeError("Variance-pilot analysis requires an explicit 10×20 matrix")

    matrix_20 = [
        [int(by_key[(task, rep)].outcome) for rep in all_twenty]
        for task in tasks
    ]
    pilot_stats = pilot_matrix_statistics(matrix_20)
    task_rows: list[dict[str, Any]] = []
    for task in tasks:
        values_10 = [int(by_key[(task, rep)].outcome) for rep in first_ten]
        values_20 = [int(by_key[(task, rep)].outcome) for rep in all_twenty]
        variance = statistics.variance(values_20)
        task_rows.append({
            "task": task,
            "solved_first_10": sum(values_10),
            "pass_at_1_first_10": statistics.fmean(values_10),
            "solved_all_20": sum(values_20),
            "pass_at_1_all_20": statistics.fmean(values_20),
            "within_task_sample_variance": variance,
        })

    round_rows = []
    round_counts = []
    for index, repetition in enumerate(repetitions):
        solved = sum(int(by_key[(task, repetition)].outcome) for task in tasks)
        round_counts.append(solved)
        engine = next(
            (item for item in config.get("engine_allocation", []) if repetition in item["repetitions"]),
            {},
        )
        round_rows.append({
            "round_index": index,
            "repetition": repetition,
            "solved_task_count": solved,
            "engine": engine.get("engine", ""),
            "port": engine.get("port", ""),
        })

    categories = Counter(row.category for row in outcomes)
    wall_seconds = np.asarray(
        [float(row.wall_seconds) for row in outcomes if row.wall_seconds is not None],
        dtype=float,
    )
    summary = {
        "analysis": "variance_pilot",
        "config_name": config["name"],
        "model": config["model"],
        "planning_role": config["planning_role"],
        "task_count": len(tasks),
        "repetition_count": len(repetitions),
        "planned_runs": len(outcomes),
        "measurable_runs": sum(row.measurable for row in outcomes),
        "category_counts": dict(sorted(categories.items())),
        "timeout_seconds": config["timeout_seconds"],
        "engine_allocation": config.get("engine_allocation", []),
        "pass_at_1_first_10": statistics.fmean(int(by_key[(t, r)].outcome) for t in tasks for r in first_ten),
        "pass_at_1_all_20": statistics.fmean(int(by_key[(t, r)].outcome) for t in tasks for r in all_twenty),
        "round_count_sample_sd": pilot_stats["round_count_sample_sd"],
        "mean_within_task_sample_variance": pilot_stats["mean_within_task_sample_variance"],
        "planning_proxy": config["planning_proxy"],
        "wall_seconds": {
            "count": int(wall_seconds.size),
            "median": float(np.median(wall_seconds)),
            "p95": float(np.percentile(wall_seconds, 95)),
            "maximum": float(np.max(wall_seconds)),
        },
    }

    design_rows: list[dict[str, Any]] = []
    if config["planning_role"] == "initial_main_run_repetition_choice":
        proxy = float(config["planning_proxy"])
        for n_tasks in config["design_task_counts"]:
            for repetitions_per_cell in config["design_repetitions"]:
                se = math.sqrt(2 * proxy / (n_tasks * repetitions_per_cell))
                half_width = float(stats.t.ppf(0.975, n_tasks - 1)) * se
                runs = config["design_cells"] * n_tasks * repetitions_per_cell
                design_rows.append({
                    "n_tasks": n_tasks,
                    "repetitions_per_cell": repetitions_per_cell,
                    "cells": config["design_cells"],
                    "planned_runs": runs,
                    "estimated_hours": runs * config["minutes_per_run"] / 60,
                    "planning_standard_error": se,
                    "nominal_t_95_half_width": half_width,
                    "degrees_freedom": n_tasks - 1,
                })
    return {
        "summary": summary,
        "task_rows": task_rows,
        "round_rows": round_rows,
        "design_rows": design_rows,
        "outcomes": outcomes,
    }


def validate_expected(config: dict[str, Any], result: dict[str, Any]) -> None:
    expected = config.get("expected", {})
    actual = result["summary"]
    checks = {
        "planned_runs": actual["planned_runs"],
        "measurable_runs": actual["measurable_runs"],
        "timeouts": actual["category_counts"].get("timeout", 0),
    }
    for key, wanted in expected.items():
        if key in checks and checks[key] != wanted:
            raise RuntimeError(f"Audit expectation failed for {key}: got {checks[key]}, expected {wanted}")
    if config["planning_role"] == "initial_main_run_repetition_choice":
        row = next(r for r in result["design_rows"] if r["n_tasks"] == 71 and r["repetitions_per_cell"] == 2)
        if not math.isclose(row["planning_standard_error"], 0.0409, abs_tol=0.00006):
            raise RuntimeError(f"Planning SE regression: {row['planning_standard_error']}")
        if not math.isclose(row["nominal_t_95_half_width"], 0.0815, abs_tol=0.00006):
            raise RuntimeError(f"Planning half-width regression: {row['nominal_t_95_half_width']}")


def write_outputs(output_dir: Path, result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "summary.json", result["summary"])
    write_csv(output_dir / "task_estimates.csv", result["task_rows"])
    write_csv(output_dir / "round_counts.csv", result["round_rows"])
    write_csv(
        output_dir / "design_precision.csv",
        result["design_rows"],
        ["n_tasks", "repetitions_per_cell", "cells", "planned_runs", "estimated_hours",
         "planning_standard_error", "nominal_t_95_half_width", "degrees_freedom"],
    )
    write_csv(output_dir / "outcome_taxonomy.csv", TAXONOMY_ROWS)
    write_csv(output_dir / "raw_status_mapping.csv", outcome_rows(result["outcomes"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if config.get("analysis_type") != "variance_pilot":
        parser.error("configuration is not a variance_pilot configuration")
    result = analyze(config)
    validate_expected(config, result)
    write_outputs(args.output_dir, result)
    print(f"Variance-pilot audit written to {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
