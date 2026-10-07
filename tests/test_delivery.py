import importlib.util
from copy import deepcopy
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.test")
        self.git("config", "user.name", "Test")
        (self.repo / "app.py").write_text("VALUE = 1\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD")
        (self.repo / "app.py").write_text("VALUE = 2\n")
        self.git("commit", "-qam", "change\n\nWork-Item: W1")
        self.head = self.git("rev-parse", "HEAD")
        self.run = {"id": "run-1", "status": "active", "plan": {"spec_hash": "spec-1",
            "work_items": [{"id": "W1", "kind": "code", "requirement_ids": ["R1"]}]},
            "items": {"W1": {"status": "complete", "attempts": [{"token": "t1"}]}},
            "verification_proofs": {"green": {"kind": "code", "phase": "GREEN", "fresh": True}},
            "verifier_proofs": {"green": {"passed": True, "item_id": "W1", "token": "t1", "evidence_id": "green"}},
            "reviews": {"item": [{"item_id": "W1", "verdict": "pass", "fresh": True}],
                        "branch": [{"verdict": "pass", "fresh": True}]},
            "review_packages": {}, "acceptances": [{"complete": True, "fresh": True,
                "acceptance_hash": "accept-1"}], "unresolved_findings": [], "amendments": [],
            "adjudications": [], "owned_resources": []}

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True,
                              text=True).stdout.strip()

    def tearDown(self):
        self.temp.cleanup()

    def module(self):
        spec = importlib.util.find_spec("workflow_lib.delivery")
        self.assertIsNotNone(spec, "canonical delivery manifests must be implemented")
        from workflow_lib.delivery import prepare_delivery, verify_delivery, record_delivery
        return prepare_delivery, verify_delivery, record_delivery

    def repos(self):
        return {"repo-1": {"location": str(self.repo), "base": self.base, "head": self.head}}

    def test_stale_head_and_manifest_authorization_fail_before_actions(self):
        prepare, verify, _ = self.module()
        manifest = prepare(self.run, self.repos(), "retained-branch")
        with self.assertRaises(ValueError):
            verify(self.run, manifest, "wrong-hash", self.repos())
        (self.repo / "app.py").write_text("VALUE = 3\n")
        with self.assertRaises(ValueError):
            verify(self.run, manifest, manifest["manifest_hash"], self.repos())

    def test_terminal_outcomes_are_bound_to_authorization_and_run_without_issue_group(self):
        prepare, verify, record = self.module()
        manifest = prepare(self.run, self.repos(), "retained-branch")
        checked = verify(self.run, manifest, manifest["manifest_hash"], self.repos())
        result = {"authorization": {"approved": True, "actor_id": "owner", "manifest_hash": manifest["manifest_hash"],
                     "action": "delivery.retained-branch"}, "outcome": "retained-branch",
                  "repository_heads": {"repo-1": self.head}}
        terminal = record(self.run, checked, result)
        self.assertEqual(terminal["status"], "delivered")
        self.assertEqual(terminal["delivery"]["outcome"], "retained-branch")
        self.assertNotIn("issue_group", terminal)
        with self.assertRaises(ValueError):
            record(terminal, checked, result)

    def test_local_merge_pull_request_and_retention_records_replay_for_standalone_runs(self):
        prepare, verify, record = self.module()
        from workflow_lib.store import read_state, transact
        for outcome in ("local-merge", "pull-request", "retained-branch"):
            run = deepcopy(self.run)
            manifest = prepare(run, self.repos(), outcome)
            checked = verify(run, manifest, manifest["manifest_hash"], self.repos())
            result = {"authorization": {"approved": True, "actor_id": "owner",
                    "manifest_hash": manifest["manifest_hash"], "action": "delivery." + outcome},
                "outcome": outcome, "repository_heads": {"repo-1": self.head}}
            if outcome == "local-merge":
                result["merge_commits"] = {"repo-1": self.head}
            elif outcome == "pull-request":
                result["pull_request"] = {"id": "PR-1", "url": "https://example.test/pr/1"}
            terminal = record(run, checked, result)
            root = Path(self.temp.name) / ("control-" + outcome)
            transact(root, 0, "fixture", {"kind": "fixture", "payload": {"runs": {"run-1": run}}})
            state = read_state(root)
            transact(root, state["version"], "delivery", {"kind": "delivery.recorded", "payload": {
                "run_id": "run-1", "delivery": terminal["delivery"]}})
            saved = read_state(root)["data"]["runs"]["run-1"]
            self.assertEqual(saved["status"], "delivered")
            self.assertEqual(saved["delivery"]["outcome"], outcome)

    def test_cleanup_requires_run_owned_resources_and_multi_repo_manifest_is_complete(self):
        prepare, _, _ = self.module()
        self.run["owned_resources"] = [{"kind": "branch", "name": "user-work", "owner_run_id": "someone-else"}]
        with self.assertRaises(ValueError):
            prepare(self.run, self.repos(), "local-merge")
        with self.assertRaises(ValueError):
            prepare(self.run, {**self.repos(), "repo-2": {"location": str(self.repo),
                "base": self.base, "head": "0" * 40}}, "retained-branch")


if __name__ == "__main__":
    unittest.main()
