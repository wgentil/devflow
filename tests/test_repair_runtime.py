import sys
import tempfile
import unittest
import subprocess
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.repair_runtime import run_repair
from workflow_lib.repair_runtime import _run_gate
from workflow_lib.store import read_state, transact


class RepairRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        run = {'id': 'r', 'status': 'active', 'actors': {'implementer': 'worker'},
               'plan': {'work_items': []}, 'items': {},
               'required_hardening_gates': ['security'], 'hardening_config_hash': 'cfg',
               'hardening_proofs': {'security': {'passed': False, 'config_hash': 'cfg'}},
               'unresolved_findings': [], 'repair_cycles': [],
               'repair_policy': {'enabled': True, 'max_attempts': 3, 'max_elapsed_ms': 100000,
                                 'max_estimated_cost': 10, 'no_progress_window': 2}}
        binding = {'binding_id': 'b', 'revision': 1, 'run_id': 'r', 'role': 'implementer',
                   'status': 'active', 'actor_id': 'worker'}
        transact(self.root, 0, 'fixture', {'kind': 'fixture', 'payload': {
            'runs': {'r': run}, 'host_bindings': {'b': binding}}})

    def tearDown(self):
        self.temp.cleanup()

    def run_cycle(self, operation_id, cost=1):
        with patch('workflow_lib.repair_runtime._preflight_worker',
                   return_value={'status': 'allow', 'resolved': {'model': 'test'}}):
            return run_repair(self.root, 'r', operation_id, cost)

    def test_one_worker_one_gate_and_replay_no_second_launch(self):
        with patch('workflow_lib.repair_runtime.invoke', return_value={'status': 'allow'}) as worker, \
             patch('workflow_lib.repair_runtime._run_gate', return_value={'proof_id': 'proof'}) as gate:
            first = self.run_cycle('op')
            replay = self.run_cycle('op')
        self.assertEqual(first['status'], 'recorded')
        self.assertTrue(replay['replayed'])
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(len(read_state(self.root)['data']['runs']['r']['repair_cycles']), 1)

    def test_unknown_price_and_unavailable_worker_do_not_change_attempt(self):
        self.assertEqual(run_repair(self.root, 'r', 'unknown')['reason_code'], 'PRICE_UNKNOWN')
        self.assertEqual(read_state(self.root)['data']['runs']['r']['repair_cycles'], [])
        with patch('workflow_lib.repair_runtime.invoke', return_value={'status': 'block',
                                                                        'reason_code': 'MODEL_UNAVAILABLE'}):
            result = self.run_cycle('blocked')
        self.assertEqual(result['reason_code'], 'MODEL_UNAVAILABLE')
        self.assertEqual(read_state(self.root)['data']['runs']['r']['repair_cycles'][0]['status'], 'aborted')
        self.assertIsNone(read_state(self.root)['data']['runs']['r'].get('active_attempt'))
        self.assertEqual(self.run_cycle('blocked')['reason_code'], 'REPAIR_ALREADY_CLAIMED')

    def test_gate_runner_error_aborts_cycle_with_remaining_failures(self):
        with patch('workflow_lib.repair_runtime.invoke', return_value={'status': 'allow'}), \
             patch('workflow_lib.repair_runtime._run_gate',
                   side_effect=RuntimeError('runner failed')):
            result = self.run_cycle('gate-error')
        self.assertEqual(result['reason_code'], 'REPAIR_VERIFICATION_FAILED')
        run = read_state(self.root)['data']['runs']['r']
        self.assertEqual(run['repair_cycles'][0]['status'], 'aborted')
        self.assertEqual(run['repair_stop']['remaining_failures']['gate_ids'], ['security'])

    def test_failed_validation_leaves_failure_delta(self):
        with patch('workflow_lib.repair_runtime.invoke', return_value={'status': 'allow'}), \
             patch('workflow_lib.repair_runtime._run_gate', return_value={'passed': False}):
            result = self.run_cycle('fail')
        self.assertEqual(result['remaining_failures']['gate_ids'], ['security'])

    def test_reviewer_cannot_repair_own_finding(self):
        state = read_state(self.root)
        reviewer = {'binding_id': 'reviewer', 'revision': 1, 'run_id': 'r',
                    'role': 'branch-reviewer', 'status': 'active', 'actor_id': 'worker'}
        transact(self.root, state['version'], 'reviewer', {'kind': 'fixture',
                 'payload': {'host_bindings': {'reviewer': reviewer}}})
        state = read_state(self.root)
        # A reviewer binding is never a repair dispatcher, even if it shares the actor ID.
        with patch('workflow_lib.repair_runtime.invoke') as worker:
            result = run_repair(self.root, 'r', 'review-only', 1)
        self.assertEqual(result['reason_code'], 'IMPLEMENTER_UNAVAILABLE')
        worker.assert_not_called()

    def test_ineligible_model_does_not_claim_or_launch(self):
        with patch('workflow_lib.repair_runtime._preflight_worker',
                   return_value={'status': 'block', 'reason_code': 'MODEL_UNAVAILABLE'}), \
             patch('workflow_lib.repair_runtime.invoke') as worker:
            result = run_repair(self.root, 'r', 'ineligible', 1)
        self.assertEqual(result['reason_code'], 'MODEL_UNAVAILABLE')
        self.assertEqual(read_state(self.root)['data']['runs']['r']['repair_cycles'], [])
        worker.assert_not_called()

    def test_configured_report_gate_fails_then_passes_after_repair(self):
        repo = self.root / 'app'
        repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 'test@example.invalid'], check=True)
        subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'Test'], check=True)
        (repo / 'flag.txt').write_text('FAIL')
        subprocess.run(['git', '-C', str(repo), 'add', 'flag.txt'], check=True)
        subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'fixture'], check=True)
        state = read_state(self.root)
        run = state['data']['runs']['r']
        run['plan']['work_items'] = [{'id': 'W1', 'repo_id': 'app'}]
        transact(self.root, state['version'], 'repo', {'kind': 'fixture', 'payload': {
            'repositories': {'app': {'location': str(repo)}}, 'runs': {'r': run}}})
        script = ("import json,pathlib; print(json.dumps({'findings': [] if "
                  "pathlib.Path('flag.txt').read_text(encoding='utf-8') == 'PASS' else [{'id':'F'}]}))")
        request = {'run_id': 'r', 'actor_id': 'worker', 'gates': {'security': {
            'repo_id': 'app', 'command': [sys.executable, '-c', script],
            'contract': {'kind': 'json-report', 'version': 1}}}}
        state = read_state(self.root)
        transact(self.root, state['version'], 'config',
                 {'kind': 'domain.harden.configure', 'payload': {'request': request}})
        failed = _run_gate(self.root, 'r', 'security', 'initial-gate')
        self.assertFalse(failed['proof']['passed'])

        def fix(*_args):
            (repo / 'flag.txt').write_text('PASS')
            return {'status': 'allow'}

        with patch('workflow_lib.repair_runtime.invoke', side_effect=fix):
            result = self.run_cycle('real-gate')
        self.assertEqual(result['remaining_failures']['gate_ids'], [])
        self.assertEqual(read_state(self.root)['data']['runs']['r']['hardening_proofs']['security']['passed'], True)


if __name__ == '__main__':
    unittest.main()
