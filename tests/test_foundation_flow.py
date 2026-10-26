import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "skills/workflow/scripts/run.py"
sys.path.insert(0, str(ROOT / "skills/workflow/scripts"))
from workflow_lib.store import read_state, transact
from workflow_lib.specs import approval_record, content_hash
from workflow_lib.plans import validate_plan


class FoundationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="devflow flow ")
        self.base = Path(self.temp.name)
        self.control = self.base / "control root"
        self.control.mkdir()
        self.repo = self.base / "fixture repo"
        self.repo.mkdir()
        self.env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(ENTRY), *map(str, args)], cwd=tempfile.gettempdir(),
                                env=self.env, text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result

    def put_json(self, name, value):
        path = self.control / name
        path.write_text(json.dumps(value))
        return path

    def test_repository_spec_approval_rechecks_pair_without_events(self):
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.cli('repo', 'register', '--root', self.control, '--repo-id', 'app', '--location', self.repo)
        specification = {'mode': 'new', 'requirements': [], 'diagrams': [
            {'title': 'Scope', 'mermaid': 'flowchart LR\n    Intent --> Requirements'}]}
        source = self.put_json('spec.json', specification)
        stored = self.cli('spec', 'store', '--root', self.control, '--file', source,
                          '--repo-id', 'app', '--path', 'docs/specs/0063-ios-safari-suite.json')
        digest = stored['content_hash']
        version = read_state(self.control)['version']
        rejected = self.cli('spec', 'approve', '--root', self.control, '--confirm-hash', 'wrong',
                            '--actor-id', 'owner', ok=False)
        self.assertIn('EXPLICIT_CONFIRMATION_REQUIRED', rejected.stdout)
        self.assertEqual(read_state(self.control)['version'], version)
        (self.repo / 'docs/specs/0063-ios-safari-suite.md').write_text('changed')
        rejected = self.cli('spec', 'approve', '--root', self.control, '--confirm-hash', digest,
                            '--actor-id', 'owner', ok=False)
        self.assertIn('SPEC_PAIR_MISMATCH', rejected.stdout)
        self.assertEqual(read_state(self.control)['version'], version)
        self.cli('spec', 'store', '--root', self.control, '--file', source,
                 '--repo-id', 'app', '--path', 'docs/specs/0063-ios-safari-suite.json')
        approved = self.cli('spec', 'approve', '--root', self.control, '--confirm-hash', digest,
                            '--actor-id', 'owner')
        self.assertEqual(approved['approval']['repo_id'], 'app')
        self.assertIn('markdown_hash', approved['approval'])

    def test_new_repository_spec_requires_mermaid_before_approval(self):
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.cli('repo', 'register', '--root', self.control, '--repo-id', 'app', '--location', self.repo)
        source = self.put_json('spec.json', {'mode': 'new', 'requirements': []})
        stored = self.cli('spec', 'store', '--root', self.control, '--file', source,
                          '--repo-id', 'app', '--path', 'docs/specs/new.json')
        version = read_state(self.control)['version']
        rejected = self.cli('spec', 'approve', '--root', self.control,
                            '--confirm-hash', stored['content_hash'], '--actor-id', 'owner', ok=False)
        self.assertIn('SPEC_DIAGRAM_REQUIRED', rejected.stdout)
        self.assertEqual(read_state(self.control)['version'], version)
        source = self.put_json('spec.json', {'mode': 'new', 'requirements': [], 'diagrams': [
            {'title': 'Scope', 'mermaid': 'flowchart LR\n    Intent --> Requirements'}]})
        stored = self.cli('spec', 'store', '--root', self.control, '--file', source,
                          '--repo-id', 'app', '--path', 'docs/specs/new.json')
        approved = self.cli('spec', 'approve', '--root', self.control,
                            '--confirm-hash', stored['content_hash'], '--actor-id', 'owner')
        self.assertEqual(approved['approval']['content_hash'], stored['content_hash'])

    def test_changed_approved_repository_spec_needs_diagram(self):
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.cli('repo', 'register', '--root', self.control, '--repo-id', 'app', '--location', self.repo)
        source = self.put_json('spec.json', {'mode': 'new', 'title': 'Legacy', 'requirements': []})
        stored = self.cli('spec', 'store', '--root', self.control, '--file', source,
                          '--repo-id', 'app', '--path', 'docs/specs/legacy.json')
        state = read_state(self.control)
        transact(self.control, state['version'], 'legacy-approval-fixture', {'kind': 'fixture', 'payload': {
            'approval': {**stored['spec_pair'], 'content_hash': stored['content_hash'],
                         'confirmed': True, 'actor_id': 'owner'}}})
        self.cli('spec', 'approve', '--root', self.control, '--confirm-hash',
                 stored['content_hash'], '--actor-id', 'owner')
        source = self.put_json('spec.json', {'mode': 'new', 'title': 'Edited', 'requirements': []})
        changed = self.cli('spec', 'store', '--root', self.control, '--file', source,
                           '--repo-id', 'app', '--path', 'docs/specs/legacy.json')
        rejected = self.cli('spec', 'approve', '--root', self.control,
                            '--confirm-hash', changed['content_hash'], '--actor-id', 'owner', ok=False)
        self.assertIn('SPEC_DIAGRAM_REQUIRED', rejected.stdout)

    def test_next_brief_resume_atomic_result_retry_and_state_location(self):
        from control_store_fixtures import legacy_root
        legacy_root(self.control) # This case verifies legacy state.json placement.
        self.cli("repo", "register", "--root", self.control, "--repo-id", "backend", "--location", self.repo)
        self.put_json("org.json", {"slices": {"architecture": {"status": "answered", "value": "hexagonal"}}})
        self.cli("context", "set", "--root", self.control, "--layer", "org", "--file", self.control / "org.json")
        first_context = self.cli("context", "resolve", "--root", self.control)
        self.assertFalse(first_context["projection_cache_hit"])
        second_context = self.cli("context", "resolve", "--root", self.control)
        self.assertTrue(second_context["projection_cache_hit"])
        specification = {"mode": "new", "requirements": [{"id": "R1", "text": "Persist a setting",
            "acceptance_criteria": ["setting survives restart"], "provenance": {"kind": "authored"}}]}
        spec_path = self.put_json("spec.json", specification)
        self.cli("spec", "store", "--root", self.control, "--file", spec_path)
        digest = self.cli("spec", "validate", "--file", spec_path)["content_hash"]
        self.cli("spec", "approve", "--root", self.control, "--confirm-hash", digest, "--actor-id", "owner")
        work_plan = {"spec_hash": digest, "stage": {"name": "build", "required_slices": ["architecture"]},
            "artifacts": {"requirements": f"sha256:{digest}"}, "work_items": [{"id": "W1", "kind": "code", "requirement_ids": ["R1"],
            "acceptance_criteria": [{"kind": "code-test", "text": "setting persistence test"}], "dependencies": []}]}
        plan_path = self.put_json("plan.json", work_plan)
        self.cli("plan", "validate", "--root", self.control, "--file", plan_path)
        current = read_state(self.control)
        transact(self.control, current["version"], "fixture-authorization-and-findings", {
            "kind": "run.context.seeded", "payload": {
                "authorization_scope": {"action": "local-test-only", "expires": "run"},
                "unresolved_findings": [{"id": "F-1", "severity": "minor"}],
            },
        })
        started = self.cli("run", "start", "--root", self.control, "--run-id", "flow-1")
        self.assertNotIn("operations", started)

        first = self.cli("run", "next", "--root", self.control, "--run-id", "flow-1")
        self.assertEqual(first['task_view']['coverage']['missing_ids'], [])
        self.assertIn('R1', first['task_view']['required_ids'])
        self.assertTrue(first['task_view']['artifact_id'])
        self.assertEqual(first["context"]["values"]["architecture"], "hexagonal")
        self.assertEqual(first["work_items"][0]["acceptance_criteria"], work_plan["work_items"][0]["acceptance_criteria"])
        self.assertEqual(first["artifacts"], {"requirements": f"sha256:{digest}"})
        self.assertEqual(first["authorization_scope"]["action"], "local-test-only")
        self.assertEqual(first["unresolved_findings"][0]["id"], "F-1")
        token = first["attempt_id"]
        after_restart = self.cli("run", "status", "--root", self.control, "--run-id", "flow-1")
        self.assertEqual(after_restart["active_attempt"]["token"], token)
        read_only_brief = self.cli("run", "brief", "--root", self.control, "--run-id", "flow-1",
                                   "--item", "W1")
        self.assertEqual(read_only_brief["attempt_id"], token)
        self.assertEqual(read_only_brief["authorization_scope"]["action"], "local-test-only")
        self.assertEqual(read_only_brief["unresolved_findings"][0]["id"], "F-1")
        checkpoint = self.cli('run', 'brief', '--root', self.control, '--run-id', 'flow-1', '--consumer-id', 'cli-session')
        delta = self.cli('run', 'brief', '--root', self.control, '--run-id', 'flow-1', '--consumer-id', 'cli-session',
                         '--since-checkpoint', checkpoint['checkpoint']['id'])
        self.assertEqual(delta['context_mode'], 'delta')
        self.assertEqual(delta['task_view']['changed_units'], [])
        recovered = self.cli('run', 'brief', '--root', self.control, '--run-id', 'flow-1',
                             '--since-checkpoint', checkpoint['checkpoint']['id'])
        self.assertEqual(recovered['context_mode'], 'full')
        inspected = self.cli("run", "inspect", "--root", self.control, "--run-id", "flow-1")
        self.assertEqual(inspected["run"]["active_attempt"]["token"], token)
        self.assertNotIn("operations", inspected)
        before_invalid = {p.relative_to(self.control / "events"): p.read_bytes()
                          for p in (self.control / "events").iterdir() if p.is_file()}
        state_before_invalid = (self.control / "state.json").read_bytes()
        self.assertNotIn(b'"operations"', state_before_invalid)
        self.cli("run", "result", "--root", self.control, "--run-id", "flow-1", "--attempt-id", token,
                 "--result", '{"detail":"missing outcome"}', ok=False)
        after_invalid = {p.relative_to(self.control / "events"): p.read_bytes()
                         for p in (self.control / "events").iterdir() if p.is_file()}
        self.assertEqual(after_invalid, before_invalid)
        self.assertEqual((self.control / "state.json").read_bytes(), state_before_invalid)
        self.cli("run", "abandon", "--root", self.control, "--run-id", "flow-1", "--attempt-id", token)
        retry = self.cli("run", "retry", "--root", self.control, "--run-id", "flow-1", "--item", "W1")
        self.assertNotEqual(retry["attempt_id"], token)
        version_before = len(list((self.control / "events").glob("[0-9]*.json")))
        rejected = self.cli("run", "result", "--root", self.control, "--run-id", "flow-1",
                            "--attempt-id", retry["attempt_id"], "--result", '{"outcome":"passed"}', ok=False)
        self.assertEqual(json.loads(rejected.stdout)['error'],'VERIFIER_PROOF_REQUIRED')
        self.assertEqual(len(list((self.control / "events").glob("[0-9]*.json"))),version_before)
        summary = self.cli("run", "result", "--root", self.control, "--run-id", "flow-1",
                           "--attempt-id", retry["attempt_id"], "--result", '{"outcome":"blocked"}')
        version_after = len(list((self.control / "events").glob("[0-9]*.json")))
        self.assertEqual(version_after, version_before + 1)
        self.assertEqual(summary["pending_items"], ["W1"])
        self.assertNotIn("build", summary["unavailable_gates"])
        self.assertIn("hardening", summary["unavailable_gates"])
        persisted = read_state(self.control)["data"]["runs"]["flow-1"]
        self.assertEqual(persisted["items"]["W1"]["attempts"][-1]["status"], "result_recorded")
        events = read_state(self.control)["operations"].values()
        issued_event = next(event for event in events if event["kind"] == "run.attempt.issued")
        self.assertNotIn("runs", issued_event["payload"])
        self.assertEqual(issued_event["payload"]["attempt"]["item_id"], "W1")
        telemetry = [json.loads(line) for line in (self.control / "offload.jsonl").read_text(encoding='utf-8').splitlines()]
        self.assertTrue(all(row["output_bytes"] > 0 for row in telemetry))
        self.assertTrue(any(row["operation"] == "run.brief" for row in telemetry))
        self.assertTrue(any(row.get("run_id") == "flow-1" for row in telemetry))
        bad_inspect = self.cli("run", "inspect", "--root", self.control, "--run-id", "../../outside", ok=False)
        self.assertIn("RUN_NOT_FOUND", bad_inspect.stdout)

        allowed = [self.control.resolve(), self.repo.resolve()]
        for path in self.base.rglob("*"):
            if path.is_file():
                self.assertTrue(any(path.resolve().is_relative_to(root) for root in allowed), str(path))

    def test_context_projection_can_return_to_a_previously_resolved_value(self):
        self.put_json("layer.json", {"slices": {"architecture": {"status": "answered", "value": "A"}}})
        self.cli("context", "set", "--root", self.control, "--layer", "org", "--file", self.control / "layer.json")
        self.cli("context", "resolve", "--root", self.control)
        self.put_json("layer.json", {"slices": {"architecture": {"status": "answered", "value": "B"}}})
        self.cli("context", "set", "--root", self.control, "--layer", "org", "--file", self.control / "layer.json")
        self.cli("context", "resolve", "--root", self.control)
        self.put_json("layer.json", {"slices": {"architecture": {"status": "answered", "value": "A"}}})
        self.cli("context", "set", "--root", self.control, "--layer", "org", "--file", self.control / "layer.json")

        resolved = self.cli("context", "resolve", "--root", self.control)

        self.assertEqual(resolved["values"]["architecture"], "A")
        persisted = read_state(self.control)["data"]["resolved_context"]
        self.assertEqual(persisted["values"]["architecture"], "A")

    def test_replayed_run_operation_never_returns_an_uncommitted_attempt_token(self):
        specification = {"mode": "new", "requirements": [{"id": "R1", "text": "One",
            "acceptance_criteria": ["one"], "provenance": {"kind": "authored"}}]}
        digest = content_hash(specification)
        approval = {**approval_record(specification, digest), "actor_id": "human-1"}
        work_plan = {"spec_hash": digest, "work_items": [{"id": "W1", "kind": "code",
            "requirement_ids": ["R1"], "dependencies": [], "acceptance_criteria": [{"kind": "code-test", "text": "test"}]}]}
        validation = validate_plan({**specification, "approval": approval}, work_plan)
        current = read_state(self.control)
        transact(self.control, current["version"], "seed-spec", {"kind": "spec.stored", "payload": {"spec": specification}})
        current = read_state(self.control)
        transact(self.control, current["version"], "seed-approval", {"kind": "spec.approved", "payload": {"approval": approval}})
        current = read_state(self.control)
        transact(self.control, current["version"], "seed-plan", {"kind": "plan.validated", "payload": {
            "plan": work_plan, "plan_validation": validation}})
        self.cli("run", "start", "--root", self.control, "--run-id", "replay")
        first = self.cli("run", "next", "--root", self.control, "--run-id", "replay", "--operation-id", "same-op")
        self.cli("run", "abandon", "--root", self.control, "--run-id", "replay", "--attempt-id", first["attempt_id"])

        repeated = self.cli("run", "retry", "--root", self.control, "--run-id", "replay", "--item", "W1",
                            "--operation-id", "same-op")

        active = read_state(self.control)["data"]["runs"]["replay"].get("active_attempt")
        self.assertTrue(repeated["replayed"])
        self.assertFalse(repeated["attempt_issued"])
        self.assertNotIn("attempt_id", repeated)
        self.assertIsNone(active)


if __name__ == "__main__":
    unittest.main()
