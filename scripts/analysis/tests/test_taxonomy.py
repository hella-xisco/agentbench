import unittest

from thesis_analysis.taxonomy import UnknownOutcomeError, normalize_outcome


def raw(**changes):
    value = {
        "config_name": "test",
        "model": "model",
        "cell": "cell",
        "task": "task",
        "repetition": "run_0",
        "trajectory_path": "trajectory.json",
        "report_path": "report.json",
        "exit_status": "Submitted",
        "evaluation_error": None,
        "resolved_present": True,
        "resolved": False,
        "model_responses": 1,
        "tool_calls": 1,
        "submission": "patch",
        "tokens": 1,
        "api_calls": 1,
        "wall_seconds": 1,
    }
    value.update(changes)
    return value


class TaxonomyTests(unittest.TestCase):
    def assert_category(self, category, **changes):
        self.assertEqual(normalize_outcome(raw(**changes)).category, category)

    def test_all_categories(self):
        self.assert_category("solved", resolved=True)
        self.assert_category("failed_patch")
        self.assert_category("empty_patch", submission="")
        self.assert_category("no_action", tool_calls=0, submission="")
        self.assert_category("timeout", exit_status="ExecutionFailed", model_responses=2,
                             report_path=None, resolved_present=False)
        self.assert_category("evaluation_error", evaluation_error="harness failed")
        self.assert_category("serving_error", exit_status="APIError", model_responses=0,
                             report_path=None, resolved_present=False)
        self.assert_category("missing_artifact", trajectory_path=None, report_path=None,
                             exit_status=None, resolved_present=False)

    def test_execution_failure_without_response_is_serving_error(self):
        outcome = normalize_outcome(raw(exit_status="ExecutionFailed", model_responses=0))
        self.assertFalse(outcome.measurable)
        self.assertEqual(outcome.origin, "measurement_pipeline")
        self.assertEqual(outcome.evaluation_status, "completed")

    def test_unknown_exit_status_aborts(self):
        with self.assertRaises(UnknownOutcomeError):
            normalize_outcome(raw(exit_status="SomethingNew"))


if __name__ == "__main__":
    unittest.main()
