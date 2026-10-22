import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.store import WorkflowError, read_state, transact


class TypedVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def module(self):
        spec = importlib.util.find_spec("workflow_lib.verifiers")
        self.assertIsNotNone(spec, "typed verifiers must be implemented")
        from workflow_lib.verifiers import verify_iac_plan, verify_iac_apply, verify_eval_set
        return verify_iac_plan, verify_iac_apply, verify_eval_set

    @staticmethod
    def command(report, exit_code=0):
        value = json.dumps(report)
        return [sys.executable, "-c", f"import sys; print({value!r}); sys.exit({exit_code})"]

    def test_iac_plan_requires_successful_plan_and_clean_policy(self):
        plan, _, _ = self.module()
        clean = self.command({"violations": []})
        report = plan(clean, clean, self.cwd, 10)
        blocked = plan(clean, self.command({"violations": ["public ingress"]}), self.cwd, 10)

        self.assertTrue(report["passed"])
        self.assertFalse(blocked["passed"])
        self.assertEqual(blocked["failure"], "POLICY_VIOLATIONS")

    def test_arbitrary_iac_logs_and_policy_diagnostics_are_not_reports(self):
        plan, apply, evaluate = self.module()
        raw = [sys.executable, '-c', "import sys;sys.stdout.buffer.write(b'caf\\xe9\\r\\n')"]
        body = b'{"violations":[]}'
        diagnostic = b"caf\xe9"
        clean = [sys.executable, '-c', f'import sys;sys.stdout.buffer.write({body!r});sys.stderr.buffer.write({diagnostic!r})']
        self.assertTrue(plan(raw, clean, self.cwd, 10)['passed'])
        authorization = {"approved": True, "action": "infrastructure.apply", "cwd": str(self.cwd.resolve()), "argv": [raw, clean]}
        self.assertTrue(apply(raw, clean, self.cwd, authorization, 10)['passed'])
        self.assertEqual(plan(raw, raw, self.cwd, 10)['failure'], 'INVALID_REPORT_ENCODING')
        self.assertEqual(evaluate(raw, self.cwd, 'baseline', None, 1, 10)['failure'], 'INVALID_REPORT_ENCODING')

    def test_iac_apply_requires_exact_explicit_authorization(self):
        _, apply, _ = self.module()
        argv = self.command({"violations": []})
        authorization = {"approved": True, "action": "infrastructure.apply",
                         "cwd": str(self.cwd.resolve()), "argv": [argv, argv]}
        denied = apply(argv, argv, self.cwd, {**authorization, "argv": ["other"]}, 10)
        accepted = apply(argv, argv, self.cwd, authorization, 10)

        self.assertFalse(denied["passed"])
        self.assertEqual(denied["failure"], "AUTHORIZATION_SCOPE_MISMATCH")
        self.assertTrue(accepted["passed"])

    def test_eval_requires_same_cases_and_post_change_threshold(self):
        _, _, verify = self.module()
        baseline_report = {"cases": [{"id": "safe", "passed": True}, {"id": "unsafe", "passed": False}]}
        baseline = verify(self.command(baseline_report), self.cwd, "baseline", None, 0.75, 10)
        improved = verify(self.command({"cases": [{"id": "safe", "passed": True},
                                    {"id": "unsafe", "passed": True}]}), self.cwd, "post",
                          baseline, 0.75, 10)
        missing = verify(self.command({"cases": [{"id": "safe", "passed": True}]}), self.cwd,
                         "post", baseline, 0.75, 10)
        below = verify(self.command({"cases": [{"id": "safe", "passed": True},
                                  {"id": "unsafe", "passed": False}]}), self.cwd,
                       "post", baseline, 0.75, 10)

        self.assertTrue(baseline["passed"])
        self.assertTrue(improved["passed"])
        self.assertEqual(missing["failure"], "EVAL_CASE_SET_CHANGED")
        self.assertEqual(below["failure"], "EVAL_THRESHOLD_NOT_MET")

    def test_timed_out_typed_commands_are_unavailable(self):
        plan, _, _ = self.module()
        hangs = [sys.executable, "-c", "import time; time.sleep(2)"]
        result = plan(hangs, self.command({"violations": []}), self.cwd, 1)
        self.assertEqual(result["failure"], "TIMEOUT")

    def test_passed_typed_proof_is_bound_to_active_kind_and_token(self):
        _, _, _ = self.module()
        from workflow_lib.verifiers import record_typed_proof
        subprocess.run(["git", "init", "-q"], cwd=self.cwd, check=True)
        subprocess.run(["git", "config", "user.email", "devflow@example.test"], cwd=self.cwd, check=True)
        subprocess.run(["git", "config", "user.name", "Devflow Test"], cwd=self.cwd, check=True)
        subprocess.run(["git", "commit", "--allow-empty", "-qm", "fixture"], cwd=self.cwd, check=True)
        root = self.cwd / "control"
        transact(root, 0, "fixture", {"kind": "fixture", "payload": {"runs": {"run-1": {
            "id": "run-1", "state_version": 1, "plan": {"work_items": [{"id": "W1", "kind": "iac", "repo_id": "repo-1"}]},
            "items": {"W1": {"attempts": [{"token": "t1"}]}},
            "active_attempt": {"token": "t1", "item_id": "W1"},
            "verification_proofs": {}, "verifier_proofs": {}}},
            "repositories": {"repo-1": {"location": str(self.cwd)}}}})
        evidence = {"id": "plan-1", "kind": "iac-plan", "passed": True, "cwd": str(self.cwd.resolve())}

        with self.assertRaises(WorkflowError):
            record_typed_proof(root, "run-1", "wrong", evidence)
        record_typed_proof(root, "run-1", "t1", evidence)

        saved = read_state(root)["data"]["runs"]["run-1"]
        self.assertEqual(saved["verification_proofs"]["plan-1"]["token"], "t1")
        self.assertNotIn("plan-1", saved["verifier_proofs"])


if __name__ == "__main__":
    unittest.main()
