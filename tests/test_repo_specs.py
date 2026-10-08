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
            self.assertEqual((self.repo / receipt['markdown_path']).read_text(), render_spec(self.spec))
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
