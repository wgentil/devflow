from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.context_regressions import check_context_regressions, evaluate_context_regression

FIXTURE = Path(__file__).resolve().parent / 'fixtures/context-efficiency'


class ContextRegressionTests(unittest.TestCase):
    def test_offline_cold_warm_drift_compaction_handoff_and_equivalent_facts(self):
        report = check_context_regressions(FIXTURE)
        self.assertTrue(report['passed'], report)
        observed = report['observed']
        self.assertLess(observed['delta_bytes'], observed['full_bytes'])
        self.assertLess(observed['full_bytes'], observed['baseline_full_fact_bytes'])
        self.assertEqual(observed['missing_ids'], [])
        self.assertTrue(observed['dependency_complete'])
        self.assertTrue(observed['reconstruction_matches'])
        self.assertTrue(observed['warm_hit'])
        self.assertTrue(observed['dependency_change_rebuilt'])
        self.assertTrue(observed['compaction_full'])
        self.assertTrue(observed['handoff_full'])

    def test_each_missing_fact_or_growth_defect_fails_even_if_payload_shrinks(self):
        report = check_context_regressions(FIXTURE)
        self.assertTrue(report['passed'], report)
        for key, value in [('missing_ids', ['G1']), ('missing_facts', ['required rule']), ('dependency_complete', False),
                ('reconstruction_matches', False), ('cold_retrieval_calls', 999), ('native_context_copies', 2),
                ('duplicate_content_bytes', 99999), ('full_bytes', 999999)]:
            observed = deepcopy(report['observed'])
            observed['full_bytes'] = 1
            observed[key] = value
            failures = evaluate_context_regression(observed, report['policy'])
            self.assertTrue(failures, key)

    def test_offline_hook_shares_fixture_checks(self):
        import tempfile
        from workflow_lib.lifecycle_hooks import run_lifecycle_hook
        with tempfile.TemporaryDirectory() as root:
            response = run_lifecycle_hook('check-context-regressions', {'root': root, 'fixture_root': str(FIXTURE)})
        self.assertEqual(response['status'], 'allow', response)
        self.assertTrue(response['result']['passed'])
