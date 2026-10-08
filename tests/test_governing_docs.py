import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib import governing_docs as gd
from workflow_lib.store import WorkflowError

class GoverningDocsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = self.repo('project')
        self.org = self.repo('org')
        self.write(self.org, 'rules.md', '## A: First\noriginal\n## B: Second\nretained\n')
        self.org_manifest = {'schema_version': 1, 'id': 'example-org', 'documents': [{'category': 'coding-standards', 'path': 'rules.md', 'rule_ids': ['A', 'B']}]}
        self.project_manifest = {'schema_version': 1, 'org': {'id': 'example-org', 'url': str(self.org)}, 'documents': [], 'overrides': {}}
        self.manifests()
    def repo(self, name):
        path = Path(self.tmp.name) / name
        path.mkdir()
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        subprocess.run(['git', '-C', str(path), '-c', 'user.name=Test', '-c', 'user.email=test@example.com', 'commit', '--allow-empty', '-qm', 'initial'], check=True)
        return path
    def write(self, repo, path, text):
        dest = repo / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
    def manifests(self):
        self.write(self.org, 'docs/devflow-org.json', json.dumps(self.org_manifest))
        self.write(self.project, 'docs/devflow-context.json', json.dumps(self.project_manifest))
    def resolve(self):
        return gd.resolve_governing_docs(self.project, self.org)
    def test_inheritance_override_and_unrelated_digest(self):
        original = self.resolve()
        self.write(self.org, 'unrelated.md', 'edit')
        self.assertEqual(original['effective_digest'], self.resolve()['effective_digest'])
        self.write(self.project, 'local.md', '## A: First\nlocal\n')
        self.project_manifest['documents'] = [{'category': 'coding-standards', 'path': 'local.md', 'rule_ids': ['A']}]
        self.project_manifest['overrides'] = {'A': 'local.md'}
        self.manifests()
        result = self.resolve()
        self.assertEqual(result['rules']['A']['provenance']['source'], 'project')
        self.assertEqual(result['rules']['B'], original['rules']['B'])
        self.assertNotEqual(result['effective_digest'], original['effective_digest'])
    def test_project_only_design_system_machine_rule(self):
        self.write(self.project, 'tokens.json', '{"color":"blue"}')
        self.project_manifest.pop('org')
        self.project_manifest['documents'] = [{'category': 'design-system', 'path': 'tokens.json', 'rule_ids': ['UI']}]
        self.manifests()
        self.assertEqual(gd.resolve_governing_docs(self.project, None)['rules']['UI']['category'], 'design-system')
    def test_sealed_override_blocks(self):
        self.org_manifest['documents'][0]['sealed_rule_ids'] = ['A']
        self.write(self.project, 'local.md', '## A: First\nlocal\n')
        self.project_manifest['documents'] = [{'category': 'coding-standards', 'path': 'local.md', 'rule_ids': ['A']}]
        self.project_manifest['overrides'] = {'A': 'local.md'}
        self.manifests()
        with self.assertRaises(WorkflowError): self.resolve()
    def test_invalid_ids_categories_and_paths(self):
        for changes in ({'rule_ids': ['A', 'A']}, {'rule_ids': ['missing']}, {'category': 'unknown'}, {'path': '../outside.md'}):
            with self.subTest(changes=changes):
                self.org_manifest['documents'][0] = {'category': 'coding-standards', 'path': 'rules.md', 'rule_ids': ['A', 'B'], **changes}
                self.manifests()
                with self.assertRaises(WorkflowError): self.resolve()
    def test_symlink_and_ignored_paths_block(self):
        (self.org / 'link.md').symlink_to('rules.md')
        for path in ('link.md', 'rules.md'):
            if path == 'rules.md': self.write(self.org, '.gitignore', 'rules.md\n')
            self.org_manifest['documents'][0]['path'] = path
            self.manifests()
            with self.assertRaises(WorkflowError): self.resolve()
    def test_unavailable_org_never_uses_stale_checkout(self):
        self.project_manifest['org']['url'] = str(Path(self.tmp.name) / 'missing.git')
        self.manifests()
        with self.assertRaises(WorkflowError) as error: self.resolve()
        self.assertEqual(error.exception.code, 'GOVERNING_SOURCE_UNAVAILABLE')

    def test_cli_explicit_repository_resolution(self):
        self.project_manifest.pop('org')
        self.manifests()
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'), 'context', 'resolve', '--project-repo', str(self.project)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('effective_digest', result.stdout)
