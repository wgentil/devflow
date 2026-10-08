import multiprocessing
import tempfile
import unittest
from pathlib import Path

from skills.workflow.scripts.workflow_lib.platform_lock import exclusive_file


def contend(path, queue):
    with Path(path).open('a+b') as handle:
        try:
            with exclusive_file(handle, blocking=False):
                queue.put('acquired')
        except BlockingIOError:
            queue.put('blocked')


class PlatformLockTests(unittest.TestCase):
    def test_nonblocking_contention_and_release_across_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lock'
            queue = multiprocessing.Queue()
            with path.open('a+b') as handle:
                with exclusive_file(handle):
                    child = multiprocessing.Process(target=contend, args=(str(path), queue))
                    child.start(); child.join(5)
                    self.assertEqual(child.exitcode, 0)
                    self.assertEqual(queue.get(timeout=2), 'blocked')
            child = multiprocessing.Process(target=contend, args=(str(path), queue))
            child.start(); child.join(5)
            self.assertEqual(child.exitcode, 0)
            self.assertEqual(queue.get(timeout=2), 'acquired')

class DirectorySyncTests(unittest.TestCase):
    def test_windows_directory_sync_is_skipped_after_file_fsync(self):
        from unittest.mock import patch
        from skills.workflow.scripts.workflow_lib import platform_lock
        with patch.object(platform_lock.os, 'name', 'nt'):
            with patch.object(platform_lock.os, 'open', side_effect=AssertionError('directory opened')):
                platform_lock.sync_directory(Path('unused'))
