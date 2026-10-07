import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.repair import failure_delta, repair_decision


class RepairDecisionTests(unittest.TestCase):
    def run_record(self):
        return {
            'id': 'run-1', 'status': 'active', 'actors': {'implementer': 'worker-1'},
            'repair_policy': {'enabled': True, 'max_attempts': 3,
                              'max_elapsed_ms': 100000, 'max_estimated_cost': 10,
                              'no_progress_window': 2},
            'repair_cycles': [], 'plan': {'work_items': []}, 'items': {},
            'required_hardening_gates': ['security'],
            'hardening_config_hash': 'cfg',
            'hardening_proofs': {'security': {'passed': False, 'failure': 'GATE_FINDINGS',
                                               'config_hash': 'cfg'}},
            'unresolved_findings': [],
        }

    def test_failing_gate_is_scoped(self):
        decision = repair_decision(self.run_record(), 1000)
        self.assertEqual(decision['status'], 'ready')
        self.assertEqual(decision['scope']['gate_ids'], ['security'])
        self.assertEqual(decision['scope']['implementer_actor'], 'worker-1')
        self.assertEqual(decision['remaining']['attempts'], 3)

    def test_review_finding_routes_to_implementer(self):
        run = self.run_record()
        run['required_hardening_gates'] = []
        run['unresolved_findings'] = [
            {'id': 'F-2', 'status': 'open', 'item_id': 'W-2'},
            {'id': 'F-1', 'status': 'open', 'item_id': 'W-1'},
        ]
        decision = repair_decision(run, 1000)
        self.assertEqual(decision['status'], 'ready')
        self.assertEqual(decision['scope']['finding_ids'], ['F-1', 'F-2'])
        self.assertEqual(decision['scope']['item_ids'], ['W-1', 'W-2'])
        self.assertEqual(decision['scope']['implementer_actor'], 'worker-1')
        reordered = dict(run, unresolved_findings=list(reversed(run['unresolved_findings'])))
        self.assertEqual(failure_delta(run)['digest'], failure_delta(reordered)['digest'])

    def test_unavailable_proof_is_not_green(self):
        run = self.run_record()
        run['hardening_proofs'] = {}
        decision = repair_decision(run, 1000)
        self.assertNotEqual(decision['status'], 'complete')
        self.assertIn('security', decision['scope']['gate_ids'])

    def test_manual_default_has_no_dispatch(self):
        run = self.run_record()
        run.pop('repair_policy')
        decision = repair_decision(run, 1000)
        self.assertEqual(decision['status'], 'blocked')
        self.assertEqual(decision['reason_code'], 'REPAIR_DISABLED')
        self.assertEqual(decision['scope']['gate_ids'], ['security'])


if __name__ == '__main__':
    unittest.main()
