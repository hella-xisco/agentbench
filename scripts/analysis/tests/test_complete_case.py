import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from thesis_analysis.main_run import CONTRASTS, _cell_summaries, _complete_contrast_sets, write_outputs
from thesis_analysis.taxonomy import normalize_outcome


def outcome(cell, task, repetition, *, evaluation_error=None, resolved=False, tokens=1, api_calls=1, wall_seconds=1):
    return normalize_outcome({
        "config_name": "test", "model": "model", "cell": cell, "task": task,
        "repetition": repetition, "trajectory_path": "trajectory.json", "report_path": "report.json",
        "exit_status": "Submitted", "evaluation_error": evaluation_error, "resolved_present": True,
        "resolved": resolved, "model_responses": 1, "tool_calls": 1, "submission": "patch",
        "tokens": tokens, "api_calls": api_calls, "wall_seconds": wall_seconds,
    })


class CompleteCaseTests(unittest.TestCase):
    def test_one_error_removes_task_only_from_contrasts_using_that_cell(self):
        cells = sorted({contrast[key] for contrast in CONTRASTS for key in ("cell_a", "cell_b")})
        repetitions = ["run_0", "run_1"]
        rows = []
        for cell in cells:
            for task in ("task_a", "task_b"):
                for repetition in repetitions:
                    error = "eval" if (cell, task, repetition) == ("curated_k1", "task_a", "run_0") else None
                    rows.append(outcome(cell, task, repetition, evaluation_error=error))
        complete, _, _ = _complete_contrast_sets(rows, ["task_a", "task_b"], repetitions)
        self.assertEqual(complete["K1-K0"], ["task_b"])
        self.assertEqual(complete["K1s-K1"], ["task_b"])
        self.assertEqual(complete["K1-K0d"], ["task_b"])
        self.assertEqual(complete["K2-K0"], ["task_a", "task_b"])
        self.assertEqual(complete["K2s-K2"], ["task_a", "task_b"])

    def test_cell_summary_reports_api_effort_and_mean_time_with_explicit_denominators(self):
        rows = [
            outcome("no_plan", "task_a", "run_0", resolved=True, tokens=10, api_calls=2, wall_seconds=4),
            outcome("no_plan", "task_a", "run_1", resolved=False, tokens=20, api_calls=4, wall_seconds=8),
        ]
        summary = _cell_summaries(rows, ["no_plan"])[0]
        self.assertEqual(summary["solved_runs"], 1)
        self.assertEqual(summary["mean_api_calls_per_measurable_run"], 3)
        self.assertNotIn("aggregate_api_calls_per_solved_run", summary)
        self.assertEqual(summary["mean_wall_seconds_per_measurable_run"], 6)

    def test_historical_output_directory_is_protected_including_children(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "statistics-v2" / "child"
            with self.assertRaisesRegex(ValueError, "must not be overwritten"):
                write_outputs(path, {})
            self.assertFalse(path.exists())

    def test_cell_mean_rejects_nonfinite_or_negative_effort(self):
        for value in (float("nan"), float("inf"), -1):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                _cell_summaries([outcome("no_plan", "task_a", "run_0", tokens=value)], ["no_plan"])


if __name__ == "__main__":
    unittest.main()
