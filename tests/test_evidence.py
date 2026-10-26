import json
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.store import read_state, transact

ENTRY = Path(__file__).resolve().parents[1] / "skills/workflow/scripts/run.py"


class EvidenceTests(unittest.TestCase):
    def setUp(self, *, legacy=False):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "control"
        if legacy:
            from control_store_fixtures import legacy_root
            legacy_root(self.root)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "devflow@example.test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Devflow Test"], cwd=self.repo, check=True)
        (self.repo / "test_target.py").write_text("# locked test\n")
        subprocess.run(["git", "add", "test_target.py"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        transact(self.root, 0, "fixture", {"kind": "fixture", "payload": {
            "repositories": {"repo-1": {"location": str(self.repo)}},
            "runs": {"run-1": {"id": "run-1", "state_version": 1,
                "plan": {"work_items": [{"id": "W1", "kind": "code", "repo_id": "repo-1"}]},
                "items": {"W1": {"attempts": []}}, "active_attempt": {
                    "token": "attempt-1", "item_id": "W1", "state_version": 1},
                "verification_proofs": {}}},
        }})

    def tearDown(self):
        self.temp.cleanup()

    def command(self, report, exit_code=0):
        encoded = json.dumps(report)
        return [sys.executable, "-c", f"import sys; print({encoded!r}); sys.exit({exit_code})"]

    def capture(self, *args):
        spec = importlib.util.find_spec("workflow_lib.evidence")
        self.assertIsNotNone(spec, "capture_evidence must be implemented")
        from workflow_lib.evidence import capture_evidence
        return capture_evidence(*args)

    def test_actual_target_red_green(self):
        red = self.capture(self.root, "run-1", "attempt-1", "RED",
                           self.command({"tests": [{"id": "test_target", "outcome": "failed"}]}, 1),
                           ["test_target.py"], ["test_target"], 10)
        evidence = self.capture(self.root, "run-1", "attempt-1", "GREEN",
                                self.command({"tests": [{"id": "test_target", "outcome": "passed"}]}),
                                ["test_target.py"], ["test_target"], 10)

        self.assertTrue(red["passed"])
        self.assertEqual(red["target_outcomes"], {"test_target": "failed"})
        self.assertEqual(evidence["exit_code"], 0)
        self.assertEqual(evidence["target_outcomes"], {"test_target": "passed"})
        self.assertEqual(evidence["repo_id"], "repo-1")
        self.assertEqual(len(evidence["test_hashes"]["test_target.py"]), 64)
        self.assertTrue((self.root / evidence["stdout_ref"]).is_file())

    def test_unrelated_failure_and_timeout(self):
        evidence = self.capture(self.root, "run-1", "attempt-1", "RED",
                                    self.command({"tests": [{"id": "other", "outcome": "failed"}]}, 1),
                                    ["test_target.py"], ["test_target"], 10)

        self.assertEqual(evidence["passed"], False)
        self.assertEqual(evidence["target_outcomes"], {})
        self.assertEqual(read_state(self.root)["version"], 1)
        self.assertFalse(read_state(self.root)["data"]["runs"]["run-1"]["verification_proofs"])

    def test_timeout_and_repo_escape_produce_stable_unpassed_results(self):
        timeout = self.capture(self.root, "run-1", "attempt-1", "GREEN",
                                   [sys.executable, "-c", "import time; time.sleep(2)"],
                                   ["test_target.py"], ["test_target"], 1)
        escaped = self.capture(self.root, "run-1", "attempt-1", "GREEN",
                                   self.command({"tests": [{"id": "test_target", "outcome": "passed"}]}),
                                   ["../outside.py"], ["test_target"], 10)

        self.assertEqual(timeout["passed"], False)
        self.assertEqual(timeout["failure"], "TIMEOUT")
        self.assertEqual(escaped["passed"], False)
        self.assertEqual(escaped["failure"], "TEST_PATH_OUTSIDE_REPOSITORY")

    def test_green_rejects_changed_locked_tests_after_red(self):
        failed = self.command({"tests": [{"id": "test_target", "outcome": "failed"}]}, 1)
        passing = self.command({"tests": [{"id": "test_target", "outcome": "passed"}]})
        self.capture(self.root, "run-1", "attempt-1", "RED", failed, ["test_target.py"], ["test_target"], 10)
        (self.repo / "test_target.py").write_text("# changed locked test\n")

        green = self.capture(self.root, "run-1", "attempt-1", "GREEN", passing,
                             ["test_target.py"], ["test_target"], 10)

        self.assertFalse(green["passed"])
        self.assertEqual(green["failure"], "LOCKED_TESTS_CHANGED")

    def test_build_command_records_proof_and_rejects_stale_tokens(self):
        report = json.dumps({"tests": [{"id": "test_target", "outcome": "failed"}]})
        command = [sys.executable, "-c", f"import sys; print({report!r}); sys.exit(1)"]
        result = subprocess.run([sys.executable, str(ENTRY), "build", "verify", "--root", str(self.root),
            "--run-id", "run-1", "--attempt-id", "attempt-1", "--phase", "red",
            "--argv-json", json.dumps(command), "--test-path", "test_target.py", "--target-id", "test_target"],
            capture_output=True, text=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])
        proof_map = read_state(self.root)["data"]["runs"]["run-1"]["verification_proofs"]
        self.assertEqual(len(proof_map), 1)

    def test_junit_xml_report_proves_declared_target(self):
        red_xml = "<testsuite failures='1'><testcase classname='tests.test_x' name='target'><failure/></testcase></testsuite>"
        green_xml = "<testsuite><testcase classname='tests.test_x' name='target'/></testsuite>"
        red_command = [sys.executable, "-c", f"import sys; print({red_xml!r}); sys.exit(1)"]
        green_command = [sys.executable, "-c", f"print({green_xml!r})"]
        self.capture(self.root, "run-1", "attempt-1", "RED", red_command,
                     ["test_target.py"], ["tests.test_x.target"], 10)
        result = self.capture(self.root, "run-1", "attempt-1", "GREEN", green_command,
                              ["test_target.py"], ["tests.test_x.target"], 10)

        self.assertTrue(result["passed"])
        self.assertEqual(result["target_outcomes"], {"tests.test_x.target": "passed"})

    def test_unittest_verbose_adapter_parses_failures_from_stderr(self):
        from workflow_lib.evidence import _report
        self.assertEqual(_report("", "test_target (tests.test_x.Target) ... FAIL\n", "unittest"),
                         {"tests.test_x.Target.test_target": "failed"})

    def test_repository_mutation_during_test_command_cannot_produce_green(self):
        self.capture(self.root, "run-1", "attempt-1", "RED",
                     self.command({"tests": [{"id": "test_target", "outcome": "failed"}]}, 1),
                     ["test_target.py"], ["test_target"], 10)
        mutating = [sys.executable, "-c", "import pathlib,json; pathlib.Path('source.py').write_text('changed'); print(json.dumps({'tests':[{'id':'test_target','outcome':'passed'}]}))"]
        result = self.capture(self.root, "run-1", "attempt-1", "GREEN", mutating,
                              ["test_target.py"], ["test_target"], 10)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failure"], "REPOSITORY_CHANGED_DURING_VERIFICATION")


if __name__ == "__main__":
    unittest.main()
