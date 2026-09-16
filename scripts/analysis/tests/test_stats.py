import json
import math
import unittest

import numpy as np
from scipy import stats as scipy_stats

from thesis_analysis.stats import bootstrap_effort, holm_adjust, paired_t_summary, pilot_matrix_statistics


class StatisticalPrimitiveTests(unittest.TestCase):
    def test_fixed_binary_pilot_matrix(self):
        matrix = [
            [0, 1, 0, 1],
            [1, 1, 1, 1],
            [0, 0, 0, 0],
        ]
        result = pilot_matrix_statistics(matrix)
        self.assertEqual(result["round_counts"], [1, 2, 1, 2])
        self.assertAlmostEqual(result["pass_at_1"], 0.5)
        self.assertAlmostEqual(result["round_count_sample_sd"], math.sqrt(1 / 3))
        self.assertEqual(result["task_sample_variances"], [1 / 3, 0, 0])
        self.assertAlmostEqual(result["mean_within_task_sample_variance"], 1 / 9)

    def test_paired_t_matches_scipy(self):
        differences = [0.5, 0.0, -0.5, 0.5, 1.0]
        result = paired_t_summary(differences)
        control = scipy_stats.ttest_1samp(differences, popmean=0)
        interval = control.confidence_interval(confidence_level=0.95)
        self.assertAlmostEqual(result["t_value"], float(control.statistic))
        self.assertAlmostEqual(result["p_value"], float(control.pvalue))
        self.assertAlmostEqual(result["ci_low"], float(interval.low))
        self.assertAlmostEqual(result["ci_high"], float(interval.high))

    def test_holm_two_and_three_tests(self):
        self.assertEqual(holm_adjust([0.01, 0.04]), [0.02, 0.04])
        self.assertEqual(holm_adjust([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])

    def test_mean_effort_bootstrap_is_byte_reproducible_and_matches_control(self):
        rows = [
            {"solved_a": 1, "solved_b": 0, "tokens_a": 10, "tokens_b": 5,
             "api_calls_a": 2, "api_calls_b": 1, "wall_seconds_a": 3, "wall_seconds_b": 2},
            {"solved_a": 0, "solved_b": 1, "tokens_a": 7, "tokens_b": 12,
             "api_calls_a": 1, "api_calls_b": 3, "wall_seconds_a": 2, "wall_seconds_b": 4},
        ]
        first = bootstrap_effort(rows, repetitions=500, seed=42)
        second = bootstrap_effort(rows, repetitions=500, seed=42)
        encoded_first = json.dumps(first, sort_keys=True, separators=(",", ":")).encode()
        encoded_second = json.dumps(second, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(encoded_first, encoded_second)
        self.assertNotIn("rejected_zero_denominator_draws", first)
        self.assertEqual(first["accepted_draws"], 500)
        self.assertEqual(first["measurable_runs_per_cell"], 4)
        self.assertEqual(first["metrics"]["tokens"]["mean_a"], 4.25)
        self.assertEqual(first["metrics"]["tokens"]["mean_b"], 4.25)
        indices = np.random.default_rng(42).integers(0, 2, size=(500, 2))
        for metric in ("tokens", "api_calls", "wall_seconds"):
            differences = np.array([(row[f"{metric}_a"] - row[f"{metric}_b"]) / 2 for row in rows])
            control = np.quantile(differences[indices].mean(axis=1), [.025, .975], method="linear")
            self.assertAlmostEqual(first["metrics"][metric]["ci_low"], control[0])
            self.assertAlmostEqual(first["metrics"][metric]["ci_high"], control[1])

    def test_mean_effort_accepts_zero_solved_runs_and_counts_failure_effort(self):
        rows = [{"solved_a": 0, "solved_b": 0, "tokens_a": 120, "tokens_b": 40,
                 "api_calls_a": 12, "api_calls_b": 4, "wall_seconds_a": 240, "wall_seconds_b": 80}]
        result = bootstrap_effort(rows, repetitions=100, runs_per_task=2)
        self.assertEqual(result["metrics"]["tokens"]["mean_a"], 60)
        self.assertEqual(result["metrics"]["tokens"]["mean_b"], 20)
        self.assertEqual(result["metrics"]["tokens"]["effect"], 40)
        self.assertEqual(result["metrics"]["tokens"]["ci_low"], 40)
        self.assertEqual(result["metrics"]["tokens"]["ci_high"], 40)

    def test_mean_effort_bootstrap_shares_draws_across_metrics_and_batches(self):
        rows = [{"tokens_a": x, "tokens_b": 1, "api_calls_a": 2*x, "api_calls_b": 2,
                 "wall_seconds_a": 3*x, "wall_seconds_b": 3} for x in (0, 2, 20)]
        result = bootstrap_effort(rows, repetitions=10000)
        indices = np.random.default_rng(42).integers(0, 3, size=(10000, 3))
        control = np.quantile(np.array([-.5, .5, 9.5])[indices].mean(axis=1), [.025, .975])
        self.assertAlmostEqual(result["metrics"]["tokens"]["ci_low"], control[0])
        self.assertAlmostEqual(result["metrics"]["tokens"]["ci_high"], control[1])
        for field in ("effect", "ci_low", "ci_high"):
            self.assertAlmostEqual(result["metrics"]["api_calls"][field], 2*result["metrics"]["tokens"][field])
            self.assertAlmostEqual(result["metrics"]["wall_seconds"][field], 3*result["metrics"]["tokens"][field])

    def test_mean_effort_rejects_invalid_inputs(self):
        for rows in ([], [{"tokens_a": None, "tokens_b": 1}],
                     [{"tokens_a": float("nan"), "tokens_b": 1}],
                     [{"tokens_a": float("inf"), "tokens_b": 1}],
                     [{"tokens_a": -1, "tokens_b": 1}], [{"tokens_a": 1}]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                bootstrap_effort(rows, metrics=("tokens",))
        for field in ("runs_per_task", "repetitions"):
            for value in (0, -1, 1.5, True):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    bootstrap_effort([{"tokens_a": 1, "tokens_b": 1}], metrics=("tokens",), **{field: value})


if __name__ == "__main__":
    unittest.main()
