import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.runs import abandon_attempt, issue_attempt, record_result, run_summary, start_run
from workflow_lib.specs import approval_record, content_hash
from workflow_lib.store import WorkflowError


def state():
    spec = {"mode": "new", "requirements": [
        {"id": "R1", "text": "One", "acceptance_criteria": ["one"], "provenance": {"kind": "authored"}},
        {"id": "R2", "text": "Two", "acceptance_criteria": ["two"], "provenance": {"kind": "authored"}},
    ]}
    digest = content_hash(spec)
    plan = {"spec_hash": digest, "work_items": [
        {"id": "W1", "kind": "code", "requirement_ids": ["R1"], "dependencies": [],
         "acceptance_criteria": [{"kind": "code-test", "text": "test one"}]},
        {"id": "W2", "kind": "code", "requirement_ids": ["R2"], "dependencies": ["W1"],
         "acceptance_criteria": [{"kind": "code-test", "text": "test two"}]},
    ]}
    return {"spec": spec, "approval": approval_record(spec, digest), "plan": plan,
            "plan_validation": {"valid": True, "spec_hash": digest}}


class RunTests(unittest.TestCase):
    def setUp(self):
        self.run = start_run(state(), "run-1", state()["plan"])

    def test_stale_and_single_use_tokens_reject_mutation(self):
        issued = issue_attempt(self.run, "W1")
        token = issued["active_attempt"]["token"]
        stale = {**issued, "state_version": issued["state_version"] + 1}
        with self.assertRaises(WorkflowError) as caught:
            record_result(stale, token, {"outcome": "failed"})
        self.assertEqual(caught.exception.code, "STALE_ATTEMPT")
        recorded = record_result(issued, token, {"outcome": "failed"})
        with self.assertRaises(WorkflowError) as caught:
            record_result(recorded, token, {"outcome": "passed"})
        self.assertEqual(caught.exception.code, "ATTEMPT_TOKEN_INVALID")

    def test_abandoned_attempt_is_preserved_and_retry_gets_new_token(self):
        issued = issue_attempt(self.run, "W1")
        old_token = issued["active_attempt"]["token"]
        abandoned = abandon_attempt(issued, old_token)
        retried = issue_attempt(abandoned, "W1")
        self.assertEqual(abandoned["items"]["W1"]["attempts"][0]["status"], "abandoned")
        self.assertNotEqual(retried["active_attempt"]["token"], old_token)

    def test_blocked_dependencies_stay_ineligible(self):
        with self.assertRaises(WorkflowError) as caught:
            issue_attempt(self.run, "W2")
        self.assertEqual(caught.exception.code, "ITEM_INELIGIBLE")

    def test_unverified_result_does_not_complete_code_item(self):
        issued = issue_attempt(self.run, "W1")
        with self.assertRaises(WorkflowError) as caught:
            record_result(issued, issued["active_attempt"]["token"], {"outcome": "passed"})
        self.assertEqual(caught.exception.code, 'VERIFIER_PROOF_REQUIRED')
        self.assertEqual(issued['active_attempt']['item_id'],'W1')
        with self.assertRaises(WorkflowError) as caught:
            issue_attempt(issued, "W2")
        self.assertEqual(caught.exception.code, "ATTEMPT_ACTIVE")

    def test_passing_proof_cannot_override_a_failed_result(self):
        issued = issue_attempt(self.run, "W1")
        token = issued["active_attempt"]["token"]
        issued["verifier_proofs"]["proof-1"] = {"passed": True, "item_id": "W1", "token": token}
        with self.assertRaises(WorkflowError) as caught:
            record_result(issued, token, {"outcome": "failed", "verifier_proof_id": "proof-1"})
        self.assertEqual(caught.exception.code, "VERIFIER_PROOF_MISMATCH")

    def test_code_green_proof_cannot_complete_iac_work(self):
        data = state()
        plan = {**data["plan"], "work_items": [{"id": "W1", "kind": "iac", "requirement_ids": ["R1"],
            "dependencies": [], "acceptance_criteria": [{"kind": "iac-plan-policy", "text": "plan"},
            {"kind": "iac-apply-policy", "text": "apply"}]}, {**data["plan"]["work_items"][1],
                "requirement_ids": ["R2"], "dependencies": ["W1"]}]}
        data["plan"] = plan
        data["plan_validation"] = {"valid": True, "spec_hash": plan["spec_hash"]}
        run = start_run(data, "run-iac", plan)
        issued = issue_attempt(run, "W1")
        token = issued["active_attempt"]["token"]
        issued["verification_proofs"] = {"green": {"id": "green", "kind": "code", "phase": "GREEN"}}
        issued["verifier_proofs"] = {"green": {"passed": True, "item_id": "W1", "token": token,
                                               "evidence_id": "green"}}
        with self.assertRaises(WorkflowError) as caught:
            record_result(issued, token, {"outcome": "passed", "verifier_proof_id": "green"})
        self.assertEqual(caught.exception.code, "VERIFIER_PROOF_MISMATCH")

    def test_summary_reports_unavailable_gates(self):
        summary = run_summary(self.run)
        self.assertEqual(summary["status"], "active")
        self.assertNotIn("build", summary["unavailable_gates"])
        self.assertIn("hardening", summary["unavailable_gates"])
        self.assertIn("delivery", summary["unavailable_gates"])
        self.assertEqual(summary["completed_items"], [])

    def test_start_rejects_plan_after_specification_changes(self):
        changed = state()
        changed["spec"]["requirements"][0]["text"] = "Different"
        with self.assertRaises(WorkflowError) as caught:
            start_run(changed, "run-stale", changed["plan"])
        self.assertEqual(caught.exception.code, "PLAN_STALE")


if __name__ == "__main__":
    unittest.main()
