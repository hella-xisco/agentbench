import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from thesis_analysis.pilot_figures import load_palette
from thesis_analysis.result_figures import (
    CELL_ORDER, CONTRAST_ORDER, generate_outcome_composition_svg,
    generate_mean_effort_forest_svg,
)


PALETTE = Path(__file__).resolve().parents[3] / "figures" / "palette.json"
SVG = "{http://www.w3.org/2000/svg}"


class OutcomeFigureTests(unittest.TestCase):
    def counts(self, factor=1):
        return {
            cell: {
                "solved": factor * (index + 1),
                "failed_patch": 7 - factor * (index + 1),
                "empty_patch": 0,
                "no_action": 0,
                "timeout": 0,
                "evaluation_error": 0,
            }
            for index, cell in enumerate(CELL_ORDER)
        }

    def test_aggregates_six_cells_into_two_configuration_bars(self):
        glm = self.counts()
        qwen = self.counts()
        qwen["K0"]["solved"] += 1
        qwen["K0"]["failed_patch"] -= 1
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "outcomes.svg"
            generate_outcome_composition_svg(glm, qwen, PALETTE, output, "audit.csv")
            root = ET.parse(output).getroot()
        labels = [element.text for element in root.findall(f"{SVG}text")]
        self.assertEqual(labels.count("GLM"), 1)
        self.assertEqual(labels.count("Qwen"), 1)
        self.assertFalse(any(cell in labels for cell in CELL_ORDER))
        self.assertFalse(any("Absolute run outcomes" in label for label in labels))
        self.assertIn("Planned runs", labels)
        self.assertIn("42", labels)
        self.assertIn("22", labels)
        palette = load_palette(PALETTE)
        segments = [
            element for element in root.findall(f"{SVG}rect")
            if element.attrib["fill"] == palette["outcome-solved"]
            and float(element.attrib["height"]) == 34
        ]
        self.assertEqual(len(segments), 2)
        self.assertAlmostEqual(float(segments[0].attrib["width"]), 765 * 21 / 42, places=1)
        self.assertAlmostEqual(float(segments[1].attrib["width"]), 765 * 22 / 42, places=1)
        self.assertIn("audit.csv", root.find(f"{SVG}metadata").text)

    def test_rejects_missing_cells(self):
        glm = self.counts()
        del glm["K0"]
        with self.assertRaisesRegex(ValueError, "all six cells"):
            generate_outcome_composition_svg(glm, self.counts(), PALETTE, Path("unused.svg"), "audit")

    def test_rejects_unrepresented_pipeline_errors(self):
        glm = self.counts()
        glm["K0"]["serving_error"] = 1
        with self.assertRaisesRegex(ValueError, "cannot omit"):
            generate_outcome_composition_svg(glm, self.counts(), PALETTE, Path("unused.svg"), "audit")


class MeanEffortFigureTests(unittest.TestCase):
    def data(self):
        return {
            "estimator": "mean_effort_per_measurable_run",
            "contrasts": [
                {"contrast": contrast, "metrics": {
                    metric: {"effect": 10 * divisor, "ci_low": -20 * divisor, "ci_high": 30 * divisor}
                    for metric, divisor in (("tokens", 1000), ("api_calls", 1), ("wall_seconds", 1))
                }} for contrast in CONTRAST_ORDER
            ],
        }

    def test_three_resource_panels_grouping_markers_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ("first.svg", "second.svg"))
            for path in (first, second):
                generate_mean_effort_forest_svg(self.data(), self.data(), PALETTE, path, "v3/effort_bootstrap.json")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            root = ET.parse(first).getroot()
        labels = ["".join(element.itertext()) for element in root.findall(f"{SVG}text")]
        for label in ("RQ1", "RQ2", "RQ3", "Δātokens [×10³ tokens]", "Δāmodelcalls [calls]", "Δātime [s]"):
            self.assertIn(label, labels)
        self.assertEqual(len(root.findall(f"{SVG}circle")), 22)
        self.assertEqual(len(root.findall(f"{SVG}polygon")), 22)
        self.assertIn("v3/effort_bootstrap.json", root.find(f"{SVG}metadata").text)

    def test_rejects_old_estimator_and_incomplete_contrasts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "figure.svg"
            with self.assertRaisesRegex(ValueError, "v3 outputs"):
                generate_mean_effort_forest_svg({"contrasts": []}, self.data(), PALETTE, output, "audit")
            data = self.data()
            data["contrasts"].pop()
            with self.assertRaisesRegex(ValueError, "seven contrasts"):
                generate_mean_effort_forest_svg(data, self.data(), PALETTE, output, "audit")

    def test_rejects_nonfinite_intervals(self):
        data = self.data()
        data["contrasts"][0]["metrics"]["tokens"]["ci_high"] = float("nan")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Invalid mean-effort"):
                generate_mean_effort_forest_svg(data, self.data(), PALETTE, Path(directory) / "figure.svg", "audit")


if __name__ == "__main__":
    unittest.main()
