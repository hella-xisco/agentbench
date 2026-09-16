import json
import tempfile
import unittest
from pathlib import Path

from thesis_analysis.io import AnalysisInputError, load_matrix


def create_run(root: Path, task: str, *, report: bool = True):
    trajectory_dir = root / "agentbench" / "suite" / "no_plan" / "model" / "run_0" / task
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    (trajectory_dir / f"{task}.traj.json").write_text(json.dumps({
        "info": {"exit_status": "Submitted", "submission": "patch", "model_stats": {"api_calls": 1},
                 "wall_time_seconds": 1},
        "messages": [{"role": "assistant", "tool_calls": [{"function": {"name": "edit"}}]}],
        "responses": [{"usage": {"total_tokens": 1}}],
    }))
    if report:
        report_dir = root / "swebench" / "suite" / "no_plan" / "model" / "run_0" / task
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "report.json").write_text(json.dumps({task: {"resolved": False}}))


class ManifestTests(unittest.TestCase):
    def config(self, root: Path, manifest: Path):
        return {
            "name": "test", "model": {"name": "model"}, "run_directory": str(root),
            "task_manifest": str(manifest), "cells": ["no_plan"], "repetitions": ["run_0"],
        }

    def test_missing_task_run_trajectory_aborts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "tasks.txt"
            manifest.write_text("task_a\ntask_b\n")
            create_run(root, "task_a")
            with self.assertRaises(AnalysisInputError):
                load_matrix(self.config(root, manifest))

    def test_additional_task_run_aborts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "tasks.txt"
            manifest.write_text("task_a\n")
            create_run(root, "task_a")
            create_run(root, "task_extra")
            with self.assertRaises(AnalysisInputError):
                load_matrix(self.config(root, manifest))

    def test_missing_report_is_explicit_missing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "tasks.txt"
            manifest.write_text("task_a\n")
            create_run(root, "task_a", report=False)
            outcomes, _ = load_matrix(self.config(root, manifest))
            self.assertEqual(outcomes[0].category, "missing_artifact")
            self.assertFalse(outcomes[0].measurable)


if __name__ == "__main__":
    unittest.main()

