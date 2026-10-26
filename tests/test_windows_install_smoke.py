"""Installed identities must come from installed entries and exact package bytes."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.releases import release_descriptor


class WindowsInstallSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / 'cache'
        self.copy = self.cache / 'devflow-marketplace/devflow/candidate'
        self.copy.mkdir(parents=True)
        for name in ('skills', 'adapters', 'definitions', '.claude-plugin', '.codex-plugin'):
            shutil.copytree(ROOT / name, self.copy / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(ROOT / 'plugin.json', self.copy / 'plugin.json')
        self.expected = release_descriptor(ROOT)
        self.record = {'pluginId': 'devflow@devflow-marketplace', 'name': 'devflow', 'marketplaceName': 'devflow-marketplace',
            'version': self.expected['plugin_version'], 'installed': True, 'enabled': True}

    def verifier(self):
        self.assertIsNotNone(importlib.util.find_spec('verify_windows_install'), 'installed Windows package verifier is required')
        import verify_windows_install
        return verify_windows_install

    def test_actual_installed_record_requires_exact_package_and_inventory(self):
        verifier = self.verifier()
        found = verifier.find_codex_plugin({'installed': [self.record], 'available': []}, self.expected, self.cache)
        self.assertEqual(found, self.copy.resolve())
        self.assertEqual(verifier.verify_package(found, self.expected)['skill_count'], 11)

    def test_installed_helper_exercises_both_control_formats(self):
        verifier=self.verifier();self.assertTrue(hasattr(verifier,'verify_control_formats'),'installed control-format probe is missing')
        report=verifier.verify_control_formats(self.copy)
        self.assertEqual(report['status'],'PASS');self.assertEqual(report['storage_formats'],[1,2]);self.assertEqual(report['logical_schema'],1)

    def test_disabled_available_only_and_wrong_fingerprint_are_rejected(self):
        verifier = self.verifier()
        for listing in ({'installed': [], 'available': [self.record]},
                        {'installed': [{**self.record, 'enabled': False}]},
                        {'installed': [{**self.record, 'installed': False}]}):
            with self.subTest(listing=listing), self.assertRaises(ValueError):
                verifier.find_codex_plugin(listing, self.expected, self.cache)
        (self.copy / 'adapters/claude-code/hook.py').write_bytes(b'wrong package bytes')
        with self.assertRaises(ValueError):
            verifier.find_codex_plugin({'installed': [self.record]}, self.expected, self.cache)

    def test_ambiguous_matching_copies_are_rejected(self):
        verifier = self.verifier()
        shutil.copytree(self.copy, self.copy.parent / 'duplicate')
        with self.assertRaises(ValueError):
            verifier.find_codex_plugin({'installed': [self.record]}, self.expected, self.cache)
