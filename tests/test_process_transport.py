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
