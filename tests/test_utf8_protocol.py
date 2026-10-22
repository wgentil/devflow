"""UTF-8 wire bytes must not depend on the Windows console code page."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
import run
from workflow_lib.store import read_state
ENTRY = ROOT / 'skills/workflow/scripts/run.py'


class UTF8ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='devflow-é東京-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = {**os.environ, 'PYTHONIOENCODING': 'cp1252'}
        self.environment.pop('PYTHONUTF8', None)

    def child(self, argv):
        return subprocess.run([sys.executable, '-X', 'utf8=0', str(ENTRY), *map(str, argv)],
                              capture_output=True, env=self.environment, timeout=15)

    def test_cli_unicode_success_and_error_are_utf8_under_cp1252(self):
        source = self.root / 'request.json'
        source.write_text('{"title":"é東京"}', encoding='utf-8')
        result = self.child(['stats', 'export', '--input', source])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('é東京', json.loads(result.stdout.decode('utf-8'))['output'])
        missing = self.root / 'missing-é東京.json'
        result = self.child(['stats', 'export', '--input', missing])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('missing-é東京.json', json.loads(result.stdout.decode('utf-8'))['message'])

    def registration(self):
        return ['repo', 'register', '--root', str(self.root / 'control'), '--repo-id', 'é東京',
                '--location', str(self.root), '--operation-id', 'register-once']

    def test_unicode_registration_response_and_exact_retry(self):
        first = self.child(self.registration())
        self.assertEqual(first.returncode, 0, first.stderr)
        value = json.loads(first.stdout.decode('utf-8'))
        self.assertEqual(value['repo_id'], 'é東京')
        second = self.child(self.registration())
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue(json.loads(second.stdout)['replayed'])
        state = read_state(self.root / 'control')
        self.assertEqual(state['version'], 1)
        self.assertEqual(list(state['data']['repositories']), ['é東京'])

    def test_stringio_callers_and_exact_output_byte_measurement(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.utf8_io'), 'UTF-8 output adapter is required')
        from workflow_lib.utf8_io import write_utf8
        for stream in (io.StringIO(), io.TextIOWrapper(io.BytesIO(), encoding='cp1252')):
            count = write_utf8('é東京\n', stream=stream)
            self.assertEqual(count, 9)
            if hasattr(stream, 'buffer'):
                self.assertEqual(stream.buffer.getvalue(), b'\xc3\xa9\xe6\x9d\xb1\xe4\xba\xac\n')
                self.assertEqual(stream.encoding, 'cp1252')
            else:
                self.assertEqual(stream.getvalue(), 'é東京\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(run.main(self.registration()), 0)
        self.assertEqual(json.loads(output.getvalue())['repo_id'], 'é東京')

    def test_failed_output_does_not_invent_rollback_or_duplicate_commit(self):
        class BrokenStream(io.StringIO):
            def write(self, value):
                raise OSError('closed downstream pipe')
        with contextlib.redirect_stdout(BrokenStream()), self.assertRaises(OSError):
            run.main(self.registration())
        self.assertEqual(read_state(self.root / 'control')['version'], 1)
        self.assertFalse((self.root / 'control' / 'offload.jsonl').exists(), 'failed output must not be counted as emitted')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(run.main(self.registration()), 0)
        self.assertTrue(json.loads(output.getvalue())['replayed'])
        self.assertEqual(read_state(self.root / 'control')['version'], 1)

    def test_hook_unicode_input_and_diagnostics(self):
        spec = importlib.util.spec_from_file_location('devflow_hook_utf8', ROOT / 'adapters/claude-code/hook.py')
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        payload = {'hook_event_name': 'TaskCompleted', 'cwd': str(self.root), 'session_id': 'é東京', 'task_id': 'é東京'}
        stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload, ensure_ascii=False).encode('utf-8')), encoding='cp1252')
        stderr = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        # Windows CreateProcess errors omit the executable path. Inject the Unicode
        # spawn diagnostic so this output contract is exercised on every OS.
        with patch.object(sys, 'stdin', stdin), patch.object(sys, 'stderr', stderr), patch.object(hook.subprocess, 'run', side_effect=OSError('missing-é東京')):
            status = hook.main()
        self.assertEqual(status, 2)
        self.assertIn('missing-é東京', stderr.buffer.getvalue().decode('utf-8'))

    def test_optional_telemetry_diagnostics_are_utf8_and_cannot_mask_success(self):
        control = self.root / 'control'
        control.mkdir()
        for name in ('offload.jsonl', 'context-metrics.jsonl'):
            (control / name).mkdir()
        result = self.child(self.registration())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.decode('utf-8'))['repo_id'], 'é東京')
        self.assertIn('é東京', result.stderr.decode('utf-8'))
        class BrokenStream(io.StringIO):
            def write(self, value):
                raise OSError('closed diagnostic pipe')
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(BrokenStream()):
            self.assertEqual(run.main(self.registration()), 0)
        self.assertTrue(json.loads(output.getvalue())['replayed'])
        self.assertEqual(read_state(control)['version'], 1)

    def test_context_view_diagnostic_does_not_raise(self):
        from workflow_lib.context_metrics import record_context_view
        stderr = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        with contextlib.redirect_stderr(stderr), patch('workflow_lib.context_metrics.measure_context_view', side_effect=ValueError('é東京')):
            result = record_context_view(self.root, {}, operation_id='v', operation='view')
        self.assertFalse(result['recorded'])
        self.assertIn('é東京', stderr.buffer.getvalue().decode('utf-8'))
