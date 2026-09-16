"""CLI for complete-case main-run contrasts and effort bootstrap intervals."""

from __future__ import annotations

import argparse
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .io import load_config, load_matrix, outcome_rows, write_csv, write_json
from .stats import bootstrap_effort, holm_adjust, paired_t_summary
from .taxonomy import NormalizedOutcome, TAXONOMY_ROWS


CELL_LABELS = {
    "no_plan": "K0",
    "curated_k0d": "K0d",
    "curated_k1": "K1",
    "curated_k1s": "K1s",
    "curated_k2": "K2",
    "curated_k2s": "K2s",
}

CONTRASTS = [
    {"id": "K1-K0", "cell_a": "curated_k1", "cell_b": "no_plan", "family": "RQ1"},
    {"id": "K2-K0", "cell_a": "curated_k2", "cell_b": "no_plan", "family": "RQ1"},
    {"id": "K1s-K1", "cell_a": "curated_k1s", "cell_b": "curated_k1", "family": "RQ2"},
    {"id": "K2s-K2", "cell_a": "curated_k2s", "cell_b": "curated_k2", "family": "RQ2"},
    {"id": "K0d-K0", "cell_a": "curated_k0d", "cell_b": "no_plan", "family": "RQ3"},
    {"id": "K1-K0d", "cell_a": "curated_k1", "cell_b": "curated_k0d", "family": "RQ3"},
    {"id": "K2-K0d", "cell_a": "curated_k2", "cell_b": "curated_k0d", "family": "RQ3"},
]

PROCEDURAL_CONTRASTS = {"K1-K0", "K1s-K1"}
EFFORT_METRICS = ("tokens", "api_calls", "wall_seconds")


def _index(outcomes: list[NormalizedOutcome]) -> dict[tuple[str, str, str], NormalizedOutcome]:
    return {(row.cell, row.task, row.repetition): row for row in outcomes}


def _required_rows(
    indexed: dict[tuple[str, str, str], NormalizedOutcome],
    task: str,
    contrast: dict[str, str],
    repetitions: list[str],
) -> list[NormalizedOutcome]:
    return [
        indexed[(cell, task, repetition)]
        for cell in (contrast["cell_a"], contrast["cell_b"])
        for repetition in repetitions
    ]


def _complete_contrast_sets(
    outcomes: list[NormalizedOutcome],
    tasks: list[str],
    repetitions: list[str],
) -> tuple[dict[str, list[str]], list[dict[str, Any]], list[dict[str, Any]]]:
    indexed = _index(outcomes)
    complete: dict[str, list[str]] = {}
    sizes: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for contrast in CONTRASTS:
        included: list[str] = []
        excluded_tasks = 0
        excluded_runs = 0
        for task in tasks:
            required = _required_rows(indexed, task, contrast, repetitions)
            failures = [row for row in required if not row.measurable]
            if failures:
                excluded_tasks += 1
                excluded_runs += len(failures)
                exclusions.append({
                    "contrast": contrast["id"],
                    "family": contrast["family"],
                    "task": task,
                    "nonmeasurable_run_count": len(failures),
                    "nonmeasurable_requirements": ";".join(
                        f"{CELL_LABELS[row.cell]}/{row.repetition}/{row.category}"
                        for row in failures
                    ),
                    "categories": ";".join(sorted({row.category for row in failures})),
                    "origins": ";".join(sorted({row.origin for row in failures})),
                })
            else:
                included.append(task)
        complete[contrast["id"]] = included
        sizes.append({
            "contrast": contrast["id"],
            "family": contrast["family"],
            "cell_a": CELL_LABELS[contrast["cell_a"]],
            "cell_b": CELL_LABELS[contrast["cell_b"]],
            "planned_tasks": len(tasks),
            "included_tasks": len(included),
            "excluded_tasks": excluded_tasks,
            "nonmeasurable_required_runs": excluded_runs,
        })
    return complete, sizes, exclusions


def _cell_summaries(outcomes: list[NormalizedOutcome], cells: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        selected = [row for row in outcomes if row.cell == cell]
        measurable = [row for row in selected if row.measurable]
        solved = sum(int(row.outcome) for row in measurable)
        summary: dict[str, Any] = {
            "cell": cell,
            "cell_label": CELL_LABELS[cell],
            "planned_runs": len(selected),
            "measurable_runs": len(measurable),
            "solved_runs": solved,
            "pass_at_1": solved / len(measurable) if measurable else None,
        }
        for metric in EFFORT_METRICS:
            values = [getattr(row, metric) for row in measurable]
            if any(value is None or not math.isfinite(float(value)) or float(value) < 0 for value in values):
                raise RuntimeError(f"Missing effort measure {metric} in measurable cell {cell}")
            total = sum(float(value) for value in values)
            summary[f"total_{metric}"] = total
            summary[f"mean_{metric}_per_measurable_run"] = (
                total / len(measurable) if measurable else None
            )
        rows.append(summary)
    return rows


def _task_contrast_rows(
    indexed: dict[tuple[str, str, str], NormalizedOutcome],
    tasks: list[str],
    contrast: dict[str, str],
    repetitions: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        a = [indexed[(contrast["cell_a"], task, repetition)] for repetition in repetitions]
        b = [indexed[(contrast["cell_b"], task, repetition)] for repetition in repetitions]
        p_a = statistics.fmean(int(row.outcome) for row in a)
        p_b = statistics.fmean(int(row.outcome) for row in b)
        result: dict[str, Any] = {
            "task": task,
            "pass_at_1_a": p_a,
            "pass_at_1_b": p_b,
            "delta": p_a - p_b,
            "solved_a": sum(int(row.outcome) for row in a),
            "solved_b": sum(int(row.outcome) for row in b),
        }
        for metric in EFFORT_METRICS:
            values_a = [getattr(row, metric) for row in a]
            values_b = [getattr(row, metric) for row in b]
            if any(value is None or not math.isfinite(float(value)) or float(value) < 0 for value in values_a + values_b):
                raise RuntimeError(f"Missing effort measure {metric} in complete task {task}, {contrast['id']}")
            result[f"{metric}_a"] = sum(float(value) for value in values_a)
            result[f"{metric}_b"] = sum(float(value) for value in values_b)
        rows.append(result)
    return rows


def _pairwise_disagreement(
    indexed: dict[tuple[str, str, str], NormalizedOutcome],
    tasks: list[str],
    cells: list[str],
    repetitions: list[str],
) -> list[dict[str, Any]]:
    if len(repetitions) != 2:
        raise RuntimeError("Pairwise disagreement is defined here for exactly two repetitions")
    result = []
    for cell in cells:
        eligible = 0
        disagreements = 0
        for task in tasks:
            pair = [indexed[(cell, task, repetition)] for repetition in repetitions]
            if all(row.measurable for row in pair):
                eligible += 1
                disagreements += pair[0].outcome != pair[1].outcome
        result.append({
            "cell": cell,
            "cell_label": CELL_LABELS[cell],
            "tasks_with_two_measurable_repetitions": eligible,
            "disagreeing_tasks": disagreements,
            "pairwise_disagreement_probability": disagreements / eligible if eligible else None,
        })
    return result


def analyze(config: dict[str, Any], audit_only: bool = False) -> dict[str, Any]:
    outcomes, tasks = load_matrix(config)
    indexed = _index(outcomes)
    repetitions = list(config["repetitions"])
    if len(repetitions) != 2:
        raise RuntimeError("The main-run 2+2 analysis requires exactly two repetitions per cell")
    complete, sample_sizes, exclusions = _complete_contrast_sets(outcomes, tasks, repetitions)
    categories = Counter(row.category for row in outcomes)
    base = {
        "analysis": "main_run",
        "analysis_version": 3,
        "effort_estimator": "mean_effort_per_measurable_run",
        "config_name": config["name"],
        "model": config["model"],
        "audit_only": audit_only,
        "task_count": len(tasks),
        "cell_count": len(config["cells"]),
        "repetitions_per_cell": len(repetitions),
        "planned_runs": len(outcomes),
        "category_counts": dict(sorted(categories.items())),
        "measurement_counts": dict(sorted(Counter(row.measurement_status for row in outcomes).items())),
        "cell_summaries": _cell_summaries(outcomes, config["cells"]),
    }
    result: dict[str, Any] = {
        "summary": base,
        "outcomes": outcomes,
        "sample_sizes": sample_sizes,
        "exclusions": exclusions,
        "contrast_results": [],
        "contrast_json": {"summary": base, "contrasts": []},
        "effort": {"config_name": config["name"], "contrasts": []},
        "disagreement": [],
        "sensitivity": [],
    }
    if audit_only:
        return result

    contrast_results: list[dict[str, Any]] = []
    detailed: list[dict[str, Any]] = []
    effort_results: list[dict[str, Any]] = []
    per_family: dict[str, list[int]] = defaultdict(list)
    for contrast in CONTRASTS:
        task_rows = _task_contrast_rows(indexed, complete[contrast["id"]], contrast, repetitions)
        t_result = paired_t_summary([row["delta"] for row in task_rows])
        aggregate = {
            "contrast": contrast["id"],
            "family": contrast["family"],
            "cell_a": CELL_LABELS[contrast["cell_a"]],
            "cell_b": CELL_LABELS[contrast["cell_b"]],
            **t_result,
        }
        per_family[contrast["family"]].append(len(contrast_results))
        contrast_results.append(aggregate)
        detailed.append({**aggregate, "task_estimates": task_rows})
        boot = bootstrap_effort(
            task_rows,
            repetitions=int(config.get("bootstrap_repetitions", 10_000)),
            seed=int(config.get("bootstrap_seed", 42)),
            runs_per_task=len(repetitions),
        )
        effort_results.append({
            "contrast": contrast["id"],
            "family": contrast["family"],
            "cell_a": CELL_LABELS[contrast["cell_a"]],
            "cell_b": CELL_LABELS[contrast["cell_b"]],
            "n_tasks": len(task_rows),
            **boot,
        })

    for family, indices in per_family.items():
        adjusted = holm_adjust([float(contrast_results[index]["p_value"]) for index in indices])
        for index, p_holm in zip(indices, adjusted):
            contrast_results[index]["p_value_holm"] = p_holm
            contrast_results[index]["holm_reject_alpha_0_05"] = p_holm < 0.05
            detailed[index]["p_value_holm"] = p_holm
            detailed[index]["holm_reject_alpha_0_05"] = p_holm < 0.05

    prefixes = tuple(config.get("delivered_only_exclude_prefixes", []))
    sensitivity: list[dict[str, Any]] = []
    for contrast in CONTRASTS:
        if contrast["id"] not in PROCEDURAL_CONTRASTS:
            continue
        delivered = [task for task in complete[contrast["id"]] if not task.startswith(prefixes)]
        task_rows = _task_contrast_rows(indexed, delivered, contrast, repetitions)
        t_result = paired_t_summary([row["delta"] for row in task_rows])
        sensitivity.append({
            "contrast": contrast["id"],
            "family": contrast["family"],
            "filter": "delivered-only",
            "excluded_prefixes": ";".join(prefixes),
            "n_tasks": t_result["n_tasks"],
            "effect": t_result["effect"],
            "sd_delta": t_result["sd_delta"],
            "standard_error": t_result["standard_error"],
            "degrees_freedom": t_result["degrees_freedom"],
            "ci_low": t_result["ci_low"],
            "ci_high": t_result["ci_high"],
        })

    result["contrast_results"] = contrast_results
    result["contrast_json"] = {"summary": base, "contrasts": detailed}
    result["effort"] = {
        "analysis_version": 3,
        "estimator": "mean_effort_per_measurable_run",
        "config_name": config["name"],
        "bootstrap_unit": "task",
        "confidence_interval": "percentile_95",
        "contrasts": effort_results,
    }
    result["disagreement"] = _pairwise_disagreement(indexed, tasks, config["cells"], repetitions)
    result["sensitivity"] = sensitivity
    return result


def validate_expected(config: dict[str, Any], result: dict[str, Any]) -> None:
    expected = config.get("expected", {})
    counts = result["summary"]["category_counts"]
    checks = {
        "planned_runs": result["summary"]["planned_runs"],
        "evaluation_errors": counts.get("evaluation_error", 0),
        "timeouts": counts.get("timeout", 0),
        "contrast_sample_sizes": [row["included_tasks"] for row in result["sample_sizes"]],
    }
    for key, wanted in expected.items():
        if key in checks and checks[key] != wanted:
            raise RuntimeError(f"Audit expectation failed for {key}: got {checks[key]}, expected {wanted}")


def _report_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"# Statistical audit: {summary['config_name']}",
        "",
        "This report records computed audit results. It does not formulate or revise research-question conclusions.",
        "",
        "## Raw audit",
        "",
        f"- Planned runs: {summary['planned_runs']}",
        f"- Tasks: {summary['task_count']}",
        f"- Measurement counts: {summary['measurement_counts']}",
        f"- Outcome categories: {summary['category_counts']}",
        "",
        "## Complete 2+2 samples",
        "",
        "| Contrast | Included | Excluded |",
        "|---|---:|---:|",
    ]
    lines.extend(
        f"| {row['contrast']} | {row['included_tasks']} | {row['excluded_tasks']} |"
        for row in result["sample_sizes"]
    )
    lines.extend(["", "## Observed cell rates", "", "| Cell | S/M | pass@1 |", "|---|---:|---:|"])
    for row in summary["cell_summaries"]:
        rate = "NA" if row["pass_at_1"] is None else f"{row['pass_at_1']:.6f}"
        lines.append(f"| {row['cell_label']} | {row['solved_runs']}/{row['measurable_runs']} | {rate} |")
    if summary["audit_only"]:
        lines.extend(["", "Inferential and bootstrap calculations were skipped by `--audit-only`."])
    else:
        lines.extend([
            "", "## Paired pass@1 contrasts", "",
            "| Contrast | Tasks | Effect | 95% t CI | p | Holm p |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for row in result["contrast_results"]:
            lines.append(
                f"| {row['contrast']} | {row['n_tasks']} | {row['effect']:.6f} | "
                f"[{row['ci_low']:.6f}, {row['ci_high']:.6f}] | {row['p_value']:.6g} | "
                f"{row['p_value_holm']:.6g} |"
            )
        lines.extend([
            "", "## Mean effort per measurable attempt", "",
            "The same complete task set is used as for each solve-rate contrast. Failed attempts and timeouts contribute effort. "
            "Intervals are paired task-bootstrap percentile intervals, not Holm decisions or effort hypothesis tests.", "",
            "| Contrast | Tasks | Runs/cell | Unit | Mean a | Mean b | Difference | 95% bootstrap CI |",
            "|---|---:|---:|---|---:|---:|---:|---:|",
        ])
        for row in result["effort"]["contrasts"]:
            for metric, values in row["metrics"].items():
                scale = 1000 if metric == "tokens" else 1
                unit = {"tokens": "Tokens [×10³]", "api_calls": "Model API calls [calls]", "wall_seconds": "Run-time [s]"}[metric]
                lines.append(
                    f"| {row['contrast']} | {row['n_tasks']} | {row['measurable_runs_per_cell']} | {unit} | "
                    f"{values['mean_a']/scale:.2f} | {values['mean_b']/scale:.2f} | {values['effect']/scale:+.2f} | "
                    f"[{values['ci_low']/scale:+.2f}, {values['ci_high']/scale:+.2f}] |"
                )
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, result: dict[str, Any]) -> None:
    if "statistics-v2" in output_dir.resolve().parts:
        raise ValueError("Historical statistics-v2 outputs must not be overwritten")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "outcome_taxonomy.csv", TAXONOMY_ROWS)
    write_csv(output_dir / "raw_status_mapping.csv", outcome_rows(result["outcomes"]))
    write_csv(output_dir / "cell_summaries.csv", result["summary"]["cell_summaries"])
    write_csv(output_dir / "contrast_sample_sizes.csv", result["sample_sizes"])
    write_csv(
        output_dir / "contrast_exclusions.csv",
        result["exclusions"],
        ["contrast", "family", "task", "nonmeasurable_run_count", "nonmeasurable_requirements", "categories", "origins"],
    )
    if not result["summary"]["audit_only"]:
        write_csv(output_dir / "contrast_results.csv", result["contrast_results"])
        write_json(output_dir / "contrast_results.json", result["contrast_json"])
        write_json(output_dir / "effort_bootstrap.json", result["effort"])
        write_csv(output_dir / "effort_results.csv", [
            {"contrast": row["contrast"], "family": row["family"],
             "cell_a": row["cell_a"], "cell_b": row["cell_b"],
             "n_tasks": row["n_tasks"], "measurable_runs_per_cell": row["measurable_runs_per_cell"],
             "estimator": row["estimator"], "metric": metric, **values}
            for row in result["effort"]["contrasts"] for metric, values in row["metrics"].items()
        ])
        write_csv(output_dir / "pairwise_disagreement.csv", result["disagreement"])
        write_csv(output_dir / "delivered_only_sensitivity.csv", result["sensitivity"])
    (output_dir / "report.md").write_text(_report_markdown(result), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args(argv)
    if "statistics-v2" in args.output_dir.resolve().parts:
        parser.error("statistics-v2 is historical; use a new statistics-v3 output directory")
    config = load_config(args.config)
    if config.get("analysis_type") != "main_run":
        parser.error("configuration is not a main_run configuration")
    result = analyze(config, audit_only=args.audit_only)
    validate_expected(config, result)
    write_outputs(args.output_dir, result)
    print(f"Main-run audit written to {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
