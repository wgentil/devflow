import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/benchmark_context_preparation.py'

class ContextBenchmarkTests(unittest.TestCase):
    def benchmark(self):
        spec=importlib.util.spec_from_file_location('context_benchmark',SCRIPT)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    def test_benchmark_uses_disposable_roots_and_reports_real_counts(self):
        module=self.benchmark();roots=[];original=module.make_context_project
        def tracked(base,**kw):
            roots.append(base);return original(base,**kw)
        with patch.object(module,'make_context_project',side_effect=tracked):
            report=module.run_benchmark(events=20,delivered_runs=3,history_bytes=100000)
        self.assertTrue(roots);self.assertTrue(all(not p.exists() for p in roots))
        self.assertEqual(report['fixture']['events'],20);self.assertEqual(report['fixture']['delivered_runs'],3)
        self.assertGreater(report['fixture']['state_bytes'],100000)
        self.assertGreater(report['initial_replay_ms'],0)
        self.assertEqual(report['replay_counts'],{'initial':1,'next':2,'exact_retry':1,'worker':0})
        self.assertEqual(sum(v for k,v in report['component_bytes'].items() if k!='serialized_bytes'),report['component_bytes']['serialized_bytes'])
        self.assertLessEqual(report['component_bytes']['serialized_bytes'],20000)
    def test_large_history_cli_next_and_exact_replay(self):
        report=self.benchmark().run_benchmark(events=30,delivered_runs=4,history_bytes=200000)
        self.assertTrue(report['token_issued']);self.assertTrue(report['exact_retry_same_token'])
        self.assertEqual(report['attempt_count'],1);self.assertTrue(report['selected_units_match_small'])
        self.assertEqual(report['selected_context_bytes'],report['small_selected_context_bytes'])
        self.assertGreater(report['commit_ms'],0);self.assertGreaterEqual(report['total_ms'],report['worker_ms'])
