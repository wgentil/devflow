"""PR package completeness and freshness regressions."""
import tempfile
import unittest
from pathlib import Path
import subprocess

from skills.workflow.scripts.workflow_lib.pr_reviews import prepare_pr_review, validate_pr_snapshot


class PrReviewPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=self.repo, text=True).strip()
        self.git = git
        git('init', '-q')
        git('config', 'user.email', 'test@example.com')
        git('config', 'user.name', 'Test')
        (self.repo / 'a.txt').write_text('one\n')
        git('add', '.'); git('commit', '-qm', 'base')
        self.base = git('rev-parse', 'HEAD')
        (self.repo / 'a.txt').write_text('two\n')
        (self.repo / 'binary.bin').write_bytes(b'\x00\x01\x02')
        git('add', '.'); git('commit', '-qm', 'change')
        self.head = git('rev-parse', 'HEAD')
        self.run = {'id': 'run-1', 'plan': {'spec_hash': 'spec-1', 'work_items': [
            {'id': 'w1', 'requirement_ids': ['r1'], 'acceptance_criteria': ['works']}]
        }, 'actors': {'implementer': 'dev'}}
        self.snapshot = {'pr_id': '123', 'pr_number': 1, 'owner': 'o', 'repo': 'r',
            'base_branch': 'main', 'base_sha': self.base, 'head_sha': self.head,
            'title': 'Change', 'body': 'Reason', 'changed_files': 2,
            'files': [{'filename': 'a.txt'}, {'filename': 'binary.bin'}],
            'files_complete': True, 'commits': [{'sha': self.head}], 'commits_complete': True,
            'checks': [{'name': 'unit', 'status': 'completed', 'conclusion': 'success'}],
            'checks_complete': True, 'comments': [], 'comments_complete': True,
            'reviews': [], 'reviews_complete': True, 'mergeable': True,
            'governing_digest': 'rules-1'}
        self.run['pending_pr'] = {'pr_id': '123', 'pr_number': 1, 'owner': 'o', 'repo': 'r',
            'base_branch': 'main', 'base_sha': self.base, 'head_sha': self.head}

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_includes_binary_and_every_file(self):
        package = prepare_pr_review(self.run, self.snapshot, self.repo)
        self.assertEqual(package['changed_files'], ['a.txt', 'binary.bin'])
        self.assertIn('GIT binary patch', package['batches'][0]['diff'])
        self.assertEqual(package['role'], 'pr')
        validate_pr_snapshot(package, self.snapshot)

    def test_truncated_files_block(self):
        self.snapshot['files'] = self.snapshot['files'][:1]
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            prepare_pr_review(self.run, self.snapshot, self.repo)

    def test_missing_ci_blocks(self):
        self.snapshot['checks'] = []
        with self.assertRaisesRegex(ValueError, 'CI'):
            prepare_pr_review(self.run, self.snapshot, self.repo)

    def test_changed_base_or_rules_rejected(self):
        package = prepare_pr_review(self.run, self.snapshot, self.repo)
        self.snapshot['governing_digest'] = 'rules-2'
        with self.assertRaisesRegex(ValueError, 'changed'):
            validate_pr_snapshot(package, self.snapshot)

    def test_fork_head_unavailable_blocks_clearly(self):
        self.snapshot['head_sha'] = 'f' * 40
        self.run['pending_pr']['head_sha'] = 'f' * 40
        with self.assertRaisesRegex(ValueError, 'locally available'):
            prepare_pr_review(self.run, self.snapshot, self.repo)

    def test_renamed_file_retains_original_path_in_full_diff(self):
        (self.repo / 'a.txt').write_text('one\n')
        self.git('mv', 'a.txt', 'renamed.txt')
        self.git('add', '-A')
        self.git('commit', '-qm', 'rename')
        self.snapshot['head_sha'] = self.git('rev-parse', 'HEAD')
        self.snapshot['commits'].append({'sha': self.snapshot['head_sha']})
        self.snapshot['files'] = [{'filename': 'renamed.txt'}, {'filename': 'binary.bin'}]
        self.run['pending_pr']['head_sha'] = self.snapshot['head_sha']
        package = prepare_pr_review(self.run, self.snapshot, self.repo)
        self.assertIn('rename from a.txt', package['full_diff'])
        self.assertIn('rename to renamed.txt', package['full_diff'])
