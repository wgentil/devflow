from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.context_checkpoints import project_checkpoint, apply_context_delta
from workflow_lib.document_units import canonical
from workflow_lib.store import WorkflowError


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scope = {'consumer_id': 'consumer', 'run_id': 'run', 'binding_id': 'binding', 'session_id': 'session',
                      'revision': 1, 'stage': 'implementation', 'role': 'implementer', 'task_ids': ['W1']}
        self.view = {'run_id': 'run', 'blockers': ['old'], 'task_view': {'required_ids': ['R1'],
            'units': [{'id': 'R1', 'content': 'a' * 6000}, {'id': 'R2', 'content': 'b' * 3000}]}}

    def test_delta_reconstructs_current_view_with_removal_and_fresh_envelope(self):
        base = project_checkpoint(self.root, self.view, self.scope)
        current = deepcopy(self.view)
        current['blockers'] = ['new approval required']
        current['task_view']['units'] = [current['task_view']['units'][0], {'id': 'R3', 'content': 'new'}]
        delta = project_checkpoint(self.root, current, self.scope, since=base['checkpoint']['id'])
        self.assertEqual(delta['context_mode'], 'delta')
        self.assertEqual(delta['task_view']['removed_ids'], ['R2'])
        self.assertEqual(delta['blockers'], current['blockers'])
        rebuilt = apply_context_delta(base, delta)
        self.assertEqual(rebuilt['task_view'], current['task_view'])
        self.assertLess(len(canonical(delta)), len(canonical(project_checkpoint(self.root, current, self.scope))))

    def test_each_scope_mismatch_forces_full(self):
        base = project_checkpoint(self.root, self.view, self.scope)
        for key, value in self.scope.items():
            other = {**self.scope, key: ['W2'] if isinstance(value, list) else 2 if isinstance(value, int) else 'other'}
            projected = project_checkpoint(self.root, self.view, other, since=base['checkpoint']['id'])
            self.assertEqual(projected['context_mode'], 'full', key)
            self.assertEqual(projected['checkpoint']['reason_code'], 'SCOPE_CHANGED')

    def test_unknown_corrupt_recovery_and_unattached_cli_force_full(self):
        base = project_checkpoint(self.root, self.view, self.scope)
        for reason in ('session-start', 'compaction', 'handoff', 'new-native-worker'):
            value = project_checkpoint(self.root, self.view, self.scope, since=base['checkpoint']['id'], recovery_reason=reason)
            self.assertEqual(value['context_mode'], 'full')
            self.assertEqual(value['checkpoint']['reason_code'], reason)
        for unknown in ('../escape', '0' * 64):
            self.assertEqual(project_checkpoint(self.root, self.view, self.scope, since=unknown)['context_mode'], 'full')
        (self.root / 'context-checkpoints' / (base['checkpoint']['id'] + '.json')).write_text('{}')
        self.assertEqual(project_checkpoint(self.root, self.view, self.scope, since=base['checkpoint']['id'])['context_mode'], 'full')
        self.assertEqual(project_checkpoint(self.root, self.view, {**self.scope, 'consumer_id': None}, since=base['checkpoint']['id'])['context_mode'], 'full')
        self.assertFalse((self.root / 'state.json').exists())

    def test_wrong_base_or_tampered_delta_cannot_reconstruct(self):
        base = project_checkpoint(self.root, self.view, self.scope)
        delta = project_checkpoint(self.root, self.view, self.scope, since=base['checkpoint']['id'])
        wrong = deepcopy(base)
        wrong['task_view']['units'][0]['content'] = 'tampered'
        with self.assertRaises(WorkflowError):
            apply_context_delta(wrong, delta)
        delta['task_view']['changed_units'] = [{'id': 'R1', 'content': 'tampered'}]
        with self.assertRaises(WorkflowError):
            apply_context_delta(base, delta)
