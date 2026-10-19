import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.context_metrics import record_context_measurement, context_statistics, measure_context_view


class ContextMetricTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.view = {'run_id': 'r', 'task_view': {'units': [{'id': 'G1', 'content': 'secret body é', 'content_hash': 'hash'}],
            'required_ids': ['G1'], 'coverage': {'supplied_ids': ['G1'], 'missing_ids': []}, 'cache_outcome': 'miss', 'retrieval_calls': 2}}

    def test_deduplicated_operations_repeated_content_and_no_bodies(self):
        event = measure_context_view(self.view, operation_id='one', operation='run.brief', duration_ms=5)
        self.assertTrue(record_context_measurement(self.root, event)['recorded'])
        self.assertTrue(record_context_measurement(self.root, event)['duplicate'])
        record_context_measurement(self.root, {**event, 'operation_id': 'two', 'cache_outcome': 'hit', 'context_mode': 'delta'})
        stats = context_statistics(self.root, {'run_id': 'r'})
        self.assertEqual(stats['helper_calls'], 2)
        self.assertEqual(stats['cache_outcomes'], {'hit': 1, 'miss': 1})
        self.assertGreater(stats['repeated_content_bytes'], 0)
        self.assertNotIn('secret body', (self.root / 'context-metrics.jsonl').read_text())
        self.assertIsNone(stats['actual_cost'])
        self.assertIsNone(stats['actual_tokens'])
        self.assertEqual(stats['semantic_omissions'], 'unknown')

    def test_measurement_failure_cannot_interrupt_the_measured_operation(self):
        from workflow_lib.context_metrics import record_context_view
        with patch('workflow_lib.context_metrics.measure_context_view', side_effect=ValueError('bad measurement')):
            result = record_context_view(self.root, self.view, operation_id='x', operation='native.input')
        self.assertFalse(result['recorded'])

    def test_partial_coverage_attribution_and_measurement_gaps(self):
        event = measure_context_view(self.view, operation_id='one', operation='native.input', duration_ms=7)
        event['missing_required_ids'] = ['R2']
        event.update(configuration_bytes=10, turn_bytes=30)
        record_context_measurement(self.root, event)
        stats = context_statistics(self.root, {})
        self.assertEqual(stats['missing_required_ids'], ['R2'])
        self.assertEqual(stats['known_native_text_bytes'], 40)
        self.assertIn('hidden', stats['measurement_coverage'])
        self.assertIn('estimate', stats['token_estimate_method'])
        with patch('workflow_lib.context_metrics._append', side_effect=OSError('unavailable')):
            self.assertFalse(record_context_measurement(self.root, event)['recorded'])
        self.assertEqual(event['missing_required_ids'], ['R2'])

    def test_runtime_reported_tokens_are_explicit_and_not_inferred_from_bytes(self):
        event = measure_context_view(self.view, operation_id='native', operation='native.input', duration_ms=1)
        event['runtime_usage'] = {'input_tokens': 30, 'output_tokens': 5}
        record_context_measurement(self.root, event)
        stats = context_statistics(self.root, {})
        self.assertEqual(stats['actual_tokens'], {'input_tokens': 30, 'output_tokens': 5})
        self.assertEqual(stats['usage_source'], 'explicit runtime observations; partial coverage')
        self.assertIsNone(stats['actual_cost'])
