"""Safety and coverage checks for the submission reproduction helpers."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, PROJECT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SubmissionToolTests(unittest.TestCase):
    def test_reproduction_covers_four_matrices_and_five_asset_commands(self):
        tool = load("reproduce")
        with tempfile.TemporaryDirectory() as directory:
            steps = tool.commands(Path(directory) / "new", False, False)
        self.assertEqual(len(steps), 9)
        self.assertEqual(sum("thesis_analysis.variance_pilot" in step for step in steps), 2)
        self.assertEqual(sum("thesis_analysis.main_run" in step for step in steps), 2)
        self.assertEqual({step[3] for step in steps[4:]}, {"pilot-tables", "pilot-figures", "material-categorization", "main-overview", "main-results"})

    def test_existing_reproduction_directory_is_rejected_before_execution(self):
        tool = load("reproduce")
        with tempfile.TemporaryDirectory() as directory, patch.object(tool.subprocess, "run") as run:
            with patch("sys.argv", ["reproduce", "--output-dir", directory]):
                with self.assertRaisesRegex(SystemExit, "already exists"):
                    tool.main()
            run.assert_not_called()

    def test_asset_registry_reads_nested_caption_groups(self):
        tool = load("register_thesis_assets")
        self.assertEqual(tool.braced(r"{Tokens [$\times 10^{3}$]}", 0)[0], r"Tokens [$\times 10^{3}$]")
        with self.assertRaisesRegex(ValueError, "Unbalanced"):
            tool.braced("{unfinished", 0)


if __name__ == "__main__":
    unittest.main()
