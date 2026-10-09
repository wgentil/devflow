import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.project_setup import initialize_project_documents
from workflow_lib.store import WorkflowError, transact, read_state
from workflow_lib.ground_interview import inspect_ground_interview, require_ground_interview
from workflow_lib.repo_input_gate import require_current_inputs

TOPICS = (
    'product-users', 'constraints', 'architecture', 'languages',
    'coding-standards', 'lint-format', 'data', 'database', 'api-layer',
    'ui-framework', 'design-system', 'accessibility-localization',
    'security-privacy', 'integrations', 'testing', 'performance-reliability',
    'deployment-release', 'operations', 'team-conventions',
)


class GroundInterviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'; self.project.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        initialize_project_documents(self.project, {'mode': 'project-only'}, 'setup')
        self.path = self.project / 'docs/devflow-ground-interview.json'

    def write(self, topics):
        self.path.write_text(json.dumps({'schema_version': 1, 'topics': topics}))

    def complete_topics(self):
        return {name: {'status': 'answered', 'material': True, 'decision': f'Decision for {name}'}
                for name in TOPICS}

    def test_new_project_requires_visible_interview_before_work(self):
        manifest = json.loads((self.project / 'docs/devflow-context.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['ground_interview']['path'], 'docs/devflow-ground-interview.json')
        report = inspect_ground_interview(self.project)
        self.assertFalse(report['ready'])
        self.assertEqual(report['missing_topics'], list(TOPICS))
        with self.assertRaises(WorkflowError) as caught: require_ground_interview(self.project)
        self.assertEqual(caught.exception.code, 'GROUND_INTERVIEW_REQUIRED')

    def test_material_deferral_blocks_but_optional_deferral_is_recorded(self):
        topics = self.complete_topics()
        topics['database'] = {'status': 'deferred', 'material': True, 'reason': 'Persistence choice pending'}
        topics['ui-framework'] = {'status': 'deferred', 'material': False, 'reason': 'No UI in first increment'}
        self.write(topics)
        report = inspect_ground_interview(self.project)
        self.assertEqual(report['unresolved_material'], ['database'])
        with self.assertRaises(WorkflowError) as caught: require_ground_interview(self.project)
        self.assertEqual(caught.exception.code, 'GROUND_INTERVIEW_INCOMPLETE')
        topics['database'] = {'status': 'answered', 'material': True, 'decision': 'Use PostgreSQL'}
        self.write(topics)
        self.assertTrue(require_ground_interview(self.project)['ready'])

    def test_established_decision_needs_source_and_not_applicable_needs_reason(self):
        topics = self.complete_topics()
        topics['architecture'] = {'status': 'established', 'material': True, 'decision': 'Modular monolith'}
        self.write(topics)
        with self.assertRaises(WorkflowError) as caught: inspect_ground_interview(self.project)
        self.assertEqual(caught.exception.code, 'INVALID_GROUND_INTERVIEW')
        topics['architecture']['sources'] = ['project:docs/architecture.md']
        topics['ui-framework'] = {'status': 'not-applicable', 'material': False, 'reason': 'CLI only'}
        self.write(topics)
        self.assertTrue(require_ground_interview(self.project)['ready'])

    def test_legacy_manifest_without_interview_field_stays_compatible(self):
        manifest = self.project / 'docs/devflow-context.json'
        value = json.loads(manifest.read_text(encoding='utf-8')); value.pop('ground_interview')
        manifest.write_text(json.dumps(value))
        self.assertFalse(inspect_ground_interview(self.project)['required'])
        self.assertTrue(require_ground_interview(self.project)['ready'])

    def test_ground_check_cli_reports_missing_and_ready(self):
        entry = ROOT / 'skills/workflow/scripts/run.py'
        command = [sys.executable, str(entry), 'setup', 'ground-check', '--project-dir', str(self.project)]
        missing = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 0, missing.stdout + missing.stderr)
        self.assertFalse(json.loads(missing.stdout)['ready'])
        self.write(self.complete_topics())
        ready = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(ready.returncode, 0, ready.stdout + ready.stderr)
        self.assertTrue(json.loads(ready.stdout)['ready'])

    def test_plan_preflight_blocks_new_project_until_material_choices_resolved(self):
        control = self.project / '.devflow/control'
        transact(control, 0, 'seed', {'kind': 'fixture', 'payload': {
            'repositories': {'app': {'location': str(self.project.resolve())}},
            'spec_pair': {'repo_id': 'app'}}})
        with patch('workflow_lib.repo_input_gate.require_current_spec', return_value={}):
            with patch('workflow_lib.document_approvals.require_current_governing_inputs', return_value={}):
                with self.assertRaises(WorkflowError) as caught:
                    require_current_inputs(control, read_state(control), 'plan-validation')
                self.assertEqual(caught.exception.code, 'GROUND_INTERVIEW_REQUIRED')
                self.write(self.complete_topics())
                self.assertIn('grounding', require_current_inputs(control, read_state(control), 'plan-validation'))
