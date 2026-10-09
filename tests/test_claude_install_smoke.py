import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_claude_install import find_installed_plugin


class ClaudeInstallSmokeTests(unittest.TestCase):
    def test_requires_enabled_exact_version_and_installed_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'adapters/claude-code').mkdir(parents=True)
            (root / 'adapters/claude-code/hook.py').write_text('pass', encoding='utf-8')
            (root / 'adapters/claude-code/hooks.json').write_text('{}', encoding='utf-8')
            (root / '.claude-plugin').mkdir()
            (root / '.claude-plugin/plugin.json').write_text(json.dumps({'version': '0.3.2'}), encoding='utf-8')
            record = {'id': 'devflow@devflow-marketplace', 'version': '0.3.2',
                      'scope': 'local', 'enabled': True, 'installPath': str(root)}
            self.assertEqual(find_installed_plugin([record], '0.3.2'), root.resolve())
            with self.assertRaises(ValueError):
                find_installed_plugin([{**record, 'enabled': False}], '0.3.2')
            with self.assertRaises(ValueError):
                find_installed_plugin([{**record, 'version': '0.3.1'}], '0.3.2')
