import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.documentation import load_documentation_policy, check_documentation, navigation, discover_documentation
from workflow_lib.store import WorkflowError


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'definitions').mkdir()
        (self.root / 'guide.md').write_text('# Guide\n\nBody\n', encoding='utf-8')
        self.policy = {'schema_version': 1, 'sources': {'guide': {'path': 'guide.md', 'selector': {'kind': 'whole'}, 'dependencies': [], 'classification': 'active'}}, 'stage_reads': {'build': ['guide']}, 'history': ['docs/superpowers/**'], 'budgets': {'entry_bytes': 4096, 'aggregate_entry_bytes': 32768, 'common_bytes': 4096, 'domain_bytes': 12288, 'initial_load_bytes': 20000}}

    def write(self, value=None):
        (self.root / 'definitions/documentation.json').write_text(json.dumps(value or self.policy), encoding='utf-8')

    def test_policy_validation_and_stable_navigation(self):
        self.write()
        policy = load_documentation_policy(self.root)
        self.assertEqual(navigation(policy, 'build'), navigation(policy, 'build'))
        self.assertIn('guide.md', navigation(policy, 'build'))
        self.assertEqual(check_documentation(self.root)['problems'], [])

    def test_invalid_version_dependencies_routes_and_budgets(self):
        for field, value in [('schema_version', 2), ('stage_reads', {'build': ['missing']}), ('budgets', {'domain_bytes': -1})]:
            bad = {**self.policy, field: value}
            self.write(bad)
            with self.subTest(field=field), self.assertRaises(WorkflowError):
                load_documentation_policy(self.root)
        bad = copy.deepcopy(self.policy)
        bad['sources']['guide']['dependencies'] = ['missing']
        self.write(bad)
        with self.assertRaises(WorkflowError):
            load_documentation_policy(self.root)

    def test_duplicate_json_ids_rejected(self):
        self.write()
        p = self.root / 'definitions/documentation.json'
        p.write_text(p.read_text().replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
        with self.assertRaises(WorkflowError):
            load_documentation_policy(self.root)

    def test_discovery_history_and_required_dependency_exceptions(self):
        self.policy['sources']['old'] = {**self.policy['sources']['guide'], 'classification': 'history'}
        self.policy['sources']['guide']['dependencies'] = ['old']
        self.write()
        self.assertEqual(discover_documentation(self.root)['excluded_ids'], ['old'])
        self.assertIn('old', discover_documentation(self.root, include_history=True)['sources'])
        self.assertIn('old', discover_documentation(self.root, required_ids=['guide'])['sources'])

    def test_checker_rejects_broken_links_routes_and_unicode_overflow(self):
        self.write()
        guide = self.root / 'guide.md'
        guide.write_text('# Guide\n\n[missing](missing.md)\n' + 'é' * 7000)
        report = check_documentation(self.root)
        self.assertTrue(any('link' in problem for problem in report['problems']))
        self.assertTrue(any('exceeds' in problem for problem in report['problems']))
        guide.write_text('# Guide\n<!-- devflow:routes:build -->\nstale\n<!-- /devflow:routes -->\n')
        self.assertTrue(any('drifted' in problem for problem in check_documentation(self.root)['problems']))

    def test_shipped_entry_budgets_and_complete_initial_read_routes(self):
        package = Path(__file__).resolve().parents[1]
        report = check_documentation(package)
        self.assertEqual(report['problems'], [])
        self.assertLessEqual(report['aggregate_entry_bytes'], 32768)
        self.assertLessEqual(report['aggregate_entry_bytes'], 65937 // 2)
        self.assertTrue(all(size <= 20000 for size in report['stage_load_bytes'].values()))
