"""Regressions for locale-dependent owned files, using actual dispatch/readers."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
import run
from encoding_fixtures import legacy_path_defaults


class UTF8BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def request(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return str(path)

    def cli(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), legacy_path_defaults():
            status = run.main(argv)
        return status, json.loads(output.getvalue())

    def test_existing_unicode_fixtures_under_legacy_writer(self):
        from test_context_artifacts import ArtifactTests
        from test_task_views import TaskViewTests
        from test_documentation import DocumentationTests
        cases = [(ArtifactTests, 'test_direct_edits_renames_and_selection_changes'),
                 (TaskViewTests, 'test_complete_selected_requirements_governance_and_docs'),
                 (DocumentationTests, 'test_checker_rejects_broken_links_routes_and_unicode_overflow')]
        for cls, method in cases:
            with self.subTest(fixture=cls.__name__), legacy_path_defaults():
                result = unittest.TestResult()
                cls(method).run(result)
                self.assertEqual(result.errors + result.failures, [])

    def test_auxiliary_json_inputs_preserve_unicode(self):
        catalog = self.request('catalog.json', {'stages': [{'id': 'é東京'}]})
        profiles = self.request('profiles.json', {'profiles': {'é東京': {'extensions': ['.é']}}})
        request = self.request('request.json', {'plan': {'work_items': [{'id': 'é東京', 'repo_id': 'é東京'}]},
                                                'repositories': {'é東京': {}}})
        migration = self.request('migration.json', {'increments': {'increments': [{'id': 'é東京', 'criteria': ['P1']}]}, 'parity': [{'id': 'P1'}]})
        export = self.request('export.json', {'title': 'é東京'})
        for argv, expected in [(['docs', '--catalog', catalog, '--profiles', profiles], 'markdown'),
                               (['harden', 'schedule', '--input', request], 'order'),
                               (['migrate', 'validate', '--input', migration], 'ids'),
                               (['stats', 'export', '--input', export], 'output')]:
            with self.subTest(argv=argv):
                status, value = self.cli(argv)
                self.assertEqual(status, 0, value)
                self.assertIn('é東京', str(value[expected]))

    def test_invalid_utf8_input_is_structured_and_does_not_mutate(self):
        source = self.root / 'bad.json'
        source.write_bytes(b'{"title":"\xff"}')
        control = self.root / 'control'
        status, value = self.cli(['stats', 'export', '--input', str(source)])
        self.assertEqual(status, 2, value)
        self.assertEqual(value['error'], 'INVALID_INPUT')
        self.assertEqual(source.read_bytes(), b'{"title":"\xff"}')
        self.assertFalse(control.exists())

    def test_patch_input_preserves_unicode(self):
        from test_test_changes import TestChangeTests
        from workflow_lib.store import transact
        from commands.build import dispatch
        from types import SimpleNamespace
        fixture = TestChangeTests('test_exact_approval_precedes_patch_application_and_records_hashes')
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        control = self.root / 'patch-control'
        transact(control, 0, 'seed', {'kind': 'fixture', 'payload': {
            'runs': {'run-1': fixture.run}, 'repositories': {'app': {'location': str(fixture.repo)}}}})
        # Match the existing locked-test item to its registered repository.
        state = __import__('workflow_lib.store', fromlist=['read_state']).read_state(control)
        fixture.run['plan']['work_items'][0]['repo_id'] = 'app'
        transact(control, state['version'], 'repo', {'kind': 'fixture', 'payload': {'runs': {'run-1': fixture.run}}})
        patch = self.root / 'change.patch'
        patch.write_text(fixture.patch.replace('assert 1 == 2', 'assert 1 == 2  # é東京'), encoding='utf-8')
        parsed = SimpleNamespace(build_command='test-change', test_change_command='propose', root=str(control),
            run_id='run-1', item='W1', patch_file=str(patch), reason='correct expectation', operation_id_explicit=False)
        with legacy_path_defaults():
            result = dispatch(parsed)
        self.assertIn('é東京', str(result['proposal']))

    def test_auxiliary_readers_reject_invalid_utf8_before_domain_work(self):
        bad = self.root / 'bad.json'
        bad.write_bytes(b'{"label":"\xff"}')
        valid = self.request('valid.json', {})
        root = str(self.root / 'uninitialized-control')
        commands = [
            ['issues', 'capture', '--root', root, '--input', str(bad)],
            ['repair', 'configure', '--root', root, '--run-id', 'r', '--input', str(bad)],
            ['improve', 'feedback', '--root', root, '--input', str(bad)],
            ['ingest', '--scope', '.', '--profile-json', str(bad), '--repo-json', valid],
            ['ingest', '--scope', '.', '--profile-json', valid, '--repo-json', str(bad)],
            ['docs', '--catalog', valid, '--profiles', str(bad)],
            ['host', 'task-bind', '--root', root, '--file', str(bad)],
            ['host', 'attach', '--root', root, '--file', valid, '--loaded-release', str(bad)],
        ]
        for operation in ('model-run', 'model-reconcile'):
            commands.append(['host', operation, '--root', root, '--operation-id', 'probe', '--file', str(bad)])
        from workflow_lib.store import read_state
        for argv in commands:
            with self.subTest(argv=argv):
                try:
                    status, value = self.cli(argv)
                except (KeyError, TypeError, ValueError) as exc:
                    self.fail('invalid UTF-8 reached domain work: ' + str(exc))
                self.assertEqual(status, 2, value)
                self.assertEqual(value['error'], 'INVALID_INPUT')
                self.assertIn('utf-8', value['message'])
                self.assertEqual(read_state(Path(root))['version'], 0)
