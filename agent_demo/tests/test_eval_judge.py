import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


AGENT_DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT_DEMO))

import eval_judge


class VerifierSemanticsTests(unittest.TestCase):
    def run_raw_verifier(self, stdout, returncode):
        completed = mock.Mock(
            returncode=returncode,
            stdout=stdout,
            stderr="",
        )
        trajectory = {"verifier_path": str(Path(eval_judge.__file__))}
        with tempfile.TemporaryDirectory() as run_dir:
            with mock.patch.object(eval_judge.subprocess, "run", return_value=completed):
                return eval_judge.run_verifier(Path(run_dir), trajectory)

    def run_verifier(self, payload, returncode):
        return self.run_raw_verifier(json.dumps(payload), returncode)

    def test_task_failure_is_a_successful_framework_run(self):
        verdict = self.run_verifier({"pass": False, "reason": "not completed"}, 1)
        self.assertTrue(verdict["success"])
        self.assertFalse(verdict["pass"])

    def test_task_pass_is_a_successful_framework_run(self):
        verdict = self.run_verifier({"pass": True, "reason": "completed"}, 0)
        self.assertTrue(verdict["success"])
        self.assertTrue(verdict["pass"])

    def test_exit_code_mismatch_is_a_framework_failure(self):
        verdict = self.run_verifier({"pass": False}, 0)
        self.assertFalse(verdict["success"])
        self.assertIn("exit-code mismatch", verdict["rationale"])

    def test_missing_boolean_pass_is_a_framework_failure(self):
        verdict = self.run_verifier({"pass": "false"}, 1)
        self.assertFalse(verdict["success"])
        self.assertIn("boolean pass", verdict["rationale"])

    def test_reported_infrastructure_error_is_a_framework_failure(self):
        verdict = self.run_verifier({"pass": False, "infra_error": True}, 1)
        self.assertFalse(verdict["success"])

    def test_malformed_json_is_a_framework_failure(self):
        verdict = self.run_raw_verifier("not json", 1)
        self.assertFalse(verdict["success"])

    def test_non_object_json_is_a_framework_failure(self):
        verdict = self.run_verifier([False], 1)
        self.assertFalse(verdict["success"])


class JudgeSemanticsTests(unittest.TestCase):
    def test_current_pass_field_is_preserved(self):
        verdict = eval_judge.normalize_judge_verdict({"pass": False})
        self.assertTrue(verdict["success"])
        self.assertFalse(verdict["pass"])

    def test_legacy_success_field_is_normalized_to_pass(self):
        verdict = eval_judge.normalize_judge_verdict({"success": False})
        self.assertTrue(verdict["success"])
        self.assertFalse(verdict["pass"])

    def test_missing_task_verdict_is_a_framework_failure(self):
        verdict = eval_judge.normalize_judge_verdict({"confidence": 0.5})
        self.assertFalse(verdict["success"])
        self.assertNotIn("pass", verdict)

    def test_framework_exit_code_does_not_treat_task_failure_as_an_error(self):
        self.assertEqual(eval_judge.framework_exit_code({"success": True, "pass": False}), 0)
        self.assertEqual(eval_judge.framework_exit_code({"success": False}), 2)


if __name__ == "__main__":
    unittest.main()
