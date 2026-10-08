import subprocess
import os
import tempfile
import unittest
from pathlib import Path

from skills.workflow.scripts.workflow_lib.git_paths import git_paths, resolve_repo_path


class GitPathsTests(unittest.TestCase):
    def test_nul_output_preserves_newline_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            names = ['space name.txt', 'café.txt']
            if os.name != 'nt':
                names.append('line\nbreak.txt')
            for name in names:
                (repo / name).write_text('content')
            self.assertEqual(set(git_paths(repo, 'ls-files', '--others', '--exclude-standard')), set(names))

    def test_resolve_rejects_drive_relative_and_parent_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            with self.assertRaises(ValueError): resolve_repo_path(repo, '../escape')
            with self.assertRaises(ValueError): resolve_repo_path(repo, 'C:escape')
            self.assertEqual(resolve_repo_path(repo, 'some file.txt'), (repo / 'some file.txt').resolve())

    @unittest.skipIf(os.name == 'nt', 'newline is not a valid Windows filename')
    def test_diff_paths_preserve_newline(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            path = repo / 'line\nbreak.txt'
            path.write_text('before', encoding='utf-8')
            subprocess.run(['git', 'add', '.'], cwd=repo, check=True)
            subprocess.run(['git', '-c', 'user.name=DevFlow', '-c', 'user.email=devflow@example.invalid',
                            'commit', '-qm', 'base'], cwd=repo, check=True)
            path.write_text('after', encoding='utf-8')
            self.assertEqual(git_paths(repo, 'diff', '--name-only', 'HEAD'), ['line\nbreak.txt'])
