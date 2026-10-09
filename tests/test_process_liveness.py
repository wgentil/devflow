import os
import subprocess
import sys
import unittest

from skills.workflow.scripts.workflow_lib.process_liveness import process_alive


class ProcessLivenessTests(unittest.TestCase):
    def test_current_process_is_alive(self):
        self.assertIs(process_alive(os.getpid()), True)

    def test_exited_process_is_gone(self):
        child = subprocess.Popen([sys.executable, '-c', 'pass'])
        child.wait(timeout=5)
        self.assertIs(process_alive(child.pid), False)
