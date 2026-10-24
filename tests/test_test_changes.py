import hashlib
import json
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
        self.assertEqual(self.source.read_text(encoding='utf-8'), "def test_locked():\n    assert 1 == 1\n")

    def test_exact_approval_precedes_patch_application_and_records_hashes(self):
        propose, approve, apply = self.module()
        proposal = propose(self.run, "W1", self.patch, "expect the corrected behavior", self.repo)

        with self.assertRaises(ValueError):
            approve(proposal, "wrong-hash", "human-1")
        approval = approve(proposal, proposal["proposal_hash"], "human-1")
        result = apply(self.repo, proposal, approval)

        self.assertEqual(self.source.read_text(encoding='utf-8'), "def test_locked():\n    assert 1 == 2\n")
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
        self.assertIn("assert 1 == 3", self.source.read_text(encoding='utf-8'))

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


class TestChangeCLITests(unittest.TestCase):
    def setUp(self):
        self.fixture = TestChangeTests('test_exact_approval_precedes_patch_application_and_records_hashes')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.root = Path(self.fixture.temp.name) / 'control é東京'
        self.entry = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'

    def seed(self, runs):
        transact(self.root, 0, 'fixture', {'kind': 'fixture', 'payload': {'runs': runs}})

    def cli(self, command, *, run_id='run-1', options=()):
        return subprocess.run([sys.executable, '-B', str(self.entry), 'build', 'test-change', command,
            '--root', str(self.root), '--run-id', run_id, *options],
            capture_output=True, encoding='utf-8', timeout=30)

    def authoritative_files(self):
        paths = [self.root / 'state.json', *(self.root / 'events').glob('*.json')]
        return {str(path): path.read_bytes() for path in paths}

    def repository_files(self, repo=None):
        return {str(path): path.read_bytes() for path in (repo or self.fixture.repo).rglob('*') if path.is_file()}

    def test_list_empty_run_without_proposal_id(self):
        # An erroneous per-proposal lookup must not prevent run-level inspection.
        self.seed({'missing': {'id': 'missing'}, 'empty': {'id': 'empty', 'test_change_proposals': {}}})
        before = self.authoritative_files()
        for run_id in ('missing', 'empty'):
            with self.subTest(run_id=run_id):
                result = self.cli('list', run_id=run_id)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {'proposals': {}})
                self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(self.authoritative_files(), before)

    def test_list_preserves_proposals_and_run_scope(self):
        # Dropping fields, filtering status, selecting another run or writing state is a bug.
        propose, approve, apply = self.fixture.module()
        pending = propose(self.fixture.run, 'W1', self.fixture.patch, 'é東京: preserve\npatch details', self.fixture.repo)
        approved = propose(self.fixture.run, 'W1', self.fixture.patch, 'approved é東京', self.fixture.repo)
        applied = propose(self.fixture.run, 'W1', self.fixture.patch, 'applied é東京', self.fixture.repo)
        approved['approval'] = approve(approved, approved['proposal_hash'], 'human-é東京')
        approved['status'] = 'approved'
        applied['approval'] = approve(applied, applied['proposal_hash'], 'human-é東京')
        result = apply(self.fixture.repo, applied, applied['approval'])
        applied.update(status='applied', after_hashes=result['after_hashes'])
        proposals = {p['id']: p for p in (pending, approved, applied)}
        self.seed({'run-1': {**self.fixture.run, 'test_change_proposals': proposals},
                   'run-2': {'id': 'run-2', 'test_change_proposals': {'other': {'id': 'other'}}}})
        before, repository = self.authoritative_files(), self.repository_files()
        version = read_state(self.root)['version']
        for _ in range(2):
            result = self.cli('list')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {'proposals': proposals})
            self.assertNotIn('Traceback', result.stderr)
        current = read_state(self.root)
        self.assertEqual(current['version'], version)
        self.assertEqual(current['data']['runs']['run-1']['test_change_proposals'], proposals)
        self.assertEqual(self.authoritative_files(), before)
        self.assertEqual(self.repository_files(), repository)

    def test_list_unknown_run_is_structured_error(self):
        self.seed({'run-1': {'id': 'run-1'}})
        before = self.authoritative_files()
        result = self.cli('list', run_id='unknown')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)['error'], 'RUN_NOT_FOUND')
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(self.authoritative_files(), before)

    def test_mutating_commands_retain_proposal_id_validation(self):
        # Accidentally widening the list branch must not bypass mutation validation.
        self.seed({'run-1': {'id': 'run-1'}})
        before, repository = self.authoritative_files(), self.repository_files()
        for command, options in (('approve', ['--confirm-hash', 'hash', '--actor-id', 'human']),
                                 ('apply', ['--confirm-hash', 'hash'])):
            with self.subTest(command=command, case='missing ID'):
                result = self.cli(command, options=options)
                self.assertEqual(result.returncode, 2)
                self.assertIn('--proposal-id', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
            with self.subTest(command=command, case='unknown ID'):
                result = self.cli(command, options=[*options, '--proposal-id', 'unknown'])
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)['error'], 'TEST_CHANGE_NOT_FOUND')
                self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(self.authoritative_files(), before)
        self.assertEqual(self.repository_files(), repository)


    def context_project(self, name):
        from large_context_fixtures import make_context_project
        project = make_context_project(Path(self.fixture.temp.name) / name)
        self.root = project['root']
        return project

    def test_list_remains_read_only_with_drifted_or_missing_spec(self):
        # Inspection must not trigger live-input invalidation, even for unknown runs.
        for mode in ('drifted', 'missing'):
            with self.subTest(mode=mode):
                project = self.context_project(mode)
                spec = project['repo'] / project['state']['data']['spec_pair']['markdown_path']
                if mode == 'drifted':
                    spec.write_text('Unapproved specification edit', encoding='utf-8')
                else:
                    spec.unlink()
                before, repository = self.authoritative_files(), self.repository_files(project['repo'])
                version = read_state(self.root)['version']
                for run_id, code, expected in (('current', 0, {'proposals': {}}),
                                               ('unknown', 2, {'error': 'RUN_NOT_FOUND'})):
                    with self.subTest(run_id=run_id):
                        result = self.cli('list', run_id=run_id)
                        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                        value = json.loads(result.stdout)
                        for key, wanted in expected.items():
                            self.assertEqual(value[key], wanted)
                        self.assertEqual(self.authoritative_files(), before)
                        self.assertEqual(read_state(self.root)['version'], version)
                self.assertEqual(self.authoritative_files(), before)
                self.assertEqual(self.repository_files(project['repo']), repository)

    def test_list_does_not_refresh_governing_receipt(self):
        # An unchanged rule's newer Git provenance is refreshed by work, not inspection.
        from workflow_lib.ground_interview import TOPICS
        from workflow_lib.repo_input_gate import preflight_inputs
        project = self.context_project('governed')
        repo = project['repo']
        (repo / 'rules.md').write_text('## A: Safety\nKeep checks.\n', encoding='utf-8')
        (repo / 'docs/devflow-context.json').write_text(json.dumps({'schema_version': 1,
            'documents': [{'category': 'coding-standards', 'path': 'rules.md', 'rule_ids': ['A']}]}), encoding='utf-8')
        (repo / 'docs/devflow-ground-interview.json').write_text(json.dumps({'schema_version': 1,
            'topics': {name: {'status': 'answered', 'material': True, 'decision': 'Offline fixture.'}
                       for name in TOPICS}}), encoding='utf-8')
        subprocess.run(['git', 'add', '.'], cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-qm', 'Fixture rules'], cwd=repo, check=True, capture_output=True)
        state = preflight_inputs(self.root, read_state(self.root), 'plan-validation')['state']
        digest = state['data']['governing_input_receipt']['effective_digest']
        run = {**state['data']['runs']['current'], 'governing_digest': digest}
        transact(self.root, state['version'], 'align-plan', {'kind': 'fixture', 'payload': {
            'runs': {'current': run}, 'governing_reassessment_required': None,
            'plan_validation': {**state['data']['plan_validation'], 'governing_digest': digest}}})
        subprocess.run(['git', 'commit', '--allow-empty', '-qm', 'Advance provenance only'],
                       cwd=repo, check=True, capture_output=True)
        before, repository = self.authoritative_files(), self.repository_files(repo)
        recorded = read_state(self.root)
        result = self.cli('list', run_id='current')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), {'proposals': {}})
        self.assertEqual(read_state(self.root), recorded)
        self.assertEqual(self.authoritative_files(), before)
        self.assertEqual(self.repository_files(repo), repository)

    def test_mutating_commands_still_require_current_inputs(self):
        # Exempting inspection must not exempt proposal/approval/application work.
        for command, options in (
            ('propose', ['--item', 'W1', '--patch-file', 'unused.patch', '--reason', 'correction']),
            ('approve', ['--proposal-id', 'unknown', '--confirm-hash', 'hash', '--actor-id', 'human']),
            ('apply', ['--proposal-id', 'unknown', '--confirm-hash', 'hash'])):
            with self.subTest(command=command):
                project = self.context_project('guard-' + command)
                path = project['repo'] / project['state']['data']['spec_pair']['markdown_path']
                path.write_text('Unapproved specification edit', encoding='utf-8')
                result = self.cli(command, run_id='current', options=options)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)['error'], 'SPEC_PAIR_MISMATCH')
                self.assertIsNotNone(read_state(self.root)['data'].get('spec_approval_invalidated'))


if __name__ == "__main__":
    unittest.main()
