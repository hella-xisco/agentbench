import unittest
import csv
import tempfile
from pathlib import Path

from thesis_analysis.pilot_figures import load_matrix
from thesis_analysis.reporting import (
    context_categorization_table,
    contrast_sample_sizes_table,
    effort_result_table,
    recurrence_table,
    fixed,
    main_outcome_counts_table,
    pass1_result_table,
    pilot_design_table,
    pilot_summary_table,
    source_comment,
)


class ReportingTests(unittest.TestCase):
    def test_context_categorization_table_alternates_rows_and_bolds_treatment_zero(self):
        rows = [
            {"id": "A-1", "repo": "owner/alpha", "bucket": "P"},
            {"id": "A-2", "repo": "owner/alpha", "bucket": "D"},
            {"id": "B-1", "repo": "owner/beta", "bucket": "D"},
            {"id": "B-2", "repo": "owner/beta", "bucket": "N"},
        ]
        rendered = context_categorization_table(rows, "% provenance\n")
        self.assertIn("Statement category", rendered)
        self.assertIn("beta & \\textbf{0} & 1 & 1 & 0 & 2", rendered)
        self.assertEqual(rendered.count("\\rowcolor{black!6}"), 1)
        self.assertIn("\\textbf{Total} & \\textbf{1} & \\textbf{2}", rendered)

    def test_context_categorization_table_rejects_unknown_category(self):
        with self.assertRaisesRegex(ValueError, "Unknown context-statement category"):
            context_categorization_table(
                [{"id": "A-1", "repo": "owner/alpha", "bucket": "X"}],
                "% provenance\n",
            )

    def test_pilot_summary_contains_declared_quantities_and_roles(self):
        glm = {
            "planning_role": "initial_main_run_repetition_choice",
            "pass_at_1_first_10": 0.4,
            "pass_at_1_all_20": 0.395,
            "round_count_sample_sd": 0.8870412,
            "mean_within_task_sample_variance": 0.1186842,
            "category_counts": {"timeout": 3},
            "planned_runs": 200,
        }
        qwen = {
            "planning_role": "transfer_check_only",
            "pass_at_1_first_10": 0.59,
            "pass_at_1_all_20": 0.585,
            "round_count_sample_sd": 0.933302,
            "mean_within_task_sample_variance": 0.0892105,
            "category_counts": {"timeout": 81},
            "planned_runs": 200,
        }
        rendered = pilot_summary_table(glm, qwen, "% provenance\n")
        self.assertIn("40.0\\,\\%", rendered)
        self.assertIn("0.1187", rendered)
        self.assertIn("81/200", rendered)
        self.assertIn("Transfer and runtime check only", rendered)

    def test_pilot_design_marks_chosen_row(self):
        rows = [
            {
                "n_tasks": "50",
                "repetitions_per_cell": "1",
                "planned_runs": "300",
                "estimated_hours": "9.25",
                "planning_standard_error": "0.0689",
                "nominal_t_95_half_width": "0.1385",
            },
            {
                "n_tasks": "71",
                "repetitions_per_cell": "2",
                "planned_runs": "852",
                "estimated_hours": "26.27",
                "planning_standard_error": "0.040888",
                "nominal_t_95_half_width": "0.0815486",
            },
        ]
        rendered = pilot_design_table(rows, 71, 2, "% provenance\n")
        self.assertIn("\\textbf{4.09}", rendered)
        self.assertIn("\\textbf{8.15}", rendered)
        self.assertIn("Server time [h]", rendered)
        self.assertIn("[pp]", rendered)

    def test_pilot_design_rejects_missing_chosen_row(self):
        with self.assertRaisesRegex(ValueError, "Chosen design"):
            pilot_design_table([], 71, 2, "% provenance\n")

    def test_decimal_display_uses_conventional_half_up_rounding(self):
        self.assertEqual(fixed("13.135"), "13.14")

    def test_provenance_path_is_portable_within_repository(self):
        rendered = source_comment("command", [Path.cwd() / "outputs" / "summary.json"])
        self.assertIn("% Source: outputs/summary.json", rendered)

    def test_pilot_figure_requires_complete_ten_by_twenty_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw_status_mapping.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["task", "repetition", "category"])
                writer.writeheader()
                writer.writerow({"task": "task-1", "repetition": "run_0", "category": "solved"})
            with self.assertRaisesRegex(ValueError, "Expected 10 pilot tasks"):
                load_matrix(path)

    def test_main_outcome_table_reports_counts_without_derived_efficiency(self):
        labels = ["K0", "K0d", "K1", "K1s", "K2", "K2s"]
        summaries = [
            {
                "cell": f"raw_{label}",
                "cell_label": label,
                "planned_runs": "2",
                "measurable_runs": "1",
            }
            for label in labels
        ]
        raw_rows = [
            {
                "cell": f"raw_{label}",
                "category": category,
                "measurement_status": status,
            }
            for label in labels
            for category, status in (
                ("solved", "measurable"),
                ("evaluation_error", "not_measurable"),
            )
        ]
        rendered = main_outcome_counts_table(
            raw_rows, raw_rows, summaries, summaries, "% provenance\n"
        )
        self.assertIn("Failed patch", rendered)
        self.assertIn("Eval. error", rendered)
        self.assertIn("$M_{g,c}$", rendered)
        self.assertIn("Measurable ($X$ defined)", rendered)
        self.assertIn("Not measurable ($X$ undefined)", rendered)
        self.assertNotIn("pass@1", rendered)
        self.assertNotIn("Tokens/solved", rendered)
        self.assertEqual(rendered.count("\\rowcolor{black!6}"), 6)
        self.assertLess(
            rendered.rindex("$g_{\\mathrm{GLM}}$"),
            rendered.index("$g_{\\mathrm{Qwen}}$"),
        )
        self.assertIn("\\addlinespace[2pt]", rendered)

    def test_main_outcome_table_rejects_unknown_categories(self):
        labels = ["K0", "K0d", "K1", "K1s", "K2", "K2s"]
        summaries = [
            {
                "cell": f"raw_{label}",
                "cell_label": label,
                "planned_runs": "1",
                "measurable_runs": "1",
            }
            for label in labels
        ]
        raw_rows = [
            {
                "cell": f"raw_{label}",
                "category": "unknown" if label == "K0" else "solved",
                "measurement_status": "measurable",
            }
            for label in labels
        ]
        with self.assertRaisesRegex(ValueError, "unknown category"):
            main_outcome_counts_table(
                raw_rows, raw_rows, summaries, summaries, "% provenance\n"
            )

    def test_contrast_sample_table_pairs_configurations(self):
        contrasts = [
            ("K1-K0", "RQ1"),
            ("K2-K0", "RQ1"),
            ("K1s-K1", "RQ2"),
            ("K2s-K2", "RQ2"),
            ("K0d-K0", "RQ3"),
            ("K1-K0d", "RQ3"),
            ("K2-K0d", "RQ3"),
        ]
        rows = [
            {
                "contrast": contrast,
                "family": family,
                "planned_tasks": "71",
                "included_tasks": "68",
                "excluded_tasks": "3",
                "nonmeasurable_required_runs": "4",
            }
            for contrast, family in contrasts
        ]
        rendered = contrast_sample_sizes_table(rows, rows, "% provenance\n")
        self.assertIn("Complete $|T^{(g)}_{ab}|$", rendered)
        self.assertIn("K1$-$K0", rendered)
        self.assertEqual(rendered.count("\\rowcolor{black!6}"), 7)

    def test_effort_table_uses_explicit_thousand_token_unit(self):
        metric = {
            "mean_a": 2000.0,
            "mean_b": 1000.0,
            "effect": 1000.0,
            "ci_low": 500.0,
            "ci_high": 1500.0,
        }
        rows = [
            {
                "contrast": contrast,
                "n_tasks": 68,
                "metrics": {
                    "tokens": metric,
                    "api_calls": metric,
                    "wall_seconds": metric,
                },
            }
            for contrast in ("K1-K0", "K2-K0")
        ]
        rendered = effort_result_table(
            {"estimator": "mean_effort_per_measurable_run", "contrasts": rows},
            {"estimator": "mean_effort_per_measurable_run", "contrasts": rows},
            "RQ1",
            "% provenance\n",
        )
        self.assertIn("Tokens [$\\times 10^3$]", rendered)
        self.assertIn("Run-time [s]", rendered)
        self.assertNotIn("Tokens (k)", rendered)
        self.assertIn("Mean $a$ & Mean $b$", rendered)
        self.assertEqual(rendered.count("\\multicolumn{7}"), 3)
        self.assertEqual(rendered.count("Configuration & Contrast"), 3)
        self.assertNotIn(" & Unit & ", rendered)
        self.assertEqual(rendered.count("\\rowcolor{black!6}"), 6)

    def test_mean_effort_table_rejects_historical_ratio_outputs(self):
        with self.assertRaisesRegex(ValueError, "historical solved-run ratios"):
            effort_result_table({"contrasts": []}, {"contrasts": []}, "RQ1", "% provenance\n")

    def test_pass1_table_reports_standard_error_in_percentage_points(self):
        rows = [
            {
                "contrast": contrast, "n_tasks": "68",
                "effect": "-0.0588235294", "standard_error": "0.0539581380",
                "ci_low": "-0.1665244237", "ci_high": "0.0488773649",
                "t_value": "-1.0901697421", "degrees_freedom": "67",
                "p_value": "0.2795437164", "p_value_holm": "0.5590874329",
                "holm_reject_alpha_0_05": "False",
            }
            for contrast in ("K1-K0", "K2-K0")
        ]
        rendered = pass1_result_table(rows, rows, "RQ1", "% provenance\n")
        self.assertIn("$\\mathrm{SE}(\\widehat\\Delta)$", rendered)
        self.assertIn("-5.9 & 5.40 & [-16.7, +4.9]", rendered)
        self.assertEqual(rendered.count("[pp]"), 3)
        self.assertEqual(rendered.count("\\rowcolor{black!6}"), 2)

    def test_recurrence_requires_same_sign_and_holm_evidence_in_both_configurations(self):
        glm = []
        qwen = []
        for index, contrast in enumerate(
            ["K1-K0", "K2-K0", "K1s-K1", "K2s-K2", "K0d-K0", "K1-K0d", "K2-K0d"]
        ):
            family = "RQ1" if index < 2 else "RQ2" if index < 4 else "RQ3"
            base = {
                "contrast": contrast,
                "family": family,
                "effect": "0.1",
                "ci_low": "0.01",
                "ci_high": "0.2",
                "p_value_holm": "0.04",
                "holm_reject_alpha_0_05": "True",
            }
            glm.append(dict(base))
            qwen.append(dict(base))
        qwen[1]["effect"] = "-0.1"
        qwen[2]["holm_reject_alpha_0_05"] = "False"
        rendered = recurrence_table(glm, qwen, "% provenance\n")
        lines = [line for line in rendered.splitlines() if "K1$-$K0" in line or "K2$-$K0" in line or "K1s$-$K1" in line]
        self.assertTrue(lines[0].endswith("yes \\\\"))
        self.assertTrue(lines[1].endswith("no \\\\"))
        self.assertTrue(lines[2].endswith("no \\\\"))


if __name__ == "__main__":
    unittest.main()
