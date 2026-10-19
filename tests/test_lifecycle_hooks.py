import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.lifecycle_hooks import run_lifecycle_hook, prepared_context
from workflow_lib.document_units import canonical, digest
from workflow_lib.process_liveness import process_alive
from workflow_lib.store import WorkflowError


class LifecycleHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_allowlisted_invalidation_records_limits_and_identities(self):
        result = run_lifecycle_hook('invalidate-context', {'root': str(self.root), 'observed_sources': {}, 'policy_hash': digest({})})
        self.assertEqual(result['status'], 'allow')
        self.assertEqual(result['limits'], {'deadline_seconds': 5, 'max_bytes': 8192})
        self.assertEqual(result['output_bytes'], len(canonical(result)))
        self.assertIn('configuration_hash', result)
        self.assertIn('source_hashes', result)

    def test_invalid_operation_request_and_limits(self):
        for name, request, limits in [('shell', {}, {}), ('prepare-context', [], {}),
                ('prepare-context', {}, {'deadline_seconds': 0}), ('prepare-context', {}, {'max_bytes': 10})]:
            result = run_lifecycle_hook(name, request, required=True, **limits)
            self.assertEqual(result['status'], 'block')
        missing = run_lifecycle_hook('prepare-context', {'root': str(self.root), 'run_id': 'missing'}, required=True)
        self.assertEqual(missing['status'], 'block')
        self.assertNotEqual(missing['reason_code'], 'HOOK_COMPLETE')

    def test_deadline_kills_worker_and_advisory_preserves_verdict(self):
        worker = self.root / 'slow.py'
        pid = self.root / 'pid'
        worker.write_text('import json,os,sys,time\nfrom pathlib import Path\nx=json.loads(sys.stdin.readline())\nPath(x["request"]["pid_path"]).write_text(str(os.getpid()))\ntime.sleep(30)\n')
        with patch('workflow_lib.lifecycle_hooks.WORKER_PATH', worker):
            result = run_lifecycle_hook('digest-verification', {'root': str(self.root), 'pid_path': str(pid),
                'result': {'passed': False, 'exit_code': 7}}, deadline_seconds=0.3)
        self.assertEqual(result['status'], 'advisory-error')
        self.assertEqual(result['reason_code'], 'HOOK_DEADLINE_EXCEEDED')
        self.assertEqual(result['original_result'], {'passed': False, 'exit_code': 7})
        self.assertFalse(process_alive(int(pid.read_text())))

    def test_oversized_and_malformed_worker_output_fail_explicitly(self):
        worker = self.root / 'bad.py'
        for output in ('not-json', json.dumps({'status': 'allow', 'result': 'é' * 6000})):
            worker.write_text('import sys\nsys.stdin.readline()\nprint(' + repr(output) + ')\n')
            with patch('workflow_lib.lifecycle_hooks.WORKER_PATH', worker):
                result = run_lifecycle_hook('prepare-context', {'root': str(self.root)}, required=True, max_bytes=2048)
            self.assertEqual(result['status'], 'block')
            self.assertIn(result['reason_code'], {'HOOK_OUTPUT_INVALID', 'HOOK_OUTPUT_OVERFLOW'})

    def test_preparation_failure_stops_operation(self):
        with self.assertRaises(WorkflowError):
            prepared_context(self.root, {'id': 'missing'}, {}, [], stage='implementation')
