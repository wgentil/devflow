import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "devflow@example.test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Devflow Test"], cwd=self.repo, check=True)
        (self.repo / "src").mkdir()
        (self.repo / "src/app.py").write_text("VALUE = 1\n")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.repo, check=True)
        self.base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, check=True,
                                   capture_output=True, text=True).stdout.strip()
        (self.repo / "src/app.py").write_text("VALUE = 2\n")
        subprocess.run(["git", "commit", "-qam", "fix value\n\nWork-Item: W1"], cwd=self.repo, check=True)
        (self.repo / "src/app.py").write_text("VALUE = 3\n")
        subprocess.run(["git", "commit", "-qam", "unattributed tweak"], cwd=self.repo, check=True)
        self.head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, check=True,
                                   capture_output=True, text=True).stdout.strip()
        self.run = {"id": "run-1", "actors": {"implementer": "impl"},
                    "plan": {"spec_hash": "spec", "work_items": [{"id": "W1", "kind": "code",
                      "requirement_ids": ["R1"], "acceptance_criteria": []}]},
                    "items": {"W1": {"attempts": [{"token": "t1"}]}},
                    "artifacts": {"result": {"sha256": "a" * 64}}}

    def tearDown(self):
        self.temp.cleanup()

    def module(self):
        spec = importlib.util.find_spec("workflow_lib.reviews")
        self.assertIsNotNone(spec, "review packages must be implemented")
        from workflow_lib.reviews import prepare_review, record_review, correction_impact
        return prepare_review, record_review, correction_impact

    def test_commit_attribution_and_unattributed_changes_are_in_package(self):
        prepare, _, _ = self.module()
        package = prepare(self.run, "branch", {"repo-1": {"location": str(self.repo),
                         "base": self.base, "head": self.head}})
        self.run.setdefault("review_packages", {})[package["package_hash"]] = package
        self.assertEqual(len(package["repositories"]["repo-1"]["commits"]), 2)
        self.assertEqual(package["repositories"]["repo-1"]["commits"][0]["work_item_ids"], ["W1"])
        self.assertEqual(package["repositories"]["repo-1"]["unattributed_changes"], [self.head])
        self.assertEqual(package["artifacts"]["result"]["sha256"], "a" * 64)

    def test_same_actor_and_stale_package_are_rejected(self):
        prepare, record, _ = self.module()
        package = prepare(self.run, "item", {"repo-1": {"location": str(self.repo),
                         "base": self.base, "head": self.head}}, [{"item_id": "W1", "id": "F1"}])
        self.run.setdefault("review_packages", {})[package["package_hash"]] = package
        report = {"package_hash": package["package_hash"], "verdict": "pass", "findings": [], "item_id": "W1"}
        with self.assertRaises(ValueError):
            record(self.run, package["package_hash"], {"role": "item", "actor_id": "impl", "tool_available": True,
                   "invocation_ref": "codex://review-1"}, report)
        self.repo.joinpath("src/app.py").write_text("VALUE = 4\n")
        with self.assertRaises(ValueError):
            record(self.run, package["package_hash"], {"role": "item", "actor_id": "reviewer",
                   "tool_available": True, "invocation_ref": "codex://review-2"}, report)

    def test_correction_limits_and_unknown_impact(self):
        prepare, _, impact = self.module()
        package = prepare(self.run, "item", {"repo-1": {"location": str(self.repo),
                         "base": self.base, "head": self.head}})
        self.run.setdefault("review_packages", {})[package["package_hash"]] = package
        run = {**self.run, "reviews": {"item": [{"package_hash": package["package_hash"],
            "correction_round": n, "verdict": "request-changes", "item_id": "W1"} for n in range(1, 5)]}}
        self.assertTrue(impact(run, ["unknown/path.py"])["invalidate_all"])
        with self.assertRaises(ValueError):
            from workflow_lib.reviews import record_review
            record_review(run, package["package_hash"], {"role": "item", "actor_id": "reviewer",
                "tool_available": True, "invocation_ref": "codex://review-2"}, {"package_hash": package["package_hash"],
                "verdict": "request-changes", "findings": [{"id": "F1", "severity": "minor",
                    "path": "src/app.py", "line": 1}], "item_id": "W1"})

    def test_package_and_judgment_are_journaled(self):
        prepare, record, _ = self.module()
        from workflow_lib.store import read_state, transact
        root = Path(self.temp.name) / "control"
        transact(root, 0, "run", {"kind": "fixture", "payload": {"runs": {"run-1": self.run}}})
        package = prepare(self.run, "item", {"repo-1": {"location": str(self.repo),
                         "base": self.base, "head": self.head}})
        state = read_state(root)
        transact(root, state["version"], "package", {"kind": "review.package.prepared",
            "payload": {"run_id": "run-1", "package": package}})
        run = read_state(root)["data"]["runs"]["run-1"]
        result = record(run, package["package_hash"], {"role": "item", "actor_id": "reviewer",
            "tool_available": True, "invocation_ref": "codex://review-1"},
            {"package_hash": package["package_hash"], "verdict": "pass", "findings": [], "item_id": "W1"})
        state = read_state(root)
        transact(root, state["version"], "review", {"kind": "review.recorded",
            "payload": {"run_id": "run-1", "review": result}})
        saved = read_state(root)["data"]["runs"]["run-1"]
        self.assertEqual(saved["reviews"]["item"][0]["actor_id"], "reviewer")
        self.assertIn(package["package_hash"], saved["review_packages"])

    def test_fifth_unresolved_item_correction_requires_independent_adjudication(self):
        _, _, _ = self.module()
        from workflow_lib.reviews import record_adjudication
        run = {**self.run, "reviews": {"item": [{"verdict": "request-changes", "item_id": "W1"}
            for _ in range(4)]}}
        decision = record_adjudication(run, "item", "adjudicator", "return",
                                       "needs evidence", "potential regression", "W1")
        self.assertEqual(decision["correction_rounds"], 4)
        with self.assertRaises(ValueError):
            record_adjudication(run, "branch", "impl", "approve", "accept", "bad", None)


if __name__ == "__main__":
    unittest.main()
