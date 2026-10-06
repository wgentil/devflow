import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.plans import ready_items, validate_plan
from workflow_lib.specs import approval_record, content_hash
from workflow_lib.store import WorkflowError


def approved_spec():
    value = {"mode": "new", "requirements": [{"id": "R1", "text": "Persist a value",
              "acceptance_criteria": ["survives restart"], "provenance": {"kind": "authored"}}]}
    value["approval"] = approval_record(value, content_hash(value))
    return value


def work_item(item_id="W1", reqs=None, deps=None, kind="code", criteria=None):
    allowed = {
        "code": [{"kind": "code-test", "text": "test persistence"}],
        "iac": [{"kind": "iac-plan-policy", "text": "plan policy"}, {"kind": "iac-apply-policy", "text": "apply policy"}],
        "agent-config": [{"kind": "agent-baseline-evaluation", "text": "baseline"}, {"kind": "agent-post-evaluation", "text": "post-change"}],
    }
    return {"id": item_id, "kind": kind, "requirement_ids": ["R1"] if reqs is None else reqs,
            "acceptance_criteria": allowed[kind] if criteria is None else criteria,
            "dependencies": [] if deps is None else deps}


def plan(items, spec=None):
    spec = approved_spec() if spec is None else spec
    return {"spec_hash": content_hash(spec), "work_items": items}


class PlanTests(unittest.TestCase):
    def test_duplicate_work_item_ids_are_rejected(self):
        with self.assertRaises(WorkflowError) as caught:
            validate_plan(approved_spec(), plan([work_item(), work_item()]))
        self.assertEqual(caught.exception.code, "DUPLICATE_WORK_ITEM_ID")

    def test_missing_dependency_is_rejected(self):
        with self.assertRaises(WorkflowError) as caught:
            validate_plan(approved_spec(), plan([work_item(deps=["absent"])]))
        self.assertEqual(caught.exception.code, "MISSING_DEPENDENCY")

    def test_dependency_cycle_is_rejected(self):
        items = [work_item("W1", deps=["W2"]), work_item("W2", deps=["W1"])]
        with self.assertRaises(WorkflowError) as caught:
            validate_plan(approved_spec(), plan(items))
        self.assertEqual(caught.exception.code, "DEPENDENCY_CYCLE")

    def test_uncovered_requirement_is_rejected(self):
        value = approved_spec()
        value["requirements"].append({"id": "R2", "text": "Audit", "acceptance_criteria": ["record exists"],
                                      "provenance": {"kind": "authored"}})
        value["approval"] = approval_record(value, content_hash(value))
        with self.assertRaises(WorkflowError) as caught:
            validate_plan(value, plan([work_item()], value))
        self.assertEqual(caught.exception.code, "UNCOVERED_REQUIREMENT")

    def test_kind_inappropriate_criteria_are_rejected(self):
        wrong = [{"kind": "iac-apply-policy", "text": "apply policy"}]
        with self.assertRaises(WorkflowError) as caught:
            validate_plan(approved_spec(), plan([work_item(kind="code", criteria=wrong)]))
        self.assertEqual(caught.exception.code, "KIND_CRITERIA_MISMATCH")

    def test_plan_requires_current_approved_spec_hash(self):
        value = approved_spec()
        changed = dict(value)
        changed["requirements"] = [{**value["requirements"][0], "text": "Changed"}]
        with self.assertRaises(WorkflowError) as caught:
            validate_plan(changed, plan([work_item()], changed))
        self.assertEqual(caught.exception.code, "SPEC_NOT_APPROVED")
        stale = plan([work_item()])
        stale["spec_hash"] = "0" * 64
        with self.assertRaises(WorkflowError) as caught:
            validate_plan(value, stale)
        self.assertEqual(caught.exception.code, "STALE_PLAN_SPEC")

    def test_ready_items_are_deterministic_and_wait_for_dependencies(self):
        items = [work_item("W3", deps=["W1"]), work_item("W2"), work_item("W1")]
        self.assertEqual([item["id"] for item in ready_items({"work_items": items}, set())], ["W1", "W2"])
        self.assertEqual([item["id"] for item in ready_items({"work_items": items}, {"W1"})], ["W2", "W3"])


if __name__ == "__main__":
    unittest.main()
