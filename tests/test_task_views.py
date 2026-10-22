import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.task_views import build_task_view, governing_selections
from workflow_lib.store import WorkflowError
from workflow_lib.document_units import canonical


class TaskViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'guide.md').write_text('# Guide\n\nRequired 東京\n')
        (self.root / 'rules.md').write_text('# Rules\n## G1: Safety\nNever skip checks.\n## Additional constraints\nNever skip credentials.\n## G2: Optional\nOther rule.\n')
        self.sources = {'guide': {'root': str(self.root), 'path': 'guide.md'},
                        'rules': {'root': str(self.root), 'path': 'rules.md'}}
        self.spec = {'mode': 'new', 'requirements': [
            {'id': 'R1', 'title': 'Greeting', 'text': 'Return hello', 'acceptance_criteria': ['こんにちは'], 'provenance': {'kind': 'authored'}},
            {'id': 'R2', 'text': 'Unselected requirement', 'acceptance_criteria': ['other'], 'provenance': {'kind': 'assumed', 'assumption': 'visible'}}]}
        self.run = {'id': 'run', 'plan': {'work_items': [{'id': 'W1', 'requirement_ids': ['R1']}, {'id': 'W2', 'requirement_ids': ['R2']}]}}
        self.envelope = {'run_id': 'run', 'blockers': ['human approval outstanding'], 'authorization_scope': {'write': False}}
        self.selection = {'spec': self.spec, 'item_ids': ['W1'], 'stage': 'implementation',
            'documents': [{'source_id': 'guide'}], 'governing': {'G1': {'source_id': 'rules',
            'selector': {'kind': 'markdown', 'heading': ['Rules', 'G1: Safety']}, 'sealed': True}}}

    def build(self, **kwargs):
        return build_task_view(self.run, self.envelope, self.selection, self.sources, {}, root=self.root / 'control', **kwargs)

    def test_complete_selected_requirements_governance_and_docs(self):
        before = copy.deepcopy(self.selection)
        value = self.build()
        text = canonical(value).decode()
        self.assertIn('Return hello', text)
        self.assertIn('Never skip checks', text)
        self.assertIn('Required 東京', text)
        self.assertNotIn('Unselected requirement', text)
        self.assertEqual(value['task_view']['required_ids'], ['G1', 'R1', 'guide'])
        self.assertEqual(value['task_view']['coverage']['missing_ids'], [])
        self.assertEqual(self.selection, before)
        self.assertEqual(value['blockers'], self.envelope['blockers'])

    def test_json_representation_has_no_second_markdown_copy(self):
        value = self.build(representation='json')
        spec_unit = next(u for u in value['task_view']['units'] if u['id'] == 'specification')
        self.assertEqual(json.loads(spec_unit['content'])['requirements'][0]['text'], 'Return hello')
        self.assertNotIn('## R1:', canonical(value).decode())

    def test_missing_inputs_fail_instead_of_claiming_complete(self):
        for change in ('spec', 'requirement', 'rule'):
            selection = copy.deepcopy(self.selection)
            if change == 'spec':
                selection.pop('spec')
            elif change == 'requirement':
                selection['spec']['requirements'] = []
            else:
                selection['governing']['G1']['source_id'] = 'unknown'
            with self.subTest(change=change), self.assertRaises(WorkflowError):
                build_task_view(self.run, self.envelope, selection, self.sources, {}, root=None)

    def test_exact_budget_overflow_optional_omission_and_references(self):
        full = self.build()
        self.assertEqual(full['budget']['serialized_bytes'], len(canonical(full)))
        with self.assertRaises(WorkflowError) as caught:
            self.build(max_bytes=100)
        self.assertEqual(caught.exception.code, 'CONTEXT_BUDGET_EXCEEDED')
        self.assertTrue(caught.exception.details['artifact_refs'])
        self.assertIn('rescope', caught.exception.details['action'].lower())
        (self.root / 'optional.md').write_text('x' * 10000)
        self.sources['optional'] = {'root': str(self.root), 'path': 'optional.md'}
        self.selection['documents'].append({'source_id': 'optional', 'required': False})
        value = self.build(max_bytes=8000)
        self.assertIn('optional', value['budget']['optional_omitted'])
        refs = self.build(max_bytes=4000, output_mode='refs')
        self.assertNotIn('units', refs['task_view'])
        self.assertEqual(refs['blockers'], self.envelope['blockers'])
        self.assertTrue(refs['task_view']['artifact_id'])

    def test_governing_receipt_applies_overrides_and_irrelevance(self):
        import base64
        def encoded(text):
            return base64.b64encode(text.encode()).decode()
        local = {'documents': [{'path': 'rules.md', 'category': 'test-strategy', 'rule_ids': ['G1', 'G2']}], 'overrides': {'G1': 'rules.md'}}
        org = {'documents': [{'path': 'org.md', 'category': 'test-strategy', 'rule_ids': ['G1'], 'sealed_rule_ids': []}]}
        receipt = {'applicable_rule_ids': ['G1'], 'files': {
            'app:manifest': {'repo_id': 'app', 'path': 'docs/devflow-context.json', 'content_base64': encoded(json.dumps(local))},
            'org:manifest': {'repo_id': 'org', 'path': 'docs/devflow-org.json', 'content_base64': encoded(json.dumps(org))},
            'app:rules': {'repo_id': 'app', 'path': 'rules.md', 'content_base64': encoded((self.root/'rules.md').read_text())}}}
        selected, sources = governing_selections(receipt, {'app': {'location': str(self.root)}, 'org': {'location': str(self.root)}})
        self.assertEqual(set(selected), {'G1'})
        self.assertEqual(selected['G1']['source_id'], 'governing:app:rules.md')
        self.assertIn('governing:app:rules.md', sources)

    def test_governing_rule_projection_preserves_non_rule_heading_constraints(self):
        import base64
        import subprocess
        from workflow_lib.governing_docs import _rules
        text = (self.root / 'rules.md').read_text().replace('Never skip credentials.', 'Never skip credentials.\n```markdown\n## Example heading\nPreserve fenced details.\n```')
        (self.root / 'rules.md').write_text(text)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '-qm', 'fixture'], check=True)
        manifest = {'documents': [{'path': 'rules.md', 'category': 'test-strategy', 'rule_ids': ['G1', 'G2']}]}
        def file(path, text):
            return {'repo_id': 'app', 'path': path, 'content_base64': base64.b64encode(text.encode()).decode()}
        receipt = {'applicable_rule_ids': ['G1'], 'files': {
            'manifest': file('docs/devflow-context.json', json.dumps(manifest)),
            'rules': file('rules.md', (self.root / 'rules.md').read_text())}}
        selected, sources = governing_selections(receipt, {'app': {'location': str(self.root)}})
        selection = {**self.selection, 'governing': selected}
        view = build_task_view(self.run, self.envelope, selection, {**self.sources, **sources}, {}, root=None)
        text = canonical(view).decode()
        self.assertIn('Never skip credentials.', text)
        self.assertIn('Preserve fenced details.', text)
        self.assertNotIn('Other rule.', text)
        unit = next(unit for unit in view['task_view']['units'] if unit['source_id'] == 'governing:app:rules.md')
        self.assertEqual(unit['content'], _rules(self.root.resolve(), manifest, 'project')['G1']['content'])

    def test_shared_diagram_survives_selected_requirement_projection(self):
        self.selection['spec']['diagrams']=[{'title':'Shared contract','mermaid':'flowchart LR\n    Shared --> Contract'}]
        for representation in ('markdown','json'):
            value=self.build(representation=representation)
            self.assertIn('Shared --> Contract',canonical(value).decode())
            self.assertNotIn('Unselected requirement',canonical(value).decode())
