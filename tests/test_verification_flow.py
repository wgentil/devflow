import json
import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "skills/workflow/scripts/run.py"


class VerificationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.control = self.root / "control"
        self.repo = self.root / "repo with spaces"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "flow@example.test")
        self.git("config", "user.name", "Flow Test")
        (self.repo / "tests").mkdir()
        (self.repo / "app.py").write_text("VALUE = 1\n")
        (self.repo / "tests/test_feature.py").write_text("from app import VALUE\n\ndef test_feature():\n    assert VALUE == 2\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture base")
        self.base = self.git("rev-parse", "HEAD")

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True,
                              text=True).stdout.strip()

    def cli(self, *args, expected=0):
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run([sys.executable, str(ENTRY), *map(str, args)], cwd=ROOT, env=environment,
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value))
        return path

    def test_end_to_end_code_gate_review_acceptance_and_delivery_preparation(self):
        self.cli("repo", "register", "--root", self.control, "--repo-id", "service", "--location", self.repo)
        spec = {"mode": "new", "requirements": [{"id": "R1", "text": "feature returns its accepted value",
            "acceptance_criteria": ["target test passes"], "provenance": {"kind": "authored"}}]}
        spec_path = self.write_json("spec.json", spec)
        self.cli("spec", "store", "--root", self.control, "--file", spec_path)
        digest = self.cli("spec", "validate", "--file", spec_path)["content_hash"]
        self.cli("spec", "approve", "--root", self.control, "--confirm-hash", digest, "--actor-id", "owner")
        plan = {"spec_hash": digest, "work_items": [{"id": "W1", "kind": "code", "repo_id": "service",
            "requirement_ids": ["R1"], "dependencies": [],
            "acceptance_criteria": [{"kind": "code-test", "text": "test_feature passes"}]}]}
        plan_path = self.write_json("plan.json", plan)
        self.cli("plan", "validate", "--root", self.control, "--file", plan_path)
        self.cli("run", "start", "--root", self.control, "--run-id", "flow-1", "--actor-id", "implementer")
        attempt = self.cli("run", "next", "--root", self.control, "--run-id", "flow-1")["attempt_id"]
        runner = ("import json,runpy,sys; sys.dont_write_bytecode=True; sys.path.insert(0,'.'); outcome='passed'; "
                  "ns=runpy.run_path('tests/test_feature.py'); "
                  "exec(\"try:\\n ns['test_feature']()\\nexcept AssertionError:\\n outcome='failed'\"); "
                  "print(json.dumps({'tests':[{'id':'test_feature','outcome':outcome}]})); "
                  "sys.exit(0 if outcome=='passed' else 1)")
        command = json.dumps([sys.executable, "-c", runner])
        red = self.cli("build", "verify", "--root", self.control, "--run-id", "flow-1", "--attempt-id", attempt,
            "--phase", "red", "--argv-json", command, "--test-path", "tests/test_feature.py",
            "--target-id", "test_feature")
        self.assertEqual(red["phase"], "RED")
        (self.repo / "app.py").write_text("VALUE = 2\n")
        self.git("add", "app.py")
        self.git("commit", "-m", "implement accepted value\n\nWork-Item: W1")
        head = self.git("rev-parse", "HEAD")
        green = self.cli("build", "verify", "--root", self.control, "--run-id", "flow-1", "--attempt-id", attempt,
            "--phase", "green", "--argv-json", command, "--test-path", "tests/test_feature.py",
            "--target-id", "test_feature")
        self.cli("run", "result", "--root", self.control, "--run-id", "flow-1", "--attempt-id", attempt,
                 "--result", json.dumps({"outcome": "passed", "verifier_proof_id": green["id"]}))
        repositories = {"service": {"location": str(self.repo), "base": self.base, "head": head}}
        item_package = self.cli("review", "package", "--root", self.control, "--run-id", "flow-1", "--role", "item",
                                "--repositories-json", json.dumps(repositories))["package"]
        self.record_review(item_package, "item-reviewer", "item", item_id="W1")
        branch_package = self.cli("review", "package", "--root", self.control, "--run-id", "flow-1", "--role", "branch",
                                  "--repositories-json", json.dumps(repositories))["package"]
        self.record_review(branch_package, "branch-reviewer", "branch")
        acceptance_package = self.cli("review", "package", "--root", self.control, "--run-id", "flow-1",
                                      "--role", "acceptance", "--repositories-json", json.dumps(repositories))["package"]
        self.record_review(acceptance_package, "acceptance-reviewer", "acceptance")
        snapshot = {"service": {"location": str(self.repo), "head": head, "changed_paths": ["app.py"]}}
        accepted = self.cli("run", "accept", "--root", self.control, "--run-id", "flow-1",
            "--report-json", json.dumps({"package_hash": acceptance_package["package_hash"], "requirements": [
                {"id": "R1", "verdict": "MET", "citations": [{"repo_id": "service", "path": "app.py", "line": 1}]}]}),
            "--repositories-json", json.dumps(snapshot))
        self.assertTrue(accepted["complete"])
        before = len(list((self.control / "events").glob("*.json")))
        manifest = self.cli("delivery", "prepare", "--root", self.control, "--run-id", "flow-1",
            "--repositories-json", json.dumps(repositories), "--outcome", "retained-branch")
        after = len(list((self.control / "events").glob("*.json")))
        self.assertEqual(before, after, "delivery preparation must be read-only")
        self.assertEqual(manifest["repositories"]["service"]["head"], head)
        self.assertEqual(manifest["acceptance_hash"], accepted["acceptance_hash"])
        self.assertEqual(manifest["unresolved_findings"], [])
        self.assertEqual(self.cli("run", "gate-status", "--root", self.control, "--run-id", "flow-1")["stage"], "delivery")

    def record_review(self, package, actor, role, item_id=None):
        report = {"package_hash": package["package_hash"], "verdict": "pass", "findings": []}
        if item_id:
            report["item_id"] = item_id
        self.cli("review", "record", "--root", self.control, "--run-id", "flow-1",
            "--package-hash", package["package_hash"], "--actor-id", actor,
            "--invocation-ref", f"codex://{actor}", "--tool-available", "--report-json", json.dumps(report))

    def test_devconsole_selected_outcomes_fixture(self):
        fixture = json.loads((ROOT / "tests/fixtures/devconsole-outcomes.json").read_text())
        self.assertEqual([entry["capability"] for entry in fixture["comparisons"]],
                         ["stale attempt token", "locked test change", "delivery summary"])
        names = {node.name for source in (ROOT / "tests").rglob("test_*.py")
                 for node in ast.walk(ast.parse(source.read_text()))
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")}
        for item in fixture["comparisons"]:
            self.assertIn(item["devflow_test"], names)


if __name__ == "__main__":
    unittest.main()
