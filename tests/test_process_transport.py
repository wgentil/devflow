import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from skills.workflow.scripts.workflow_lib.process_transport import JsonLineProcess, bounded_capture


class ProcessTransportTests(unittest.TestCase):
    def test_bounded_capture_collects_both_pipes(self):
        code = "import sys; sys.stdout.write('hello'); sys.stderr.write('warning')"
        result = bounded_capture([sys.executable, '-c', code], Path.cwd(), 5, 1024)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, 'hello', 'warning'))

    def test_bounded_capture_limits_output(self):
        code = "import sys; sys.stdout.write('x'*2048)"
        with self.assertRaises(ValueError):
            bounded_capture([sys.executable, '-c', code], Path.cwd(), 5, 1024)

    def test_json_line_process_round_trip(self):
        code = "import sys; line=sys.stdin.readline(); sys.stdout.write(line); sys.stdout.flush()"
        with JsonLineProcess([sys.executable, '-c', code], Path.cwd(), 1024) as process:
            process.send({'id': 1}, 5)
            self.assertEqual(process.next(5), {'id': 1})

class CleanupTests(unittest.TestCase):
    def test_exited_windows_process_does_not_call_taskkill_on_reused_pid(self):
        from unittest.mock import Mock, patch
        from skills.workflow.scripts.workflow_lib import process_transport
        process = Mock(pid=1234)
        process.poll.return_value = 0
        with patch.object(process_transport.os, 'name', 'nt'):
            with patch.object(process_transport.subprocess, 'run') as command:
                process_transport.stop_tree(process)
        command.assert_not_called()

class WindowsJobTests(unittest.TestCase):
    def test_job_cleanup_uses_attached_handle_and_closes_it(self):
        from unittest.mock import Mock
        from skills.workflow.scripts.workflow_lib.process_transport import WindowsJob
        api = Mock()
        api.CreateJobObjectW.return_value = 10
        api.AssignProcessToJobObject.return_value = 1
        api.TerminateJobObject.return_value = 1
        api.CloseHandle.return_value = 1
        process = Mock(_handle=20)
        job = WindowsJob(process, api=api)
        job.stop()
        api.AssignProcessToJobObject.assert_called_once()
        api.TerminateJobObject.assert_called_once()
        api.CloseHandle.assert_called_once()
