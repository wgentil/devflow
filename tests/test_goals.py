import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.goals import goal_contract
from workflow_lib.journal_domains import digest
from workflow_lib.store import read_state, transact, WorkflowError


class GoalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        run = {'id': 'r', 'status': 'active', 'plan': {'work_items': [{'id': 'W1'}]},
               'items': {'W1': {'status': 'pending', 'attempts': []}},
               'required_hardening_gates': ['security'], 'repair_policy': {'enabled': False}}
        binding = {'binding_id': 'b', 'revision': 1, 'run_id': 'r', 'host': 'codex',
                   'role': 'implementer', 'status': 'active', 'actor_id': 'worker',
                   'release': {'release_id': 'v1'}}
        transact(self.root, 0, 'fixture', {'kind': 'fixture', 'payload': {
            'runs': {'r': run}, 'host_bindings': {'b': binding}}})

    def tearDown(self): self.temp.cleanup()

    def request(self):
        run = read_state(self.root)['data']['runs']['r']
        return {'binding_id': 'b', 'revision': 1, 'host': 'codex', 'run_id': 'r',
                'goal_ref': 'thread-goal-1', 'capability_version': 'manual-v1',
                'contract_hash': digest(goal_contract(run)),
                'authorization': {'approved': True, 'actor_id': 'human'}}

    def bind(self, request, operation='bind'):
        state = read_state(self.root)
        return transact(self.root, state['version'], operation,
                        {'kind': 'domain.host.goal-bind', 'payload': {'request': request}})

    def test_contract_has_verification_and_blocked_condition(self):
        contract = goal_contract(read_state(self.root)['data']['runs']['r'])
        self.assertIn('verification', contract)
        self.assertIn('blocked_condition', contract)
        self.assertIn('security', str(contract))

    def test_binding_requires_user_authorization(self):
        request = self.request()
        request['authorization'] = {'approved': False, 'actor_id': 'human'}
        with self.assertRaises(WorkflowError): self.bind(request)

    def test_goal_complete_does_not_advance_run(self):
        self.bind(self.request())
        run = read_state(self.root)['data']['runs']['r']
        self.assertEqual(run['status'], 'active')
        self.assertEqual(run['items']['W1']['status'], 'pending')

    def test_binding_replay_is_idempotent(self):
        request = self.request()
        self.bind(request)
        self.assertTrue(self.bind(request)['replayed'])
        self.assertEqual(len(read_state(self.root)['data']['runs']['r']['goal_bindings']), 1)


if __name__ == '__main__': unittest.main()
