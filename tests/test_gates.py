import importlib.util
import tempfile
import subprocess
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "src/app.py").write_text("VALUE = 1\n")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.repo, check=True)
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, capture_output=True,
                              text=True, check=True).stdout.strip()
        (self.repo / "src/app.py").write_text("VALUE = 2\n")
        subprocess.run(["git", "commit", "-qam", "change"], cwd=self.repo, check=True)
        self.base = base
        self.head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, capture_output=True,
                                   text=True, check=True).stdout.strip()
        self.run = {"id": "r1", "status": "active", "plan": {"spec_hash": "s",
            "work_items": [{"id": "W1", "kind": "code", "requirement_ids": ["R1"],
                "acceptance_criteria": [{"kind": "code-test", "text": "test"}], "dependencies": []}]},
            "items": {"W1": {"status": "complete", "attempts": [{"token": "t1"}]}},
            "active_attempt": None, "verification_proofs": {}, "verifier_proofs": {},
            "reviews": {}, "review_packages": {}, "unresolved_findings": [], "acceptances": []}

    def tearDown(self):
        self.temp.cleanup()

    def module(self):
        spec = importlib.util.find_spec("workflow_lib.gates")
        self.assertIsNotNone(spec, "verified gates and acceptance must be implemented")
        from workflow_lib.gates import gate_status, accept_requirements, amend_item, discard_run
        return gate_status, accept_requirements, amend_item, discard_run

    def test_unbacked_pass_and_parked_mandatory_finding_cannot_advance(self):
        status, _, _, _ = self.module()
        self.run["items"]["W1"]["status"] = "pending"
        self.run["items"]["W1"]["attempts"][-1].update({"status": "result_recorded",
            "result": {"outcome": "passed"}})
        self.run["unresolved_findings"] = [{"id": "F1", "mandatory": True, "status": "parked"}]
        result = status(self.run)
        self.assertEqual(result["stage"], "implementation")
        self.assertFalse(result["can_advance"])

    def test_mandatory_waiver_requires_run_scoped_authorization(self):
        from workflow_lib.gates import park_finding, resolve_finding, waive_finding
        self.run["unresolved_findings"] = [{"id": "F1", "mandatory": True, "status": "open"}]
        parked = park_finding(self.run, "F1", {"actor_id": "owner", "why": "defer",
            "cost_if_wrong": "possible defect"})
        with self.assertRaises(ValueError):
            waive_finding(parked, "F1", {"approved": True, "finding_id": "F1", "run_id": "other",
                "scope": "R1", "actor_id": "owner", "reason": "waive"})
        waived = waive_finding(parked, "F1", {"approved": True, "finding_id": "F1", "run_id": "r1",
            "scope": "R1", "actor_id": "owner", "reason": "waive with acceptance"})
        self.assertEqual(waived["unresolved_findings"][0]["status"], "waived")
        self.assertEqual(__import__("workflow_lib.gates", fromlist=["gate_status"]).gate_status(waived)["blocking_findings"], [])
        resolved = resolve_finding(parked, "F1", "owner", "fixed in commit", ["commit:abc"])
        self.assertEqual(resolved["unresolved_findings"][0]["status"], "resolved")

    def test_acceptance_citations_and_previous_met_requirement_regression(self):
        _, accept, _, _ = self.module()
        from workflow_lib.reviews import prepare_review
        package = prepare_review(self.run, "acceptance", {"repo-1": {"location": str(self.repo),
            "base": self.base, "head": self.head}})
        self.run["review_packages"] = {package["package_hash"]: package}
        self.run["reviews"] = {"acceptance": [{"role": "acceptance", "package_hash": package["package_hash"],
            "verdict": "pass", "fresh": True}]}
        report = {"package_hash": package["package_hash"], "requirements": [{"id": "R1", "verdict": "MET",
                    "citations": [{"repo_id": "repo-1", "path": "src/app.py", "line": 1}]}]}
        snapshots = {"repo-1": {"location": str(self.repo), "changed_paths": ["src/app.py"], "head": self.head}}
        accepted = accept(self.run, report, snapshots)
        self.assertEqual(accepted["requirements"][0]["verdict"], "MET")
        from workflow_lib.store import read_state, transact
        root = Path(self.temp.name) / "acceptance-control"
        transact(root, 0, "fixture", {"kind": "fixture", "payload": {"runs": {"r1": self.run}}})
        state = read_state(root)
        transact(root, state["version"], "acceptance", {"kind": "acceptance.recorded", "payload": {
            "run_id": "r1", "acceptance": accepted}})
        self.assertTrue(read_state(root)["data"]["runs"]["r1"]["acceptances"][0]["complete"])
        regressed = {**self.run, "acceptances": [accepted]}
        report["requirements"][0]["verdict"] = "NOT MET"
        with self.assertRaises(ValueError):
            accept(regressed, report, snapshots)
        report["requirements"][0]["verdict"] = "MET"
        report["requirements"][0]["citations"][0]["path"] = "src/missing.py"
        self.assertEqual(accept(self.run, report, snapshots)["requirements"][0]["verdict"], "NOT MET")

    def test_amendment_is_atomic_preserves_history_invalidates_reviews_and_discard_is_terminal(self):
        _, _, amend, discard = self.module()
        item = {"id": "W1", "kind": "code", "requirement_ids": ["R1"],
            "acceptance_criteria": [{"kind": "code-test", "text": "updated"}], "dependencies": []}
        ruling = {"actor_id": "human-1", "decision": "approve", "why": "clarified",
                  "cost_if_wrong": "rework"}
        with self.assertRaises(ValueError):
            amend(self.run, "W1", item, {**ruling, "plan_hash": "stale"})
        self.assertNotIn("amendments", self.run)
        self.run["review_packages"] = {"p1": {"input_paths": ["src/app.py"]}}
        self.run["reviews"] = {"branch": [{"review_id": "rv1", "package_hash": "p1", "verdict": "pass"}]}
        from workflow_lib.reviews import _canonical
        import hashlib, json
        plan_hash = hashlib.sha256(_canonical(self.run["plan"]).encode()).hexdigest()
        changed = amend(self.run, "W1", item, {**ruling, "plan_hash": plan_hash, "spec_hash": "s"})
        self.assertEqual(changed["amendments"][0]["ruling"]["why"], "clarified")
        self.assertFalse(changed["reviews"]["branch"][0].get("fresh", True))
        terminal = discard(changed, "cancelled by owner", "human-1")
        self.assertEqual(terminal["status"], "discarded")
        self.assertEqual(terminal["discard_reason"], "cancelled by owner")

    def test_amendment_and_discard_events_replay_atomically(self):
        from workflow_lib.store import read_state, transact
        _, _, amend, _ = self.module()
        root = Path(self.temp.name) / "control"
        transact(root, 0, "fixture", {"kind": "fixture", "payload": {"runs": {"r1": self.run}}})
        item = {"id": "W1", "kind": "code", "requirement_ids": ["R1"],
            "acceptance_criteria": [{"kind": "code-test", "text": "updated"}], "dependencies": []}
        from workflow_lib.reviews import _canonical
        import hashlib
        ruling = {"actor_id": "human-1", "decision": "approve", "why": "clarified", "cost_if_wrong": "rework"}
        current = read_state(root)
        run = current["data"]["runs"]["r1"]
        plan_hash = hashlib.sha256(_canonical(run["plan"]).encode()).hexdigest()
        updated = amend(run, "W1", item, {**ruling, "plan_hash": plan_hash, "spec_hash": "s"})
        transact(root, current["version"], "amend", {"kind": "run.item.amended", "payload": {
            "run_id": "r1", "plan": updated["plan"], "amendment": updated["amendments"][-1]}})
        saved = read_state(root)["data"]["runs"]["r1"]
        self.assertEqual(len(saved["amendments"]), 1)
        self.assertEqual(saved["items"]["W1"]["status"], "pending")
        state = read_state(root)
        transact(root, state["version"], "discard", {"kind": "run.discarded", "payload": {
            "run_id": "r1", "reason": "owner cancelled", "actor_id": "human-1"}})
        terminal = read_state(root)["data"]["runs"]["r1"]
        self.assertEqual(terminal["status"], "discarded")
        self.assertEqual(terminal["discard_reason"], "owner cancelled")


if __name__ == "__main__":
    unittest.main()
