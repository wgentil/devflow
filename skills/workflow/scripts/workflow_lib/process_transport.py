"""Pipe transports that do not rely on selector support for anonymous pipes."""
from __future__ import annotations
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import threading


def stop_tree(process: subprocess.Popen) -> None:
    """Stop the spawned process group/tree, or report uncertain cleanup."""
    if os.name == 'nt':
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                capture_output=True, timeout=5, check=False)
        if result.returncode and process.poll() is None:
            raise RuntimeError('Windows process tree cleanup could not be confirmed')
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
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    return subprocess.Popen(argv, cwd=cwd, stdin=stdin, stdout=subprocess.PIPE,
                            stderr=stderr, creationflags=flags,
                            start_new_session=os.name != 'nt')


def bounded_capture(argv: list[str], cwd: str | Path, timeout: float, limit: int) -> subprocess.CompletedProcess:
    process = spawn(argv, cwd)
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
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError('Native host timed out') from exc
        for thread in threads:
            thread.join(timeout=2)
        if exceeded.is_set():
            raise ValueError('Native output exceeds the supported bound')
        if any(thread.is_alive() for thread in threads):
            raise TimeoutError('Native output drain did not finish')
        return subprocess.CompletedProcess(argv, process.returncode,
            buffers[0].decode('utf-8', 'replace'), buffers[1].decode('utf-8', 'replace'))
    finally:
        if process.poll() is None:
            stop_tree(process)


class JsonLineProcess:
    def __init__(self, argv: list[str], cwd: str | Path, limit: int):
        self.process = spawn(argv, cwd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.limit = limit
        self.incoming = queue.Queue(maxsize=4096)
        self._send_lock = threading.Lock()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self):
        buffer = bytearray()
        try:
            while chunk := os.read(self.process.stdout.fileno(), 65536):
                buffer.extend(chunk)
                if len(buffer) > self.limit:
                    self.incoming.put(ValueError('Native protocol output exceeds bound'))
                    return
                while b'\n' in buffer:
                    line, _, rest = buffer.partition(b'\n')
                    buffer = bytearray(rest)
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeError):
                        value = ValueError('Native protocol returned malformed JSON')
                    self.incoming.put(value)
        finally:
            self.incoming.put(EOFError('Native protocol closed'))

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
