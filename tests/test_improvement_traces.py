import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.improvement_traces import project_run_trace
from workflow_lib.store import WorkflowError


class ImprovementTraceTests(unittest.TestCase):
    def state(self):
        return {'data': {'runs': {'r': {'id': 'r', 'status': 'active',
                'improvement_trace_enabled': True, 'plan': {'work_items': []},
                'native_invocations': {'i': {'status': 'allow', 'output': 'SECRET-TEXT'}},
                'model_receipts': {'i': {'observed': {'model': 'm', 'effort': 'high'},
                                         'prompt': 'SECRET-TEXT'}},
                'repair_cycles': [{'cycle_id': 'c', 'input_delta_hash': 'before',
                                   'output_delta_hash': 'after', 'status': 'recorded'}],
                'unresolved_findings': [{'id': 'F1', 'detail': 'SECRET-TEXT'}],
                'hardening_proofs': {'g': {'passed': False, 'output': 'SECRET-TEXT'}}}},
                'usage': {'events': []}}}

    def test_opt_in_required(self):
        state = self.state()
        state['data']['runs']['r'].pop('improvement_trace_enabled')
        with self.assertRaises(WorkflowError):
            project_run_trace(state, 'r', True)

    def test_trace_excludes_secret_content(self):
        trace = project_run_trace(self.state(), 'r', True)
        self.assertNotIn('SECRET-TEXT', str(trace))
        self.assertEqual(trace['finding_ids'], ['F1'])
        self.assertEqual(trace['model_observations'][0]['model'], 'm')

    def test_missing_usage_is_unknown(self):
        self.assertEqual(project_run_trace(self.state(), 'r', True)['usage_status'], 'unknown')

    def test_repair_delta_visible(self):
        trace = project_run_trace(self.state(), 'r', False)
        self.assertEqual(trace['repair_deltas'][0]['input_delta_hash'], 'before')
        self.assertEqual(trace['repair_deltas'][0]['output_delta_hash'], 'after')


if __name__ == '__main__': unittest.main()
