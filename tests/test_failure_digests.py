import copy
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.failure_digests import build_failure_digest
from workflow_lib.evidence import _blob
from workflow_lib.document_units import canonical


class FailureDigestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def result(self, stdout, stderr=''):
        return {'passed': False, 'exit_code': 7, 'token': 'attempt', 'output_hash': 'original',
                'stdout_ref': _blob(self.root, stdout), 'stderr_ref': _blob(self.root, stderr)}

    def test_json_repeated_failures_preserve_verdict_ids_counts_and_evidence(self):
        value = self.result('{"tests":[{"id":"a","outcome":"failed","message":"same é"},{"id":"b","outcome":"failed","message":"same é"},{"id":"c","outcome":"error"},{"id":"d","outcome":"skipped"}]}')
        before = copy.deepcopy(value)
        digest = build_failure_digest(value, {'root': str(self.root)})
        self.assertEqual(digest['counts'], {'failed': 2, 'error': 1, 'skipped': 1, 'passed': 0})
        self.assertEqual(digest['original_result']['exit_code'], 7)
        self.assertEqual(digest['original_result']['token'], 'attempt')
        self.assertIn(['a', 'b'], [group['ids'] for group in digest['groups']])
        self.assertTrue(digest['artifact_refs'])
        self.assertEqual(value, before)

    def test_junit_unittest_and_malformed_reports(self):
        reports = [('<testsuite><testcase classname="A" name="test"><failure>broken</failure></testcase></testsuite>', '', 'json'),
                   ('', 'test_x (A) ... ERROR\nRan 1 test\nFAILED (errors=1)', 'unittest')]
        for stdout, stderr, format in reports:
            result = self.result(stdout, stderr)
            result['report_format'] = format
            digest = build_failure_digest(result, {'root': str(self.root)})
            self.assertEqual(digest['status'], 'available')
            self.assertEqual(digest['counts']['failed'] + digest['counts']['error'], 1)
        invalid = self.result('not a report')
        invalid['failure'] = 'UNSUPPORTED_TEST_REPORT'
        digest = build_failure_digest(invalid, {'root': str(self.root)})
        self.assertEqual(digest['status'], 'unavailable')
        self.assertIsNone(digest['counts'])
        self.assertFalse(digest['original_result']['passed'])

    def test_large_logs_output_budget_unicode_and_deadline(self):
        value = self.result('é' * 1000000)
        value['test_counts'] = {'failed': 3, 'error': 0, 'skipped': 2, 'passed': 0}
        digest = build_failure_digest(value, {'root': str(self.root)}, max_bytes=2048)
        self.assertLessEqual(len(canonical(digest)), 2048)
        self.assertEqual(digest['counts']['failed'], 3)
        self.assertTrue(digest['omissions'])
        expired = build_failure_digest(value, {'root': str(self.root)}, deadline=time.monotonic() - 1)
        self.assertEqual(expired['status'], 'unavailable')
        self.assertFalse(expired['original_result']['passed'])

    def test_advisory_hook_failure_does_not_change_original_result(self):
        from unittest.mock import patch
        from workflow_lib.lifecycle_hooks import verification_projection
        value = {'passed': False, 'exit_code': 5}
        with patch('workflow_lib.lifecycle_hooks.run_lifecycle_hook', return_value={'status': 'advisory-error', 'reason_code': 'HOOK_DEADLINE_EXCEEDED'}):
            projected = verification_projection(self.root, value)
        self.assertEqual(projected['passed'], False)
        self.assertEqual(projected['exit_code'], 5)
        self.assertEqual(value, {'passed': False, 'exit_code': 5})

    def test_interrupted_unittest_output_does_not_claim_complete_totals(self):
        result = self.result('', 'test_a (Suite) ... ok\ntest_b (Suite) ... ')
        result.update(report_format='unittest', failure='TIMEOUT', exit_code=None)
        digest = build_failure_digest(result, {'root': str(self.root)})
        self.assertEqual(digest['status'], 'unavailable')
        self.assertIsNone(digest['counts'])
        self.assertTrue(digest['omissions'])

    def test_unittest_missing_summary_or_count_mismatch_has_unknown_totals(self):
        for report in ('test_a (Suite) ... ok\nRan 2 tests\nOK',
                       'test_a (Suite) ... ok\nRan 1 test',
                       'test_a (Suite) ... ok\nOK',
                       'test_a (Suite) ... ok\nRan 1 test\nFAILED (errors=1)'):
            with self.subTest(report=report):
                result = self.result('', report)
                result['report_format'] = 'unittest'
                digest = build_failure_digest(result, {'root': str(self.root)})
                self.assertEqual(digest['status'], 'unavailable')
                self.assertIsNone(digest['counts'])
