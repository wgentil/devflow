import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.store import read_state, transact, WorkflowError
from workflow_lib.repo_specs import write_spec_pair
from workflow_lib.specs import content_hash
from workflow_lib.repo_input_gate import require_current_spec, migrate_legacy_spec

class RepoInputGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'control'
        self.repo = Path(self.temp.name) / 'repo'
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.spec = {'mode': 'new', 'title': 'Gate', 'requirements': []}
        self.pair = {'repo_id': 'r', **write_spec_pair(self.repo, 'docs/spec.json', self.spec)}
        self.write({'repositories': {'r': {'location': str(self.repo)}}, 'spec': self.spec,
                    'spec_pair': self.pair, 'approval': {**self.pair, 'confirmed': True, 'actor_id': 'human'}})
    def tearDown(self): self.temp.cleanup()
    def write(self, data):
        s = read_state(self.root)
        transact(self.root, s['version'], str(s['version']), {'kind': 'fixture', 'payload': data})
    def test_drift_invalidates_approval_even_after_restore_and_replay_is_pure(self):
        for phase in ('plan-validation', 'run-start', 'handoff', 'delivery'):
            with self.subTest(phase=phase):
                self.write({'approval': {**self.pair, 'confirmed': True}, 'spec_approval_invalidated': None})
                md = self.repo / self.pair['markdown_path']; old = md.read_bytes(); md.write_text('drift')
                with self.assertRaises(WorkflowError): require_current_spec(self.root, read_state(self.root), phase)
                md.write_bytes(old)
                with self.assertRaises(WorkflowError) as caught: require_current_spec(self.root, read_state(self.root), phase)
                self.assertEqual(caught.exception.code, 'SPEC_APPROVAL_STALE')
                md.unlink()
                self.assertIsNotNone(read_state(self.root)['data']['spec'])
                md.write_bytes(old)
    def test_legacy_migration_candidate_requires_reapproval_and_preserves_targets(self):
        self.write({'spec_pair': None, 'approval': {'content_hash': content_hash(self.spec), 'confirmed': True}})
        self.assertEqual(require_current_spec(self.root, read_state(self.root), 'plan')['content_hash'], content_hash(self.spec))
        receipt = migrate_legacy_spec(self.root, 'r', 'docs/migrated.json', 'migration')
        self.assertEqual(receipt['content_hash'], content_hash(self.spec))
        self.assertEqual(migrate_legacy_spec(self.root, 'r', 'docs/migrated.json', 'migration'), receipt)
        with self.assertRaises(WorkflowError): require_current_spec(self.root, read_state(self.root), 'run')
        before = (self.repo / 'docs/spec.json').read_bytes()
        self.write({'spec_pair': None})
        with self.assertRaises(WorkflowError): migrate_legacy_spec(self.root, 'r', 'docs/spec.json', 'other')
        self.assertEqual((self.repo / 'docs/spec.json').read_bytes(), before)

    def test_cli_transitions_share_live_gate(self):
        script = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'
        f = self.repo / 'input.json'; f.write_text('{}')
        commands = [ ['plan', 'validate', '--file', str(f)],
                     ['run', 'start', '--run-id', 'run'],
                     ['host', 'handoff-prepare', '--file', str(f), '--operation-id', 'handoff'],
                     ['delivery', 'prepare', '--run-id', 'run', '--repositories-json', '{}', '--outcome', 'retained-branch'] ]
        (self.repo / self.pair['markdown_path']).write_text('drift')
        for command in commands:
            with self.subTest(command=command):
                result = subprocess.run([sys.executable, str(script), *command, '--root', str(self.root)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(json.loads(result.stdout)['error'], ['SPEC_PAIR_MISMATCH', 'SPEC_APPROVAL_STALE'])

    def test_explicit_cli_reapproval_clears_observed_drift(self):
        md = self.repo / self.pair['markdown_path']; original = md.read_bytes(); md.write_text('drift')
        with self.assertRaises(WorkflowError): require_current_spec(self.root, read_state(self.root), 'run-start')
        md.write_bytes(original)
        script = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'
        result = subprocess.run([sys.executable, str(script), 'spec', 'approve', '--root', str(self.root),
            '--confirm-hash', content_hash(self.spec), '--actor-id', 'human', '--operation-id', 'fresh-approval'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(require_current_spec(self.root, read_state(self.root), 'run-start'), self.pair)

    def test_migration_cli_and_operation_conflict(self):
        self.write({'spec_pair': None})
        script = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'
        args = [sys.executable, str(script), 'spec', 'migrate', '--root', str(self.root), '--repo-id', 'r',
                '--path', 'docs/cli.json', '--operation-id', 'cli-migration']
        first = subprocess.run(args, capture_output=True, text=True)
        second = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(json.loads(first.stdout), json.loads(second.stdout))
        self.assertEqual(json.loads(first.stdout)['content_hash'], content_hash(self.spec))
        with self.assertRaises(WorkflowError) as caught: migrate_legacy_spec(self.root, 'r', 'docs/other.json', 'cli-migration')
        self.assertEqual(caught.exception.code, 'OPERATION_CONFLICT')

    def test_committed_handoff_retry_is_read_only_with_changed_or_missing_pair(self):
        from test_hosts import host_state, attachment
        from workflow_lib.hosts import apply_host_event
        data = host_state(str(self.repo))
        data['repositories']['r'] = {'location': str(self.repo)}
        apply_host_event(data, 'attach', attachment(project=str(self.repo)))
        self.write(data)
        request = {'binding_id': 'b1', 'revision': 1, 'handoff_id': 'h1',
                   'target_host': 'claude', 'target_session_id': 's2', 'target_actor_id': 'a2'}
        f = self.repo / 'handoff.json'; f.write_text(json.dumps(request))
        script = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'
        args = [sys.executable, str(script), 'host', 'handoff-prepare', '--root', str(self.root),
                '--file', str(f), '--operation-id', 'successful-handoff']
        first = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        baseline = read_state(self.root)
        events = {p.name: p.read_bytes() for p in (self.root / 'events').iterdir()}
        md = self.repo / self.pair['markdown_path']
        for missing in (False, True):
            if missing: md.unlink()
            else: md.write_text('drift')
            replay = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)
            self.assertTrue(json.loads(replay.stdout)['replayed'])
            self.assertEqual(json.loads(replay.stdout)['handoff_id'], 'h1')
            self.assertEqual(read_state(self.root), baseline)
            self.assertEqual({p.name: p.read_bytes() for p in (self.root / 'events').iterdir()}, events)
        f.write_text(json.dumps({**request, 'target_actor_id': 'different'}))
        conflict = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(json.loads(conflict.stdout)['error'], 'OPERATION_CONFLICT')
        self.assertEqual(read_state(self.root), baseline)
