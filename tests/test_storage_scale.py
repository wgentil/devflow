"""End-to-end storage scale and complete-corpus payload evidence."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/benchmark_control_storage.py'

class StorageScaleTests(unittest.TestCase):
    def benchmark(self):
        self.assertTrue(SCRIPT.is_file(),'actual owned-corpus command benchmark is required')
        spec=importlib.util.spec_from_file_location('control_storage_benchmark',SCRIPT)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_history_growth_keeps_operational_reads_scoped(self):
        report=self.benchmark().run_scale_benchmark(counts=(10,1000))
        self.assertEqual([row['terminal_runs'] for row in report['profiles']],[10,1000])
        for profile in report['profiles']:
            self.assertTrue(profile['full_audit_valid'])
            for sample in profile['commands']:
                self.assertEqual(sample['terminal_body_reads'],0,sample)
                self.assertEqual(sample['historical_package_reads'],0,sample)
                self.assertEqual(sample['old_segment_reads'],0,sample)
                self.assertGreater(sample['queries'],0)
                self.assertGreater(sample['elapsed_ms'],0)
        small,large=report['profiles']
        for a,b in zip(small['commands'],large['commands']):
            self.assertEqual(a['command'],b['command'])
            self.assertLessEqual(b['queries'],a['queries']+10)
            self.assertLessEqual(b['sqlite_vm_steps'],max(1000,a['sqlite_vm_steps']*4))
        self.assertTrue(report['owned_roots_removed'])

    def test_review_corpus_meets_hot_payload_ratio(self):
        report=self.benchmark().run_review_corpus_benchmark(review_bytes=100*1024*1024)
        self.assertGreaterEqual(report['closed_review_logical_bytes'],100*1024*1024)
        self.assertTrue(report['full_audit_valid']);self.assertTrue(report['logical_parity'])
        self.assertLess(report['hot_payload_ratio'],0.1)
        self.assertEqual(report['actual_reclaimed_bytes'],max(0,report['before_total_bytes']-report['physical']['total_bytes']))
        self.assertGreater(report['physical']['database_bytes'],0)
        self.assertGreater(report['physical']['objects_bytes'],0)
        self.assertGreater(report['physical']['total_bytes'],report['physical']['database_bytes'])
        self.assertTrue(report['owned_roots_removed'])
