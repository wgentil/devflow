import subprocess
import tempfile
import unittest
from pathlib import Path

from skills.workflow.scripts.workflow_lib.git_paths import git_paths, resolve_repo_path


class GitPathsTests(unittest.TestCase):
    def test_nul_output_preserves_newline_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            for name in ['space name.txt', 'line\nbreak.txt', 'café.txt']:
                (repo / name).write_text('content')
            self.assertEqual(set(git_paths(repo, 'ls-files', '--others', '--exclude-standard')),
                             {'space name.txt', 'line\nbreak.txt', 'café.txt'})

    def test_resolve_rejects_drive_relative_and_parent_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            with self.assertRaises(ValueError): resolve_repo_path(repo, '../escape')
            with self.assertRaises(ValueError): resolve_repo_path(repo, 'C:escape')
            self.assertEqual(resolve_repo_path(repo, 'some file.txt'), (repo / 'some file.txt').resolve())
