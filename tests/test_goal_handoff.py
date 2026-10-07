import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.goals import goal_handoff_decision


class GoalHandoffTests(unittest.TestCase):
    def state(self):
        return {'runs': {'r': {'id': 'r', 'status': 'active',
                'plan': {'work_items': []}, 'goal_bindings': {'b': {'host': 'codex',
                'goal_ref': 'codex-secret-id'}}}}}

    def test_cross_host_id_isolation_and_manual_capability(self):
        decision = goal_handoff_decision(self.state(), {'run_id': 'r'}, 'claude')
        self.assertTrue(decision['requires_new_goal'])
        self.assertEqual(decision['reason_code'], 'CAPABILITY_UNAVAILABLE')
        self.assertNotIn('codex-secret-id', str(decision))

    def test_repair_budget_and_user_pause_block(self):
        state = self.state()
        state['runs']['r']['repair_stop'] = {'reason_code': 'SPEND_LIMIT'}
        self.assertEqual(goal_handoff_decision(state, {'run_id': 'r'}, 'claude')['status'], 'blocked')
        state['runs']['r'].pop('repair_stop')
        state['runs']['r']['goal_user_paused'] = True
        self.assertEqual(goal_handoff_decision(state, {'run_id': 'r'}, 'claude')['reason_code'], 'USER_PAUSED')

    def test_stale_proof_does_not_complete_goal(self):
        state = self.state()
        state['runs']['r']['required_hardening_gates'] = ['security']
        state['runs']['r']['hardening_config_hash'] = 'new'
        state['runs']['r']['hardening_proofs'] = {'security': {'passed': True, 'config_hash': 'old'}}
        decision = goal_handoff_decision(state, {'run_id': 'r'}, 'claude')
        self.assertNotEqual(decision['status'], 'complete')


if __name__ == '__main__': unittest.main()
