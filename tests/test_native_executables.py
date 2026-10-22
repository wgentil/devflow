"""Resolve controlled npm layouts; launch actual Node with literal argv."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))


class NativeExecutableTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='devflow host é東京 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix = self.root / 'prefix'
        self.prefix.mkdir()

    def resolver(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.native_executables'), 'safe Windows executable resolution is required')
        from workflow_lib.native_executables import resolve_native_argv
        return resolve_native_argv

    def npm(self, host='codex', local=False):
        package_name = '@openai/codex' if host == 'codex' else '@anthropic-ai/claude-code'
        package = self.prefix / 'node_modules' / package_name
        package.mkdir(parents=True)
        entry = package / 'cli.js'
        entry.write_text('console.log(JSON.stringify(process.argv.slice(2)));', encoding='utf-8')
        (package / 'package.json').write_text(json.dumps({'name': package_name, 'bin': {host: 'cli.js'}}), encoding='utf-8')
        shim = (self.prefix / 'node_modules/.bin' if local else self.prefix) / (host + '.cmd')
        shim.parent.mkdir(parents=True, exist_ok=True)
        shim.write_text('@echo UNSAFE_SHIM_MUST_NOT_EXECUTE\n', encoding='utf-8')
        return shim, package, entry

    def test_native_exe_and_npm_bin_resolution(self):
        resolve = self.resolver()
        executable = self.prefix / 'codex.exe'
        executable.write_bytes(b'fixture native executable')
        self.assertEqual(resolve([str(executable), '--version'], platform_name='nt'), [str(executable.resolve()), '--version'])
        for host, local in [('codex', False), ('claude', True)]:
            with self.subTest(host=host):
                shim, package, entry = self.npm(host, local)
                with patch('workflow_lib.native_executables.shutil.which', return_value=str(self.prefix / 'node.exe')):
                    (self.prefix / 'node.exe').write_bytes(b'fixture node executable')
                    result = resolve([str(shim), '--version'], platform_name='nt')
                self.assertEqual(result, [str((self.prefix / 'node.exe').resolve()), str(entry.resolve()), '--version'])

    def test_missing_or_escaping_npm_target_is_unavailable(self):
        resolve = self.resolver()
        shim, package, entry = self.npm()
        entry.unlink()
        with self.assertRaises(OSError):
            resolve([str(shim)], platform_name='nt')
        outside = self.root / 'outside.js'
        outside.write_bytes(b'outside')
        (package / 'package.json').write_text(json.dumps({'name': '@openai/codex', 'bin': {'codex': '../../../../outside.js'}}), encoding='utf-8')
        node = self.prefix / 'node.exe'
        node.write_bytes(b'fixture native executable')
        with patch('workflow_lib.native_executables.shutil.which', return_value=str(node)), self.assertRaises(OSError):
            resolve([str(shim)], platform_name='nt')
        shim.unlink()
        with self.assertRaises(OSError):
            resolve([str(shim)], platform_name='nt')

    def test_windows_prompt_metacharacters_are_literal_argv(self):
        resolve = self.resolver()
        node = shutil.which('node')
        if node is None:
            self.skipTest('optional Node executable required for actual npm JavaScript launch; CI installs Node')
        shim, package, entry = self.npm()
        node_exe = self.prefix / 'node.exe'
        if os.name == 'nt':
            shutil.copy2(node, node_exe)
        else:
            node_exe.symlink_to(node)
        arguments = ['é東京 with spaces', 'quote"inside', '& touch SHOULD_NOT_EXIST', '%PATH%', '$(touch SHOULD_NOT_EXIST)']
        with patch('workflow_lib.native_executables.shutil.which', return_value=str(node_exe)):
            argv = resolve([str(shim), *arguments], platform_name='nt')
        result = subprocess.run(argv, cwd=self.root, capture_output=True, check=True, timeout=10)
        self.assertEqual(json.loads(result.stdout), arguments)
        self.assertFalse((self.root / 'SHOULD_NOT_EXIST').exists())

    def test_explicit_custom_rpc_argv_and_unix_are_preserved(self):
        resolve = self.resolver()
        custom = [sys.executable, '-c', 'print("custom")']
        self.assertEqual(resolve(custom, platform_name='nt'), custom)
        self.assertEqual(resolve(['codex', 'app-server'], platform_name='posix'), ['codex', 'app-server'])
