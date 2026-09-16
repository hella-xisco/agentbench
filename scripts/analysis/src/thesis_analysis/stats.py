"""Statistical primitives shared by pilot and main-run analyses."""

from __future__ import annotations

import math
import statistics
from typing import Any

import numpy as np
from scipy import stats


def pilot_matrix_statistics(matrix: list[list[int]]) -> dict[str, Any]:
    """Compute pilot quantities for a task×repetition binary matrix."""
    if not matrix or not matrix[0]:
        raise ValueError("Pilot matrix must not be empty")
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError("Pilot matrix must be rectangular")
    if any(value not in (0, 1) for row in matrix for value in row):
        raise ValueError("Pilot outcomes must be binary")
    round_counts = [sum(row[column] for row in matrix) for column in range(width)]
    within = [statistics.variance(row) for row in matrix]
    return {
        "pass_at_1": statistics.fmean(value for row in matrix for value in row),
        "round_counts": round_counts,
        "round_count_sample_sd": statistics.stdev(round_counts),
        "task_sample_variances": within,
        "mean_within_task_sample_variance": statistics.fmean(within),
    }


def paired_t_summary(differences: list[float], confidence: float = 0.95) -> dict[str, float | int]:
    n = len(differences)
    if n < 2:
        raise ValueError("A paired t analysis requires at least two task differences")
    mean = statistics.fmean(differences)
    sd = statistics.stdev(differences)
    se = sd / math.sqrt(n)
    df = n - 1
    critical = float(stats.t.ppf(0.5 + confidence / 2, df))
    if se == 0:
        t_value = 0.0 if mean == 0 else math.copysign(math.inf, mean)
        p_value = 1.0 if mean == 0 else 0.0
    else:
        t_value = mean / se
        p_value = float(2 * stats.t.sf(abs(t_value), df))
    return {
        "n_tasks": n,
        "effect": mean,
        "sd_delta": sd,
        "standard_error": se,
        "t_value": t_value,
        "degrees_freedom": df,
        "p_value": p_value,
        "ci_low": mean - critical * se,
        "ci_high": mean + critical * se,
    }


def holm_adjust(p_values: list[float]) -> list[float]:
    """Return Holm step-down adjusted p-values in original order."""
    m = len(p_values)
    if any(not 0 <= p <= 1 for p in p_values):
        raise ValueError("p-values must lie in [0, 1]")
    order = sorted(range(m), key=p_values.__getitem__)
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        candidate = min(1.0, (m - rank) * p_values[index])
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted


def bootstrap_effort(
    rows: list[dict[str, Any]],
    metrics: tuple[str, ...] = ("tokens", "api_calls", "wall_seconds"),
    repetitions: int = 10_000,
    seed: int = 42,
    runs_per_task: int = 2,
) -> dict[str, Any]:
    """Bootstrap differences in mean effort per measurable attempt.

    Each input effort value is a task's sum across runs_per_task repetitions.
    Tasks retain both cells and all repetitions; draws are shared by all metrics.
    Solved counts do not enter this estimator, so no draw needs rejection.
    """
    if not rows:
        raise ValueError("Bootstrap requires task rows")
    for name, value in (("repetitions", repetitions), ("runs_per_task", runs_per_task)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not metrics or len(set(metrics)) != len(metrics):
        raise ValueError("Bootstrap metrics must be nonempty and unique")
    try:
        a = np.asarray([[float(row[f"{metric}_a"]) for metric in metrics] for row in rows])
        b = np.asarray([[float(row[f"{metric}_b"]) for metric in metrics] for row in rows])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Missing or invalid task effort measurement") from error
    if not np.isfinite(a).all() or not np.isfinite(b).all() or (a < 0).any() or (b < 0).any():
        raise ValueError("Task effort measurements must be finite and nonnegative")
    rng = np.random.default_rng(seed)
    n = len(rows)
    task_differences = (a - b) / runs_per_task
    draws = np.empty((repetitions, len(metrics)))
    for start in range(0, repetitions, 4096):
        stop = min(start + 4096, repetitions)
        indices = rng.integers(0, n, size=(stop - start, n))
        draws[start:stop] = task_differences[indices].mean(axis=1)
    result_metrics: dict[str, Any] = {}
    for column, metric in enumerate(metrics):
        mean_a = float(a[:, column].sum() / (runs_per_task * n))
        mean_b = float(b[:, column].sum() / (runs_per_task * n))
        low, high = np.quantile(draws[:, column], [0.025, 0.975], method="linear")
        result_metrics[metric] = {
            "mean_a": mean_a,
            "mean_b": mean_b,
            "effect": mean_a - mean_b,
            "ci_low": float(low),
            "ci_high": float(high),
        }
    return {
        "estimator": "mean_effort_per_measurable_run",
        "runs_per_task": runs_per_task,
        "measurable_runs_per_cell": runs_per_task * n,
        "seed": seed,
        "requested_draws": repetitions,
        "accepted_draws": repetitions,
        "metrics": result_metrics,
    }
