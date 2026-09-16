import unittest
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from thesis_analysis.io import REPO_ROOT, load_config
from thesis_analysis.main_run import analyze as analyze_main, validate_expected as validate_main, write_outputs
from thesis_analysis.variance_pilot import analyze as analyze_pilot, validate_expected as validate_pilot


CONFIG_ROOT = REPO_ROOT / "scripts" / "analysis" / "configs"


class RepositoryIntegrationTests(unittest.TestCase):
    def test_both_pilots_match_audit_expectations(self):
        for name in ("vp_glm.json", "vp_qwen.json"):
            with self.subTest(config=name):
                config = load_config(CONFIG_ROOT / name)
                result = analyze_pilot(config)
                validate_pilot(config, result)

    def test_both_main_runs_match_error_and_sample_expectations(self):
        for name in ("main_glm.json", "main_qwen.json"):
            with self.subTest(config=name):
                config = load_config(CONFIG_ROOT / name)
                result = analyze_main(config, audit_only=True)
                validate_main(config, result)

    def test_both_main_runs_preserve_solve_tests_and_match_mean_effort_controls(self):
        for name in ("main_glm.json", "main_qwen.json"):
            with self.subTest(config=name):
                config = load_config(CONFIG_ROOT / name)
                analysis_dir = REPO_ROOT / config["run_directory"] / "analysis"
                old_dir = analysis_dir / "statistics-v2"
                # A submission needs only accepted v3 records, not historical ratios.
                control_dir = old_dir if old_dir.exists() else analysis_dir / "statistics-v3"
                old = json.loads((control_dir / "contrast_results.json").read_text())
                result = analyze_main(config)
                validate_main(config, result)
                self.assertEqual(result["contrast_json"]["contrasts"], old["contrasts"])
                for contrast, effort in zip(old["contrasts"], result["effort"]["contrasts"], strict=True):
                    self.assertEqual(effort["estimator"], "mean_effort_per_measurable_run")
                    task_rows = contrast["task_estimates"]
                    count = len(task_rows)
                    indices = np.random.default_rng(42).integers(0, count, size=(10000, count))
                    for metric, values in effort["metrics"].items():
                        left = np.array([row[f"{metric}_a"] / 2 for row in task_rows])
                        right = np.array([row[f"{metric}_b"] / 2 for row in task_rows])
                        self.assertAlmostEqual(values["mean_a"], float(left.mean()), delta=1e-8)
                        self.assertAlmostEqual(values["mean_b"], float(right.mean()), delta=1e-8)
                        control = np.quantile((left-right)[indices].mean(axis=1), [.025, .975])
                        self.assertAlmostEqual(values["ci_low"], control[0], delta=1e-8)
                        self.assertAlmostEqual(values["ci_high"], control[1], delta=1e-8)
                with TemporaryDirectory() as directory:
                    write_outputs(Path(directory), result)
                    saved_dir = analysis_dir / "statistics-v3"
                    if saved_dir.exists():
                        for path in Path(directory).iterdir():
                            self.assertEqual(path.read_bytes(), (saved_dir / path.name).read_bytes(),
                                             f"v3 output is not byte reproducible: {name}/{path.name}")
                    with (Path(directory) / "effort_results.csv").open(newline="") as stream:
                        rows = list(csv.DictReader(stream))
                    self.assertEqual(len(rows), 21)
                    self.assertTrue(all(row["estimator"] == "mean_effort_per_measurable_run" for row in rows))
                    self.assertIn("Mean effort per measurable attempt", (Path(directory) / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
