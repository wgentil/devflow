"""The CI runner must collect later failures and keep a failing process status."""
import contextlib
import importlib.util
import io
import json
import locale
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class PlatformRunnerTests(unittest.TestCase):
    def runner(self):
        self.assertIsNotNone(importlib.util.find_spec('run_platform_tests'), 'full platform report runner is required')
        from run_platform_tests import run_suite
        return run_suite

    def test_runner_collects_later_failures_and_preserves_nonzero_exit(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test_collect.py').write_text('''import unittest
class Cases(unittest.TestCase):
 def test_a_failure(self): self.fail('first failure')
 def test_b_error(self): raise RuntimeError('later error')
 @unittest.skip('fixture skip')
 def test_c_skip(self): pass
 def test_d_pass(self): self.assertEqual(2+2,4)
''', encoding='utf-8')
            report_path = root / 'report.json'
            with contextlib.redirect_stderr(io.StringIO()):
                report = runner(root, ['test_*.py'], report_path)
            self.assertFalse(report['success'])
            self.assertEqual(report['tests_run'], 4)
            self.assertEqual(len(report['failures']), 1)
            self.assertEqual(len(report['errors']), 1)
            self.assertIn('test_b_error', report['errors'][0])
            self.assertEqual(report['skips'][0]['reason'], 'fixture skip')
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/run_platform_tests.py'),
                '--start-dir', str(root), '--output', str(report_path)], capture_output=True, timeout=15)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads(report_path.read_text(encoding='utf-8'))['tests_run'], 4)

    def test_runner_reports_actual_locale_and_counts(self):
        runner = self.runner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'test_locale_fixture.py').write_text('import unittest\nclass Case(unittest.TestCase):\n def test_ok(self): pass\n', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                report = runner(root, ['test_locale_fixture.py'], root / 'report.json')
            self.assertTrue(report['success'])
            self.assertEqual(report['schema_version'], 1)
            self.assertEqual(report['tests_run'], 1)
            self.assertEqual(report['metadata']['preferred_encoding'], locale.getpreferredencoding(False))
            self.assertEqual(report['metadata']['utf8_mode'], sys.flags.utf8_mode)
            self.assertEqual(report['metadata']['python'], sys.version)
