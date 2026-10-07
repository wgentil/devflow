import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.gate_reports import normalize_contract, parse_gate_report
from workflow_lib.hardening import verify_gate


class GateReportTests(unittest.TestCase):
    def setUp(self):
        self.contract = {'kind': 'json-report', 'version': 1}

    def test_zero_exit_with_empty_json_report_fails(self):
        result = parse_gate_report(self.contract, '', '', 0)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failure'], 'REPORT_MISSING')

    def test_valid_empty_findings_passes(self):
        result = parse_gate_report(self.contract, '{"findings":[]}', '', 0)
        self.assertTrue(result['passed'])
        self.assertEqual(result['finding_count'], 0)
        self.assertIsNotNone(result['report_hash'])

    def test_valid_findings_block_gate(self):
        body = '{"findings":[{"id":"security-1"}]}'
        result = parse_gate_report(self.contract, body, '', 0)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failure'], 'GATE_FINDINGS')
        self.assertEqual(result['finding_ids'], ['security-1'])

    def test_malformed_or_placeholder_report_fails(self):
        for body, reason in [('not json', 'REPORT_INVALID'),
                             ('{"findings":[]', 'REPORT_INVALID'),
                             ('<JSON ARRAY HERE>', 'REPORT_INVALID'),
                             ('{"findings":[42]}', 'REPORT_SCHEMA_INVALID'),
                             ('{"findings":[{}]}', 'REPORT_SCHEMA_INVALID')]:
            with self.subTest(body=body):
                result = parse_gate_report(self.contract, body, '', 0)
                self.assertFalse(result['passed'])
                self.assertEqual(result['failure'], reason)

    def test_unknown_contract_fails(self):
        with self.assertRaises(ValueError):
            normalize_contract({'contract': {'kind': 'unknown'}})
        with self.assertRaises(ValueError):
            normalize_contract({'contract': {'kind': 'json-report', 'version': 2}})
        with self.assertRaises(ValueError):
            normalize_contract({'contract': {'kind': 'json-report', 'version': True}})

    def test_exit_status_default_ignores_stdout_shape(self):
        self.assertEqual(normalize_contract({'command': ['true']}), {'kind': 'exit-status'})
        result = parse_gate_report({'kind': 'exit-status'}, 'not json', '', 0)
        self.assertTrue(result['passed'])

    def test_verify_gate_uses_required_report_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            (root / 'file').write_text('baseline')
            subprocess.run(['git', 'add', 'file'], cwd=root, check=True)
            subprocess.run(['git', '-c', 'user.name=test', '-c', 'user.email=test@example.com',
                            'commit', '-qm', 'baseline'], cwd=root, check=True)
            command = [sys.executable, '-c', 'print("not json")']
            result = verify_gate(root, 'run', 'security', command, self.contract)
            self.assertFalse(result['passed'])
            self.assertEqual(result['failure'], 'REPORT_INVALID')
            self.assertEqual(result['argv'], command)
            self.assertIsNotNone(result['output_hash'])


if __name__ == '__main__':
    unittest.main()
