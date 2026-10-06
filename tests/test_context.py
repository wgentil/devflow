import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.context import (ORG_SLICES, org_slices_to_interview, register_repo,
                                  resolve_context, resolve_context_cached)
from workflow_lib.store import WorkflowError


class ContextTests(unittest.TestCase):
    def test_six_org_slices_and_answered_or_declined_slices_are_reused(self):
        self.assertEqual(ORG_SLICES, (
            "platform", "coding-standards", "architecture", "test-strategy", "release-process", "design-system"
        ))
        org = {"slices": {
            "platform": {"status": "answered", "value": "macOS"},
            "architecture": {"status": "declined", "reason": "not decided"},
        }}
        self.assertEqual(org_slices_to_interview(org), [
            "coding-standards", "test-strategy", "release-process", "design-system"
        ])

    def test_project_and_user_precedence_reports_provenance_and_sealed_conflict(self):
        org = {"slices": {"platform": {"status": "answered", "value": "linux", "sealed": True}}}
        project = {"slices": {"platform": {"status": "answered", "value": "macOS"},
                              "architecture": {"status": "answered", "value": "ports and adapters"}}}
        result = resolve_context(org, project, {"platform": "windows"}, {"max_tokens": 100})
        self.assertEqual(result["values"], {"platform": "windows", "architecture": "ports and adapters"})
        self.assertEqual(result["provenance"], {"platform": "user", "architecture": "project"})
        self.assertEqual(result["conflicts"], [{"slice": "platform", "sealed_value": "linux", "selected_value": "windows", "selected_from": "user"}])

    def test_declines_and_budget_overruns_remain_explicit_estimates(self):
        org = {"slices": {"release-process": {"status": "declined", "reason": "prototype"}}}
        project = {"slices": {"architecture": {"status": "answered", "value": "A fairly long architecture description"}}}
        result = resolve_context(org, project, {}, {"max_tokens": 1})
        self.assertEqual(result["declined"], [{"slice": "release-process", "reason": "prototype", "source": "organization"}])
        self.assertGreater(result["budget"]["estimated_tokens"], 1)
        self.assertTrue(result["budget"]["exceeded"])
        self.assertIn("estimate", result["budget"]["method"])

    def test_repo_relocation_keeps_id_and_artifact_references_with_spaced_path(self):
        state = {"repositories": {"backend": {"location": "/old/path", "artifact_refs": ["src/a.py"]}}}
        with tempfile.TemporaryDirectory(prefix="repo with spaces ") as folder:
            result = register_repo(state, "backend", folder)
            self.assertEqual(result["repositories"]["backend"]["location"], str(Path(folder).resolve()))
            self.assertEqual(result["repositories"]["backend"]["artifact_refs"], ["src/a.py"])
            with self.assertRaises(WorkflowError) as caught:
                register_repo(result, "new", str(Path(folder) / "missing"))
            self.assertEqual(caught.exception.code, "REPO_LOCATION_NOT_FOUND")
            self.assertEqual(result["repositories"]["backend"]["location"], str(Path(folder).resolve()))

    def test_projection_reuse_and_invalidation_keep_context_provenance(self):
        org = {"slices": {"platform": {"status": "answered", "value": "linux", "sealed": True},
                          "release-process": {"status": "declined", "reason": "TBD"}}}
        project = {"slices": {"architecture": {"status": "answered", "value": "layered"}}}
        overrides = {"platform": "macOS"}
        cache = {}
        first = resolve_context_cached(org, project, overrides, {"max_tokens": 50}, cache,
                                       {"org": "h1", "project": "h2"}, "resolver-1")
        self.assertFalse(first["cache_hit"])
        second = resolve_context_cached(org, project, overrides, {"max_tokens": 50}, cache,
                                        {"org": "h1", "project": "h2"}, "resolver-1")
        self.assertTrue(second["cache_hit"])
        self.assertEqual(second["resolved"]["values"]["platform"], "macOS")
        self.assertEqual(second["resolved"]["provenance"]["platform"], "user")
        self.assertEqual(second["resolved"]["declined"][0]["reason"], "TBD")
        self.assertEqual(second["resolved"]["conflicts"][0]["sealed_value"], "linux")
        self.assertFalse(resolve_context_cached(org, project, overrides, {"max_tokens": 50}, cache,
                          {"org": "changed", "project": "h2"}, "resolver-1")["cache_hit"])
        self.assertFalse(resolve_context_cached(org, project, overrides, {"max_tokens": 50}, cache,
                          {"org": "h1", "project": "h2"}, "resolver-2")["cache_hit"])


if __name__ == "__main__":
    unittest.main()
