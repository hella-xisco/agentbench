import json
import tempfile
import unittest
from pathlib import Path

from thesis_analysis.behaviour import classify_call, read_trajectory


class BehaviourTests(unittest.TestCase):
    def test_phase_rules_distinguish_read_edit_and_validation(self):
        self.assertEqual(classify_call("read", "{}"), "explore")
        self.assertEqual(classify_call("edit", "{}"), "edit")
        self.assertEqual(classify_call("bash", '{"command":"cd repo && pytest -q"}'), "validate")
        self.assertEqual(classify_call("bash", '{"command":"rg needle src"}'), "explore")

    def test_trajectory_detects_skill_activation_and_three_call_loop(self):
        tool_call = {
            "function": {
                "name": "read",
                "arguments": '{"path":"/tmp/.pi/skills/demo/SKILL.md"}',
            }
        }
        trajectory = {
            "messages": [
                {"role": "assistant", "tool_calls": [tool_call, tool_call, tool_call]}
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectory.json"
            path.write_text(json.dumps(trajectory), encoding="utf-8")
            parsed = read_trajectory(path)
        self.assertEqual(parsed["calls"], 3)
        self.assertEqual(parsed["skill_reads"], 3)
        self.assertTrue(parsed["loop"])


if __name__ == "__main__":
    unittest.main()
