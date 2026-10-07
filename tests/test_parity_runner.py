import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.parity_runner import verify_pilot


class ParityRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / 'fixture.txt').write_text('same input')

    def tearDown(self): self.temp.cleanup()

    def pilot(self, legacy=None, replacement=None, comparator=None):
        digest = hashlib.sha256((self.repo / 'fixture.txt').read_bytes()).hexdigest()
        command = [sys.executable, '-c', "from pathlib import Path; Path('out.txt').write_text(Path('fixture.txt').read_text())"]
        return {'fixtures': [{'path': 'fixture.txt', 'sha256': digest}],
                'legacy_argv': legacy or command, 'replacement_argv': replacement or command,
                'legacy_output_path': 'out.txt', 'replacement_output_path': 'out.txt',
                'comparator': comparator or {'kind': 'exact-bytes', 'version': 1}}

    def test_same_input_matching_output_passes(self):
        proof = verify_pilot(self.pilot(), self.repo, 10)
        self.assertTrue(proof['passed'])
        self.assertEqual(proof['input_hashes']['fixture.txt'],
                         hashlib.sha256(b'same input').hexdigest())

    def test_different_fixture_bytes_fail(self):
        pilot = self.pilot()
        (self.repo / 'fixture.txt').write_text('changed')
        self.assertEqual(verify_pilot(pilot, self.repo, 10)['failure'], 'FIXTURE_CHANGED')

    def test_missing_output_fails(self):
        pilot = self.pilot(replacement=[sys.executable, '-c', 'pass'])
        self.assertEqual(verify_pilot(pilot, self.repo, 10)['failure'], 'OUTPUT_MISSING')

    def test_declared_ignored_field_only(self):
        first = [sys.executable, '-c', "from pathlib import Path; Path('out.txt').write_text('{\"value\":1,\"time\":1}')"]
        second = [sys.executable, '-c', "from pathlib import Path; Path('out.txt').write_text('{\"value\":1,\"time\":2}')"]
        pilot = self.pilot(first, second, {'kind': 'json-fields', 'version': 1, 'ignore': ['time']})
        self.assertTrue(verify_pilot(pilot, self.repo, 10)['passed'])
        pilot['comparator']['ignore'] = []
        self.assertEqual(verify_pilot(pilot, self.repo, 10)['failure'], 'OUTPUT_DIFFERENCE')

    def test_command_timeout_fails(self):
        pilot = self.pilot(legacy=[sys.executable, '-c', 'import time; time.sleep(2)'])
        self.assertEqual(verify_pilot(pilot, self.repo, 1)['failure'], 'TIMEOUT')


if __name__ == '__main__': unittest.main()
