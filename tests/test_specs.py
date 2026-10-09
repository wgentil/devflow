import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.specs import approval_record, approval_status, find_gaps, render_spec, validate_spec
from workflow_lib.store import WorkflowError


def spec(mode="new"):
    return {"mode": mode, "title": "Example", "requirements": [
        {"id": "R1", "text": "Persist the user setting", "acceptance_criteria": ["setting survives restart"],
         "provenance": {"kind": "authored"}},
        {"id": "R2", "text": "Keep an explicit assumption", "acceptance_criteria": ["assumption is visible"],
         "provenance": {"kind": "assumed", "assumption": "single tenant"}},
    ], "gaps": [{"id": "G1", "question": "Which cloud?", "status": "unanswered"}]}


class SpecTests(unittest.TestCase):
    def test_duplicate_requirement_ids_are_rejected(self):
        value = spec()
        value["requirements"].append(dict(value["requirements"][0]))
        with self.assertRaises(WorkflowError) as caught:
            validate_spec(value)
        self.assertEqual(caught.exception.code, "DUPLICATE_REQUIREMENT_ID")

    def test_derived_requirement_requires_complete_source_citation(self):
        value = spec()
        value["requirements"][0]["provenance"] = {"kind": "derived", "sources": [{"path": "src/a.py"}]}
        with self.assertRaises(WorkflowError) as caught:
            validate_spec(value)
        self.assertEqual(caught.exception.code, "MISSING_DERIVED_CITATION")

    def test_unanswered_gaps_and_assumptions_are_preserved(self):
        value = spec()
        validate_spec(value)
        self.assertEqual(find_gaps(value), [{"id": "G1", "question": "Which cloud?", "status": "unanswered"}])
        rendered = render_spec(value)
        self.assertIn("single tenant", rendered)
        self.assertIn("G1", rendered)

    def test_diagram_is_rendered_from_authoritative_spec(self):
        value = spec()
        value["diagrams"] = [{"title": "Setting flow", "mermaid": "flowchart LR\n    Input --> Save"}]
        rendered = render_spec(value)
        self.assertIn("## Diagrams\n\n### Setting flow\n\n```mermaid\nflowchart LR\n    Input --> Save\n```", rendered)

    def test_diagram_cannot_break_markdown_fence(self):
        value = spec()
        value["diagrams"] = [{"title": "Bad", "mermaid": "flowchart LR\n```\nA --> B"}]
        with self.assertRaises(WorkflowError) as caught:
            validate_spec(value)
        self.assertEqual(caught.exception.code, "INVALID_SPEC_DIAGRAM")

    def test_supported_modes_validate(self):
        for mode in ("new", "extend", "migrate"):
            self.assertEqual(validate_spec(spec(mode))["mode"], mode)

    def test_approval_binds_exact_spec_content(self):
        value = spec()
        validation = validate_spec(value)
        with self.assertRaises(WorkflowError) as caught:
            approval_record(value)
        self.assertEqual(caught.exception.code, "EXPLICIT_CONFIRMATION_REQUIRED")
        record = approval_record(value, confirmed_hash=validation["content_hash"])
        self.assertTrue(approval_status(value, record)["approved"])
        changed = spec()
        changed["requirements"][0]["text"] = "Changed"
        self.assertFalse(approval_status(changed, record)["approved"])


if __name__ == "__main__":
    unittest.main()
