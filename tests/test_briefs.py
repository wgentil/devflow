import json
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.briefs import assemble_brief
from workflow_lib.store import WorkflowError


def fixture():
    item = lambda item_id: {"id": item_id, "kind": "code", "requirement_ids": ["R1"],
        "acceptance_criteria": ["preserves behavior"], "dependencies": []}
    run = {"id": "run-7", "state_version": 4, "plan": {"work_items": [item("W1"), item("W2"),
        {"id": "W3", "kind": "iac", "requirement_ids": ["R2"], "acceptance_criteria": ["policy passes"], "dependencies": ["W1"]}]},
        "items": {"W1": {"status": "pending"}, "W2": {"status": "pending"}, "W3": {"status": "pending"}},
        "active_attempt": None,
        "unavailable_gates": ["review", "delivery"], "artifacts": {"spec": "sha256:abc"}}
    context = {"values": {"platform": "macOS", "architecture": "layered", "unrelated": "omit"},
               "provenance": {"platform": "user", "architecture": "project"},
               "declined": [{"slice": "unrelated", "reason": "skip"}],
               "conflicts": [{"slice": "platform", "sealed_value": "linux", "selected_value": "macOS"}],
               "budget": {"estimated_tokens": 10, "exceeded": False, "method": "fixture estimate"}}
    stage = {"name": "build", "required_slices": ["platform"], "optional_slices": ["architecture"],
        "instructions": "Implement the selected work.", "kind_instructions": {"code": "Run focused tests.",
        "iac": "Review policy.", "agent-config": "Run evals."}, "required_artifacts": ["spec"]}
    return run, context, stage


def actual_size(value):
    return len(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


class BriefTests(unittest.TestCase):
    def test_brief_scopes_context_items_and_kind_instructions(self):
        run, context, stage = fixture()
        brief = assemble_brief(run, context, stage, ["W1", "W2"], 10000)
        self.assertEqual(brief["context"]["values"], {"platform": "macOS", "architecture": "layered"})
        self.assertEqual(brief["context"]["conflicts"][0]["slice"], "platform")
        self.assertEqual(brief["context"]["declined"], [])
        self.assertEqual(brief["context"]["budget"]["method"], "fixture estimate")
        self.assertEqual([item["id"] for item in brief["work_items"]], ["W1", "W2"])
        self.assertEqual(brief["instructions"]["kind"], {"code": "Run focused tests."})
        self.assertEqual(brief["artifacts"], {"spec": "sha256:abc"})
        self.assertIsNone(brief["attempt_id"])
        self.assertIn("review", brief["unavailable_gates"])

    def test_blocked_or_unknown_item_is_rejected(self):
        run, context, stage = fixture()
        with self.assertRaises(WorkflowError) as caught:
            assemble_brief(run, context, stage, ["W3"], 10000)
        self.assertEqual(caught.exception.code, "ITEM_INELIGIBLE")

    def test_brief_size_is_exact_utf8_and_exact_size_limit_succeeds(self):
        run, context, stage = fixture()
        context["values"]["platform"] = "東京🛰️"
        max_bytes = 100000
        for _ in range(8):
            brief = assemble_brief(run, context, stage, ["W1"], max_bytes)
            measured = actual_size(brief)
            self.assertEqual(brief["budget"]["serialized_bytes"], measured)
            max_bytes = measured
        exact = assemble_brief(run, context, stage, ["W1"], max_bytes)
        self.assertEqual(exact["budget"]["serialized_bytes"], max_bytes)
        self.assertIn("estimate", exact["budget"]["token_estimate_method"])

    def test_overflow_reports_mandatory_size_and_artifact_references(self):
        run, context, stage = fixture()
        with self.assertRaises(WorkflowError) as caught:
            assemble_brief(run, context, stage, ["W1"], 100)
        self.assertEqual(caught.exception.code, "BRIEF_BUDGET_EXCEEDED")
        self.assertGreater(caught.exception.details["required_bytes"], 100)
        self.assertEqual(caught.exception.details["artifact_refs"], {"spec": "sha256:abc"})

    def test_optional_slices_are_named_when_omitted(self):
        run, context, stage = fixture()
        full = assemble_brief(run, context, stage, ["W1"], 10000)
        limit = full["budget"]["serialized_bytes"] - len("layered".encode())
        brief = assemble_brief(run, context, stage, ["W1"], limit)
        self.assertIn("architecture", brief["budget"]["optional_omitted"])
        self.assertNotIn("architecture", brief["context"]["values"])

    def test_fixture_records_combined_and_separate_read_bytes(self):
        run, context, stage = fixture()
        brief = assemble_brief(run, context, stage, ["W1"], 10000)
        separate_responses = [
            {"eligible_work_items": brief["work_items"]},
            {"context": brief["context"]},
            {"artifacts": brief["artifacts"]},
            {key: brief[key] for key in ("run_id", "stage", "attempt_id", "instructions", "authorization_scope",
                                         "unresolved_findings", "unavailable_gates", "budget")},
        ]
        separate_bytes = sum(actual_size(response) for response in separate_responses)
        brief_bytes = brief["budget"]["serialized_bytes"]
        print(f"brief fixture: next=1 call/{brief_bytes} bytes; separate=4 calls/{separate_bytes} bytes")
        self.assertEqual(brief["work_items"], separate_responses[0]["eligible_work_items"])
        self.assertEqual(brief["context"], separate_responses[1]["context"])
        self.assertEqual(brief["artifacts"], separate_responses[2]["artifacts"])
        self.assertEqual(len(separate_responses), 4)


if __name__ == "__main__":
    unittest.main()
