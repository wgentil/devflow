"""Real Git/verification boundaries; locale simulation is not Windows acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from encoding_fixtures import legacy_subprocess_defaults
from workflow_lib.bootstrap import initialize_project
from workflow_lib.store import read_state, transact
from workflow_lib.document_approvals import propose_document_change, approve_document_change
from workflow_lib.governing_docs import canonical_document_bytes
from workflow_lib.evidence import capture_evidence
from workflow_lib.git_paths import resolve_repo_path


class WindowsWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='devflow-é東京-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name).resolve()
        self.repo = self.directory / 'application é東京'
        self.repo.mkdir()
        self.control = self.directory / 'control'
        self.git('init', '-q')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'user.name', 'Fixture')
        self.git('config', 'core.autocrlf', 'false')
        (self.repo / 'test_target.py').write_bytes(b'# locked test\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'base')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, capture_output=True,
                              text=True, encoding='utf-8', check=True).stdout.strip()

    def test_init_resume_and_worktree_in_unicode_directory_without_utf8_override(self):
        with legacy_subprocess_defaults():
            first = initialize_project(self.repo, self.control, 'init', None)
            second = initialize_project(self.repo, self.control, 'resume', None)
        self.assertEqual(Path(first['project_dir']), self.repo)
        self.assertEqual(second['repo_id'], first['repo_id'])
        self.assertEqual(read_state(self.control)['version'], 1)
        worktree = self.directory / 'worktree é東京'
        self.git('worktree', 'add', '-b', 'test-worktree', str(worktree))
        with legacy_subprocess_defaults():
            initialized = initialize_project(worktree, self.directory / 'other-control', 'worktree', None)
        self.assertEqual(Path(initialized['project_dir']), worktree)

    def test_unicode_governing_approval_and_exact_source_hashes(self):
        name = 'rules-é東京.md'
        before = '## A: Rule\nOriginal é東京\n'.encode('utf-8')
        after = '## A: Rule\nChanged é東京\n'.encode('utf-8')
        (self.repo / name).write_bytes(before)
        self.git('add', '.')
        self.git('commit', '-qm', 'rule')
        transact(self.control, 0, 'seed', {'kind': 'fixture', 'payload': {'repositories': {'p': {'location': str(self.repo)}}}})
        (self.repo / name).write_bytes(after)
        with legacy_subprocess_defaults():
            proposal = propose_document_change(self.control, 'p', [name])
            approve_document_change(self.control, proposal['proposal_hash'], 'fixture-human')
        self.assertEqual(proposal['files'][name]['before_hash'], hashlib.sha256(before).hexdigest())
        self.assertEqual(proposal['files'][name]['after_hash'], hashlib.sha256(after).hexdigest())
        self.assertIn('+Changed é東京', proposal['files'][name]['diff'])

    def seed_attempt(self):
        transact(self.control, 0, 'seed', {'kind': 'fixture', 'payload': {
            'repositories': {'app': {'location': str(self.repo)}}, 'runs': {'run': {
                'id': 'run', 'plan': {'work_items': [{'id': 'W1', 'repo_id': 'app', 'kind': 'code'}]},
                'items': {'W1': {'attempts': []}}, 'active_attempt': {'token': 'attempt', 'item_id': 'W1', 'state_version': 1},
                'verification_proofs': {}}}}})

    def capture(self, raw, exit_code, phase='RED', target='é東京'):
        command = [sys.executable, '-c', f'import sys;sys.stdout.buffer.write({raw!r});sys.exit({exit_code})']
        with legacy_subprocess_defaults():
            return capture_evidence(self.control, 'run', 'attempt', phase, command, ['test_target.py'], [target], 10)

    def test_unicode_target_report_records_real_red_green(self):
        self.seed_attempt()
        for phase, outcome, code in [('RED', 'failed', 1), ('GREEN', 'passed', 0)]:
            report = json.dumps({'tests': [{'id': 'é東京', 'outcome': outcome}]}, ensure_ascii=False).encode('utf-8')
            result = self.capture(report, code, phase)
            self.assertTrue(result['passed'], result)
            self.assertEqual(result['target_outcomes'], {'é東京': outcome})
            self.assertEqual((self.control / result['stdout_ref']).read_bytes(), report)

    def test_invalid_report_encoding_never_records_passing_proof(self):
        self.seed_attempt()
        raw = b'{"tests":[{"id":"target","outcome":"failed"}],"note":"\xff"}'
        result = self.capture(raw, 1, target='target')
        self.assertFalse(result['passed'], result)
        self.assertEqual(result['failure'], 'INVALID_TEST_REPORT_ENCODING')
        self.assertEqual((self.control / result['stdout_ref']).read_bytes(), raw)
        self.assertEqual(read_state(self.control)['version'], 1)

    def test_tracked_crlf_and_checkout_conversion_keep_approval_identity(self):
        # Literal expectations guard against normalizing genuinely tracked CRLF.
        self.assertEqual(canonical_document_bytes(b'line\r\n', windows=True, baseline=b'line\n'), b'line\n')
        self.assertEqual(canonical_document_bytes(b'line\r\n', windows=True, baseline=b'line\r\n'), b'line\r\n')
        self.assertEqual(canonical_document_bytes(b'line\r\n', windows=False), b'line\r\n')
        (self.repo / '.gitattributes').write_bytes(b'*.md -text\n')
        name = 'tracked.md'
        raw = b'## A: Rule\r\nTracked CRLF\r\n'
        (self.repo / name).write_bytes(raw)
        self.git('add', '.')
        self.git('commit', '-qm', 'tracked CRLF')
        transact(self.control, 0, 'seed', {'kind': 'fixture', 'payload': {'repositories': {'p': {'location': str(self.repo)}}}})
        proposal = propose_document_change(self.control, 'p', [name])
        self.assertEqual(proposal['files'][name]['before_hash'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(proposal['files'][name]['after_hash'], hashlib.sha256(raw).hexdigest())

    @unittest.skipUnless(os.name == 'nt', 'native NTFS junction containment')
    def test_junction_escape_is_rejected(self):
        outside = self.directory / 'outside'
        outside.mkdir()
        (outside / 'source.txt').write_bytes(b'outside')
        junction = self.repo / 'junction'
        subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(outside)], check=True, capture_output=True)
        try:
            with self.assertRaises(ValueError):
                resolve_repo_path(self.repo, 'junction/source.txt')
        finally:
            junction.rmdir()
        self.assertEqual((outside / 'source.txt').read_bytes(), b'outside')

    def test_git_text_consumers_preserve_unicode_commit_identity(self):
        from workflow_lib import reviews, gates, delivery, governing_docs
        self.git('commit', '--allow-empty', '-qm', 'Feature é東京\n\nWork-Item: W1')
        with legacy_subprocess_defaults():
            for reader in (reviews._git, gates._git_text, delivery._git):
                with self.subTest(reader=reader.__module__):
                    self.assertIn('Feature é東京', reader(self.repo, 'show', '-s', '--format=%B', 'HEAD'))
            self.assertIn('Feature é東京', governing_docs._git(self.repo, 'show', '-s', '--format=%B', 'HEAD').stdout)

    def test_typed_and_improvement_json_preserve_unicode(self):
        from workflow_lib.verifiers import _run
        from workflow_lib.improvement_eval import run_candidate_cases
        raw = '{"label":"é東京"}'.encode('utf-8')
        command = [sys.executable, '-c', f'import sys;sys.stdout.buffer.write({raw!r})']
        with legacy_subprocess_defaults():
            result = _run(command, self.repo, 10)
            self.assertEqual(json.loads(result['stdout']), {'label': 'é東京'})
            report = run_candidate_cases({'artifact_hash': 'fixture'}, [{'case_id': 'case', 'case_hash': 'hash',
                'scoring_version': 1, 'approved_by': 'fixture-human', 'command': command, 'expected': {'label': 'é東京'}}], self.repo)
        self.assertTrue(report['case_results'][0]['passed'], report)


    def test_owned_fixtures_under_windows_text_defaults(self):
        from encoding_fixtures import legacy_path_defaults
        from test_context_input_continuity import ContextInputContinuityTests
        from test_repo_specs import RepoSpecTests
        from test_document_units import DocumentUnitTests
        from test_task_views import TaskViewTests
        cases = [(ContextInputContinuityTests, 'test_windows_checkout_conversion_matches_validated_receipt'),
                 (RepoSpecTests, 'test_frozen_legacy_pair_remains_valid_until_rewritten'),
                 (DocumentUnitTests, 'test_fence_aware_exact_markdown_heading'),
                 (TaskViewTests, 'test_governing_rule_projection_preserves_non_rule_heading_constraints')]
        for cls, method in cases:
            with self.subTest(fixture=cls.__name__), legacy_path_defaults(codec='utf-8', newline='\r\n'):
                result = unittest.TestResult()
                cls(method).run(result)
                self.assertEqual(result.errors + result.failures, [])


    def test_utf8_review_cli_clients_under_legacy_default(self):
        from test_review_input_scope import ReviewInputScopeTests
        with legacy_subprocess_defaults():
            result = unittest.TestResult()
            ReviewInputScopeTests('test_scoped_cli_package_and_record_allow_unrelated_next_item').run(result)
        self.assertEqual(result.errors + result.failures, [])
