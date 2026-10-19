import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.repo_specs import write_spec_pair, read_spec_pair, assert_repo_spec_approval
from workflow_lib.specs import render_spec, content_hash
from workflow_lib.store import WorkflowError


class RepoSpecTests(unittest.TestCase):
    def test_frozen_legacy_pair_remains_valid_until_rewritten(self):
        self.spec['requirements'] = [{'id': 'R1', 'text': 'Say hello',
            'acceptance_criteria': ['greeting returned'], 'provenance': {'kind': 'authored'}}]
        receipt = write_spec_pair(self.repo, self.path, self.spec)
        md = self.repo / receipt['markdown_path']
        old = '# Safari\n\nMode: new\n\n## R1: Say hello\n\nProvenance: authored\n\nAcceptance criteria:\n- greeting returned\n'
        md.write_text(old, encoding='utf-8')
        legacy = read_spec_pair(self.repo, self.path)
        legacy.pop('spec')
        self.assertEqual(assert_repo_spec_approval(self.repo, legacy)['spec'], self.spec)
        current = write_spec_pair(self.repo, self.path, self.spec)
        self.assertNotEqual(current['markdown_hash'], legacy['markdown_hash'])
        self.error('SPEC_APPROVAL_STALE', assert_repo_spec_approval, self.repo, legacy)
        md.write_text(old + '\nUnapproved detail\n', encoding='utf-8')
        self.error('SPEC_PAIR_MISMATCH', read_spec_pair, self.repo, self.path)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='spec café ')
        self.repo = Path(self.temp.name)
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        self.spec = {'mode': 'new', 'title': 'Safari', 'requirements': []}
        self.path = 'docs/specs/0063-ios-safari-suite.json'

    def tearDown(self):
        self.temp.cleanup()

    def error(self, code, function, *args):
        with self.assertRaises(WorkflowError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)

    def test_visible_deterministic_pair_and_unicode_path(self):
        for path in (self.path, 'docs/specs/space café.json'):
            receipt = write_spec_pair(self.repo, path, self.spec)
            self.assertEqual(receipt['content_hash'], content_hash(self.spec))
            self.assertEqual((self.repo / receipt['markdown_path']).read_text(encoding='utf-8'), render_spec(self.spec))
            self.assertEqual(read_spec_pair(self.repo, path)['spec'], self.spec)
            self.assertEqual(write_spec_pair(self.repo, path, self.spec), receipt)
            self.assertEqual(assert_repo_spec_approval(self.repo, receipt)['spec'], self.spec)

    def test_changed_or_missing_half(self):
        receipt = write_spec_pair(self.repo, self.path, self.spec)
        md = self.repo / receipt['markdown_path']
        md.write_text('changed')
        self.error('SPEC_PAIR_MISMATCH', read_spec_pair, self.repo, self.path)
        write_spec_pair(self.repo, self.path, self.spec)
        altered = {**self.spec, 'title': 'Changed'}
        write_spec_pair(self.repo, self.path, altered)
        self.error('SPEC_APPROVAL_STALE', assert_repo_spec_approval, self.repo, receipt)
        md.unlink()
        self.error('SPEC_PAIR_MISSING', read_spec_pair, self.repo, self.path)
        write_spec_pair(self.repo, self.path, self.spec)
        (self.repo / self.path).unlink()
        self.error('SPEC_PAIR_MISSING', read_spec_pair, self.repo, self.path)

    def test_escape_and_ignored_files(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.repo / 'escape').symlink_to(outside, target_is_directory=True)
            self.error('SPEC_PATH_ESCAPE', write_spec_pair, self.repo, 'escape/spec.json', self.spec)
        self.error('SPEC_PATH_ESCAPE', write_spec_pair, self.repo, '../spec.json', self.spec)
        (self.repo / '.gitignore').write_text('docs/specs/\n')
        self.error('SPEC_PATH_IGNORED', write_spec_pair, self.repo, self.path, self.spec)
        self.assertFalse((self.repo / self.path).exists())

    def test_read_and_approval_reject_pair_symlinked_into_excluded_directory(self):
        for directory in ('.devflow', '.git'):
            with self.subTest(directory=directory):
                receipt = write_spec_pair(self.repo, self.path, self.spec)
                hidden = self.repo / directory / 'hidden-spec'
                hidden.mkdir(parents=True, exist_ok=True)
                for key in ('json_path', 'markdown_path'):
                    visible = self.repo / receipt[key]
                    target = hidden / visible.name
                    visible.replace(target)
                    visible.symlink_to(target)
                self.error('SPEC_PATH_ESCAPE', read_spec_pair, self.repo, self.path)
                self.error('SPEC_PATH_ESCAPE', assert_repo_spec_approval, self.repo, receipt)
                for key in ('json_path', 'markdown_path'):
                    (self.repo / receipt[key]).unlink()

    def test_resolved_ignored_target_and_ignored_markdown_companion(self):
        receipt = write_spec_pair(self.repo, self.path, self.spec)
        hidden = self.repo / 'private'
        hidden.mkdir()
        visible = self.repo / receipt['markdown_path']
        target = hidden / visible.name
        visible.replace(target)
        visible.symlink_to(target)
        (self.repo / '.gitignore').write_text('private/\n')
        self.error('SPEC_PATH_IGNORED', read_spec_pair, self.repo, self.path)
        self.error('SPEC_PATH_IGNORED', assert_repo_spec_approval, self.repo, receipt)
        visible.unlink()
        (self.repo / '.gitignore').write_text('docs/specs/*.md\n')
        self.error('SPEC_PATH_IGNORED', write_spec_pair, self.repo, self.path, self.spec)

    def test_absolute_and_excluded_paths_are_rejected(self):
        for path in (str(self.repo / 'absolute.json'), '.devflow/spec.json', '.git/spec.json'):
            with self.subTest(path=path):
                self.error('SPEC_PATH_ESCAPE', write_spec_pair, self.repo, path, self.spec)
