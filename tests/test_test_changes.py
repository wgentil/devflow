import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.store import read_state, transact


class TestChangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "devflow@example.test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Devflow Test"], cwd=self.repo, check=True)
        (self.repo / "tests").mkdir()
        self.source = self.repo / "tests/test_locked.py"
        self.source.write_text("def test_locked():\n    assert 1 == 1\n")
        subprocess.run(["git", "add", "tests/test_locked.py"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        self.before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.run = {"id": "run-1", "plan": {"work_items": [{"id": "W1"}]}, "verification_proofs": {"red-1": {
            "id": "red-1", "phase": "RED", "passed": True, "item_id": "W1", "token": "attempt-1",
            "test_hashes": {"tests/test_locked.py": self.before}}}}
        self.patch = """diff --git a/tests/test_locked.py b/tests/test_locked.py
index 0000000..0000000 100644
--- a/tests/test_locked.py
+++ b/tests/test_locked.py
@@ -1,2 +1,2 @@
 def test_locked():
-    assert 1 == 1
+    assert 1 == 2
"""

    def tearDown(self):
        self.temp.cleanup()

    def module(self):
        spec = importlib.util.find_spec("workflow_lib.test_changes")
        self.assertIsNotNone(spec, "test change proposals must be implemented")
        from workflow_lib.test_changes import propose_test_change, approve_test_change, apply_approved_patch
        return propose_test_change, approve_test_change, apply_approved_patch

    def test_proposal_rejects_unlocked_and_structural_changes(self):
        propose, _, _ = self.module()
        unlocked = self.patch.replace("tests/test_locked.py", "src/app.py")
        structural = self.patch.replace("--- a/tests/test_locked.py", "--- /dev/null").replace(
            "+++ b/tests/test_locked.py", "+++ b/tests/test_locked.py")

        with self.assertRaises(ValueError):
            propose(self.run, "W1", unlocked, "test was wrong", self.repo)
        with self.assertRaises(ValueError):
            propose(self.run, "W1", structural, "replace the test", self.repo)
        self.assertEqual(self.source.read_text(), "def test_locked():\n    assert 1 == 1\n")

    def test_exact_approval_precedes_patch_application_and_records_hashes(self):
        propose, approve, apply = self.module()
        proposal = propose(self.run, "W1", self.patch, "expect the corrected behavior", self.repo)

        with self.assertRaises(ValueError):
            approve(proposal, "wrong-hash", "human-1")
        approval = approve(proposal, proposal["proposal_hash"], "human-1")
        result = apply(self.repo, proposal, approval)

        self.assertEqual(self.source.read_text(), "def test_locked():\n    assert 1 == 2\n")
        self.assertEqual(proposal["before_hashes"], {"tests/test_locked.py": self.before})
        self.assertEqual(len(result["after_hashes"]["tests/test_locked.py"]), 64)
        replay = apply(self.repo, proposal, approval)
        self.assertEqual(replay["after_hashes"], result["after_hashes"])

    def test_edited_test_preimage_blocks_an_approved_patch(self):
        propose, approve, apply = self.module()
        proposal = propose(self.run, "W1", self.patch, "expect the corrected behavior", self.repo)
        approval = approve(proposal, proposal["proposal_hash"], "human-1")
        self.source.write_text("def test_locked():\n    assert 1 == 3\n")

        with self.assertRaises(ValueError):
            apply(self.repo, proposal, approval)
        self.assertIn("assert 1 == 3", self.source.read_text())

    def test_applied_change_marks_every_dependent_green_proof_stale(self):
        propose, approve, apply = self.module()
        proposal = propose(self.run, "W1", self.patch, "correct expected behavior", self.repo)
        approval = approve(proposal, proposal["proposal_hash"], "human-1")
        result = apply(self.repo, proposal, approval)
        green = {"id": "green-1", "phase": "GREEN", "passed": True, "item_id": "W1",
                 "token": "attempt-1", "test_hashes": {"tests/test_locked.py": self.before},
                 "ruling": "historical ruling"}
        root = Path(self.temp.name) / "control"
        transact(root, 0, "fixture", {"kind": "fixture", "payload": {"runs": {
            "run-1": {"id": "run-1", "verification_proofs": {"green-1": green},
                      "verifier_proofs": {"green-1": {"passed": True}},
                      "test_change_proposals": {proposal["id"]: {**proposal, "approval": approval,
                                                                    "status": "approved"}}},
            "run-2": {"id": "run-2", "verification_proofs": {"green-2": {
                **green, "id": "green-2"}}, "verifier_proofs": {"green-2": {"passed": True}}}}}})
        state = read_state(root)
        transact(root, state["version"], "begin", {"kind": "test.change.applying", "payload": {
            "run_id": "run-1", "proposal_id": proposal["id"]}})
        state = read_state(root)
        transact(root, state["version"], "apply", {"kind": "test.change.applied", "payload": {
            "run_id": "run-1", "proposal_id": proposal["id"], "after_hashes": result["after_hashes"]}})
        saved = read_state(root)["data"]["runs"]
        self.assertFalse(saved["run-1"]["verification_proofs"]["green-1"]["fresh"])
        self.assertFalse(saved["run-2"]["verification_proofs"]["green-2"]["fresh"])
        self.assertFalse(saved["run-1"]["verifier_proofs"]["green-1"]["passed"])
        self.assertEqual(saved["run-1"]["verification_proofs"]["green-1"]["ruling"], "historical ruling")


if __name__ == "__main__":
    unittest.main()
