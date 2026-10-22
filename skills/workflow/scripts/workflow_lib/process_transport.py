"""Pipe transports that do not rely on selector support for anonymous pipes."""
from __future__ import annotations
import json
import ctypes
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading
import time


class JobAccounting(ctypes.Structure):
    # Fixed Windows ABI sizes also permit protocol tests on non-Windows hosts.
    _fields_ = [(name, ctypes.c_int64) for name in
                ('TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')] + [
                (name, ctypes.c_uint32) for name in
                ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses', 'TotalTerminatedProcesses')]


class JobProcessIds(ctypes.Structure):
    _fields_ = [('NumberOfAssignedProcesses', ctypes.c_uint32),
                ('NumberOfProcessIdsInList', ctypes.c_uint32),
                ('ProcessIdList', ctypes.c_size_t * 4096)]


class WindowsJob:
    """Own a Windows process tree without signaling the caller's console."""
    def __init__(self, process: subprocess.Popen, api=None):
        if api is None:
            import ctypes
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            api.CreateJobObjectW.restype = ctypes.c_void_p
            api.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
            api.AssignProcessToJobObject.restype = ctypes.c_int
            api.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            api.TerminateJobObject.restype = ctypes.c_int
            api.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            api.QueryInformationJobObject.restype = ctypes.c_int
            api.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                                                     ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
            api.OpenProcess.restype = ctypes.c_void_p
            api.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
            api.IsProcessInJob.restype = ctypes.c_int
            api.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
            api.TerminateProcess.restype = ctypes.c_int
            api.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            api.WaitForSingleObject.restype = ctypes.c_uint32
            api.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            api.GetLastError.restype = ctypes.c_uint32
            api.CloseHandle.restype = ctypes.c_int
            api.CloseHandle.argtypes = [ctypes.c_void_p]
        self.api = api
        self.members = {}
        self.handle = api.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError('CreateJobObjectW failed')
        if not api.AssignProcessToJobObject(self.handle, int(process._handle)):
            api.CloseHandle(self.handle)
            self.handle = None
            raise OSError('AssignProcessToJobObject failed')

    def _drain_members(self, deadline):
        # TerminateJobObject may detach members before their handles are signaled.
        # Retain verified member handles, terminate individually, and rescan for
        # children created during the previous snapshot before draining the Job.
        while True:
            info = JobProcessIds()
            if not self.api.QueryInformationJobObject(self.handle, 3, ctypes.byref(info), ctypes.sizeof(info), None):
                raise OSError('QueryInformationJobObject failed; tree cleanup is unconfirmed')
            if info.NumberOfAssignedProcesses > info.NumberOfProcessIdsInList or info.NumberOfProcessIdsInList > 4096:
                raise OSError('Windows process list exceeds cleanup bound')
            pids = list(info.ProcessIdList[:info.NumberOfProcessIdsInList])
            for pid in pids:
                if pid not in self.members:
                    handle = self.api.OpenProcess(0x00101001, False, pid)  # synchronize/query/terminate
                    if not handle:
                        if self.api.GetLastError() == 87:  # process exited during query
                            continue
                        raise OSError('OpenProcess failed; tree cleanup is unconfirmed')
                    member = ctypes.c_int()
                    if not self.api.IsProcessInJob(handle, self.handle, ctypes.byref(member)) or not member.value:
                        self.api.CloseHandle(handle)
                        raise OSError('Process job identity is unconfirmed')
                    self.members[pid] = handle
            for handle in self.members.values():
                if self.api.WaitForSingleObject(handle, 0) != 0:
                    # A process already exiting may reject TerminateProcess
                    # before its handle is signaled. Only the bounded wait
                    # establishes completion, regardless of termination's return.
                    self.api.TerminateProcess(handle, 1)
                    remaining = max(0, int((deadline - time.monotonic()) * 1000))
                    if self.api.WaitForSingleObject(handle, remaining) != 0:
                        raise TimeoutError('Windows tree cleanup is unconfirmed')
            if not pids:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError('Windows tree cleanup is unconfirmed')
            time.sleep(0.01)

    def stop(self):
        if self.handle is None:
            return
        deadline = time.monotonic() + 5
        self._drain_members(deadline)
        if not self.api.TerminateJobObject(self.handle, 1):
            raise OSError('TerminateJobObject failed; tree cleanup is unconfirmed')
        while True:
            info = JobAccounting()
            if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None):
                raise OSError('QueryInformationJobObject failed; tree cleanup is unconfirmed')
            if info.ActiveProcesses == 0:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Windows tree cleanup is unconfirmed')
            time.sleep(0.01)
        for pid, handle in list(self.members.items()):
            if not self.api.CloseHandle(handle):
                raise OSError("CloseHandle failed after process cleanup")
            del self.members[pid]
        if not self.api.CloseHandle(self.handle):
            raise OSError('CloseHandle failed after tree cleanup')
        self.handle = None


def resume_suspended_process(process: subprocess.Popen) -> None:
    """Resume the sole initial thread only after its process joins the Job."""
    import ctypes
    from ctypes import wintypes

    class THREADENTRY32(ctypes.Structure):
        _fields_ = [(name, wintypes.DWORD) for name in
                    ('dwSize', 'cntUsage', 'th32ThreadID', 'th32OwnerProcessID',
                     'tpBasePri', 'tpDeltaPri', 'dwFlags')]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = (wintypes.HANDLE, ctypes.POINTER(THREADENTRY32))
    kernel.Thread32Next.argtypes = (wintypes.HANDLE, ctypes.POINTER(THREADENTRY32))
    kernel.OpenThread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.ResumeThread.argtypes = (wintypes.HANDLE,)
    kernel.ResumeThread.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
    if snapshot == wintypes.HANDLE(-1).value:
        raise OSError('Cannot enumerate suspended process threads')
    try:
        entry = THREADENTRY32()
        entry.dwSize = ctypes.sizeof(entry)
        found = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.th32OwnerProcessID == process.pid:
                thread = kernel.OpenThread(0x0002, False, entry.th32ThreadID)  # THREAD_SUSPEND_RESUME
                if not thread:
                    raise OSError('Cannot open suspended process thread')
                try:
                    if kernel.ResumeThread(thread) == 0xFFFFFFFF:
                        raise OSError('Cannot resume suspended process thread')
                    return
                finally:
                    kernel.CloseHandle(thread)
            found = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        raise OSError('Suspended process thread is unavailable')
    finally:
        kernel.CloseHandle(snapshot)


def stop_tree(process: subprocess.Popen) -> None:
    """Stop the spawned process group/tree, or report uncertain cleanup."""
    if os.name == 'nt':
        job = getattr(process, '_devflow_job', None)
        if job is not None:
            job.stop()
        elif process.poll() is None:
            raise RuntimeError('Windows process has no attached job; tree cleanup is unconfirmed')
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            if process.poll() is None:
                raise
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            if process.poll() is None:
                raise
    process.wait(timeout=5)


def spawn(argv, cwd, *, stdin=subprocess.DEVNULL, stderr=subprocess.PIPE):
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004) if os.name == 'nt' else 0
    process = subprocess.Popen(argv, cwd=cwd, stdin=stdin, stdout=subprocess.PIPE,
                            stderr=stderr, creationflags=flags,
                            start_new_session=os.name != 'nt')
    if os.name == 'nt':
        try:
            process._devflow_job = WindowsJob(process)
            resume_suspended_process(process)
        except OSError:
            if getattr(process, '_devflow_job', None) is not None:
                process._devflow_job.stop()
            else:
                process.kill()
            process.wait(timeout=5)
            raise
    return process


def bounded_capture(argv: list[str], cwd: str | Path, timeout: float, limit: int) -> subprocess.CompletedProcess:
    process = spawn(argv, cwd)
    deadline = time.monotonic() + timeout
    buffers = [bytearray(), bytearray()]
    exceeded = threading.Event()
    threads = []

    def drain(pipe, target):
        try:
            while chunk := os.read(pipe.fileno(), 65536):
                if len(target) + len(chunk) > limit:
                    exceeded.set()
                    return
                target.extend(chunk)
        finally:
            pipe.close()

    try:
        for pipe, target in zip((process.stdout, process.stderr), buffers):
            thread = threading.Thread(target=drain, args=(pipe, target), daemon=True)
            thread.start(); threads.append(thread)
        try:
            process.wait(timeout=max(deadline - time.monotonic(), 0))
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError('Native host timed out') from exc
        for thread in threads:
            thread.join(timeout=max(deadline - time.monotonic(), 0))
        if exceeded.is_set():
            raise ValueError('Native output exceeds the supported bound')
        if any(thread.is_alive() for thread in threads):
            raise TimeoutError('Native descendant kept an output pipe open')
        return subprocess.CompletedProcess(argv, process.returncode,
            buffers[0].decode('utf-8', 'replace'), buffers[1].decode('utf-8', 'replace'))
    finally:
        stop_tree(process)


class JsonLineProcess:
    def __init__(self, argv: list[str], cwd: str | Path, limit: int):
        self.process = spawn(argv, cwd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.limit = limit
        self.incoming = queue.Queue(maxsize=16)
        self._closed = threading.Event()
        self._send_lock = threading.Lock()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self):
        buffer = bytearray()
        total = 0
        try:
            while chunk := os.read(self.process.stdout.fileno(), 65536):
                total += len(chunk)
                if total > 32 * self.limit:
                    self._offer(ValueError('Native protocol output exceeds cumulative bound'))
                    return
                buffer.extend(chunk)
                while b'\n' in buffer:
                    line, _, rest = buffer.partition(b'\n')
                    buffer = bytearray(rest)
                    if len(line) > self.limit:
                        self._offer(ValueError('Native protocol output exceeds bound'))
                        return
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeError):
                        value = ValueError('Native protocol returned malformed JSON')
                    if not self._offer(value):
                        return
                if len(buffer) > self.limit:
                    self._offer(ValueError('Native protocol output exceeds bound'))
                    return
        finally:
            self._offer(EOFError('Native protocol closed'))

    def _offer(self, value):
        while not self._closed.is_set():
            try:
                self.incoming.put(value, timeout=0.05)
                return True
            except queue.Full:
                pass
        return False

    def send(self, value: dict, timeout: float):
        encoded = (json.dumps(value, separators=(',', ':')) + '\n').encode()
        if len(encoded) > self.limit:
            raise ValueError('Native protocol request exceeds bound')
        done = threading.Event()
        errors = []
        with self._send_lock:
            def write():
                try:
                    self.process.stdin.write(encoded)
                    self.process.stdin.flush()
                except (OSError, ValueError) as exc:
                    errors.append(exc)
                finally:
                    done.set()
            threading.Thread(target=write, daemon=True).start()
            if not done.wait(timeout):
                raise TimeoutError('Native protocol write timed out')
            if errors:
                raise errors[0]

    def next(self, timeout: float) -> dict:
        try:
            value = self.incoming.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError('Native protocol read timed out') from exc
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        self._closed.set()
        try:
            stop_tree(self.process)
        finally:
            self.process.stdin.close()
            self.process.stdout.close()
            self._reader.join(timeout=2)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
