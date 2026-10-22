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

    def test_json_line_process_accepts_burst_of_short_lines(self):
        code = "import sys;sys.stdout.write(''.join('{\"id\":%d}\\n'%i for i in range(200)));sys.stdout.flush()"
        with JsonLineProcess([sys.executable, '-c', code], Path.cwd(), 1024) as process:
            self.assertEqual([process.next(5)['id'] for _ in range(200)], list(range(200)))
            self.assertEqual(process.process.wait(timeout=5), 0)

    def test_json_line_process_caps_cumulative_output(self):
        code = "import sys;sys.stdout.write('{\"id\":1}\\n'*300);sys.stdout.flush()"
        with JsonLineProcess([sys.executable, '-c', code], Path.cwd(), 64) as process:
            with self.assertRaisesRegex(ValueError, 'cumulative'):
                for _ in range(300):
                    process.next(5)

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
        api.QueryInformationJobObject.side_effect = lambda handle, kind, info, size, returned: (setattr(info._obj, 'ActiveProcesses', 0) if kind == 1 else None) or 1
        process = Mock(_handle=20)
        job = WindowsJob(process, api=api)
        job.stop()
        api.AssignProcessToJobObject.assert_called_once()
        api.TerminateJobObject.assert_called_once()
        api.CloseHandle.assert_called_once()

class WindowsJobCompletionTests(unittest.TestCase):
    def job(self, counts, *, query_ok=True):
        from unittest.mock import Mock
        from skills.workflow.scripts.workflow_lib.process_transport import WindowsJob
        api = Mock()
        api.CreateJobObjectW.return_value = 10
        api.AssignProcessToJobObject.return_value = 1
        api.TerminateJobObject.return_value = 1
        api.CloseHandle.return_value = 1
        counts = iter(counts)
        def query(handle, kind, info, size, returned):
            self.assertEqual(handle, 10)
            if kind == 1:
                info._obj.ActiveProcesses = next(counts)
            return int(query_ok)
        api.QueryInformationJobObject.side_effect = query
        return WindowsJob(Mock(_handle=20), api=api), api

    def test_job_waits_for_zero_active_processes_before_closing(self):
        from unittest.mock import patch
        job, api = self.job([2, 1, 0])
        with patch('skills.workflow.scripts.workflow_lib.process_transport.time.sleep'):
            job.stop()
        self.assertEqual(api.QueryInformationJobObject.call_count, 4)
        self.assertEqual(api.method_calls[-1][0], 'CloseHandle')
        self.assertIsNone(job.handle)

    def test_unconfirmed_job_cleanup_raises_and_retains_handle_for_retry(self):
        from unittest.mock import patch
        job, api = self.job([1])
        with patch('skills.workflow.scripts.workflow_lib.process_transport.time.monotonic', side_effect=[0, 6]):
            with self.assertRaisesRegex(TimeoutError, 'cleanup'):
                job.stop()
        api.CloseHandle.assert_not_called()
        self.assertEqual(job.handle, 10)
        api.QueryInformationJobObject.side_effect = lambda handle, kind, info, size, returned: (setattr(info._obj, 'ActiveProcesses', 0) if kind == 1 else None) or 1
        job.stop()
        api.CloseHandle.assert_called_once()

    def test_job_query_failure_does_not_report_confirmed_cleanup(self):
        job, api = self.job([0], query_ok=False)
        with self.assertRaisesRegex(OSError, 'QueryInformationJobObject'):
            job.stop()
        api.CloseHandle.assert_not_called()

    def test_member_handles_are_signaled_before_job_accounting_can_allow_return(self):
        job, api = self.job([0])
        queries = iter([[123], []])
        def query(handle, kind, info, size, returned):
            if kind == 3:
                ids = next(queries)
                info._obj.NumberOfAssignedProcesses = len(ids)
                info._obj.NumberOfProcessIdsInList = len(ids)
                for index, pid in enumerate(ids):
                    info._obj.ProcessIdList[index] = pid
            return 1
        api.QueryInformationJobObject.side_effect = query
        api.OpenProcess.return_value = 99
        api.IsProcessInJob.side_effect = lambda handle, job_handle, member: (setattr(member._obj, 'value', 1) or 1)
        api.WaitForSingleObject.side_effect = [258, 258]
        api.TerminateProcess.return_value = 1
        with self.assertRaisesRegex(TimeoutError, 'cleanup'):
            job.stop()
        api.TerminateJobObject.assert_not_called()
        api.CloseHandle.assert_not_called()

    @unittest.skipUnless(sys.platform == 'win32', 'requires native Windows Job and process handles')
    def test_exited_leader_descendant_is_signaled_before_close_returns(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        child = 'import time;time.sleep(60)'
        code = f'import subprocess,sys,json;p=subprocess.Popen([sys.executable,"-c",{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);print(json.dumps({{"pid":p.pid}}),flush=True)'
        process = JsonLineProcess([sys.executable, '-c', code], Path.cwd(), 1024)
        handle = None
        try:
            pid = process.next(10)['pid']
            handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
            self.assertTrue(handle)
            self.assertEqual(process.process.wait(timeout=10), 0)
            process.close()
            self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0, 'descendant still running when cleanup returned')
        finally:
            if process.process._devflow_job.handle is not None:
                process.close()
            if handle:
                kernel.CloseHandle(handle)
