import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.document_units import select_document_units
from workflow_lib.store import WorkflowError


class DocumentUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = {}

    def source(self, name, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8', newline='\n')
        self.sources[name] = {'root': str(self.root), 'path': path}
        return name

    def select(self, name, selector=None):
        return select_document_units(self.sources, [{'source_id': name, 'selector': selector or {'kind': 'whole'}}], {})

    def test_fence_aware_exact_markdown_heading(self):
        self.source('guide', 'guide.md', '# Guide\n## Rules\nA\n```md\n## Other\n```\n### Nested\nB\n## Other\nC\n')
        result = self.select('guide', {'kind': 'markdown', 'heading': ['Guide', 'Rules']})
        self.assertIn('### Nested\nB', result['units'][0]['content'])
        self.assertNotIn('\nC', result['units'][0]['content'])
        self.source('bad', 'bad.md', '## Same\na\n## Same\nb\n')
        with self.assertRaises(WorkflowError):
            self.select('bad', {'kind': 'markdown', 'heading': ['Same']})

    def test_json_pointer_escapes_arrays_and_root(self):
        self.source('api', 'api.json', json.dumps({'a/b': {'~key': ['é']}}))
        result = self.select('api', {'kind': 'json-pointer', 'pointer': '/a~1b/~0key/0'})
        self.assertEqual(json.loads(result['units'][0]['content']), 'é')
        self.assertEqual(len(self.select('api')['units']), 1)
        for pointer in ('no-slash', '/a~2b', '/a~1b/~0key/01', '/missing'):
            with self.subTest(pointer=pointer), self.assertRaises(WorkflowError):
                self.select('api', {'kind': 'json-pointer', 'pointer': pointer})

    def test_reference_closure_cycle_diamond_and_registered_paths(self):
        self.source('a', 'a.json', '{"pick":{"$ref":"b.json#/B"}}')
        self.source('b', 'b.json', '{"B":{"allOf":[{"$ref":"c.json#/C"},{"$ref":"c.json#/C"}]}}')
        self.source('c', 'c.json', '{"C":{"$ref":"b.json#/B"}}')
        result = self.select('a', {'kind': 'json-pointer', 'pointer': '/pick'})
        self.assertEqual(len(result['units']), 3)
        self.assertEqual(set(result['source_hashes']), {'a', 'b', 'c'})
        self.assertTrue(all(u['reasons'] for u in result['units']))

    def test_unknown_remote_and_escaped_dependencies_fail(self):
        for ref in ('https://example.test/a', 'unregistered.json#/x', '../escape.json', '#anchor'):
            self.source('api', 'api.json', json.dumps({'$ref': ref}))
            with self.subTest(ref=ref), self.assertRaises(WorkflowError):
                self.select('api')

    def test_unsupported_id_scopes_and_cross_repository_escape_fail(self):
        self.source('api', 'api.json', '{"$id":"https://example.test/base/","pick":{"$ref":"b.json#/B"}}')
        self.source('b', 'b.json', '{"B":{}}')
        with self.assertRaises(WorkflowError):
            self.select('api', {'kind': 'json-pointer', 'pointer': '/pick'})
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other)
            (outside / 'b.json').write_text('{"B":{}}', newline='\n')
            self.sources['outside'] = {'root': str(outside), 'path': 'b.json'}
            self.source('api', 'api.json', json.dumps({'$ref': str(outside / 'b.json') + '#/B'}))
            with self.assertRaises(WorkflowError):
                self.select('api')

    def test_yaml_whole_file_and_private_or_symlink_paths(self):
        self.source('yaml', 'api.yaml', 'openapi: 3.0.0\n')
        self.assertIn('openapi', self.select('yaml')['units'][0]['content'])
        with self.assertRaises(WorkflowError):
            self.select('yaml', {'kind': 'json-pointer', 'pointer': '/openapi'})
        self.source('private', '.devflow/secret.json', '{}')
        with self.assertRaises(WorkflowError):
            self.select('private')
        with tempfile.TemporaryDirectory() as outside:
            (self.root / 'link').symlink_to(outside, target_is_directory=True)
            self.sources['escape'] = {'root': str(self.root), 'path': 'link/a.json'}
            with self.assertRaises(WorkflowError):
                self.select('escape')

    def test_declared_dependencies_and_missing_required(self):
        self.source('a', 'a.md', 'A')
        self.source('b', 'b.md', 'B')
        policy = {'sources': {'a': {'dependencies': ['b']}, 'b': {'dependencies': []}}}
        result = select_document_units(self.sources, [{'source_id': 'a'}], policy)
        self.assertEqual(result['required_ids'], ['a', 'b'])
        del self.sources['b']
        with self.assertRaises(WorkflowError):
            select_document_units(self.sources, [{'source_id': 'a'}], policy)
