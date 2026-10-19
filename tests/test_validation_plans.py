from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.validation_plans import plan_validation
from workflow_lib.document_units import digest


class ValidationPlanTests(unittest.TestCase):
    def setUp(self):
        self.config = {'schema_version': 1, 'required_checks': [{'id': 'unit', 'argv': ['python3', '-m', 'unittest']},
            {'id': 'docs', 'argv': ['python3', 'scripts/check_documentation.py', '--check']},
            {'id': 'full', 'argv': ['python3', '-m', 'unittest', 'discover']}],
            'mappings': [{'paths': ['src/**', 'tests/**'], 'component': 'runtime', 'check_ids': ['unit']},
                         {'paths': ['docs/**', 'src/docs.py'], 'check_ids': ['docs']}]}

    def test_overlapping_mappings_and_complete_required_set(self):
        plan = plan_validation(['src/docs.py'], self.config)
        self.assertEqual(plan['focused_check_ids'], ['docs', 'unit'])
        self.assertEqual(plan['required_check_ids'], ['docs', 'full', 'unit'])
        self.assertEqual(plan['outstanding_check_ids'], plan['required_check_ids'])
        self.assertFalse(plan['grants_gate_pass'])
        self.assertEqual(plan['configuration_hash'], digest(self.config))

    def test_unmapped_missing_or_stale_mapping_falls_back_to_full(self):
        for changed, config, observed in [(['old/deleted.py', 'new/renamed.py'], self.config, None),
                (['src/a.py'], {**self.config, 'mappings': []}, None), (['src/a.py'], self.config, 'stale')]:
            plan = plan_validation(changed, config, observed_config_hash=observed)
            self.assertEqual(plan['focused_check_ids'], plan['required_check_ids'])
            self.assertEqual(plan['selection_mode'], 'full')

    def test_missing_invalid_configuration_never_guesses_commands(self):
        for config in (None, {}, {'schema_version': 1, 'required_checks': []},
                       {**self.config, 'mappings': [{'paths': ['src/**'], 'check_ids': ['unknown']}]}):
            plan = plan_validation(['src/a.py'], config)
            self.assertEqual(plan['status'], 'unavailable')
            self.assertFalse(plan['grants_gate_pass'])
            self.assertEqual(plan['focused_check_ids'], [])

    def test_cli_plans_without_executing_or_advancing_any_gate(self):
        import json
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / 'checks.json'
            config.write_text(json.dumps(self.config))
            root = Path(temp) / 'control'
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'),
                'build', 'validation-plan', '--root', str(root), '--config', str(config), '--changed-path', 'src/a.py'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan = json.loads(result.stdout)['result']
            self.assertEqual(plan['focused_check_ids'], ['unit'])
            self.assertEqual(plan['required_check_ids'], ['docs', 'full', 'unit'])
            self.assertFalse((root / 'events').exists())
