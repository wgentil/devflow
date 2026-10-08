import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.releases import release_descriptor, check_release

class ReleaseTests(unittest.TestCase):
    def test_relocation_preserves_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / 'package with spaces'
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns('.git', '.worktrees', '.superpowers', '__pycache__'))
            self.assertEqual(release_descriptor(ROOT), release_descriptor(copy))
            (copy / 'skills/workflow/scripts/__pycache__').mkdir(exist_ok=True)
            (copy / 'skills/workflow/scripts/__pycache__/x.pyc').write_bytes(b'cache')
            self.assertEqual(release_descriptor(ROOT), release_descriptor(copy))
    def test_same_version_content_change_blocks(self):
        source = release_descriptor(ROOT)
        target = {**source, 'fingerprint': 'changed'}
        self.assertEqual(check_release(source, target, 1)['status'], 'block')
    def test_unknown_loaded_release_blocks(self):
        self.assertEqual(check_release({}, release_descriptor(ROOT), 1)['status'], 'block')
    def test_unsupported_schema_blocks(self):
        release = release_descriptor(ROOT)
        self.assertEqual(check_release(release, release, 999)['status'], 'block')
    def test_distributions_resolve_shared_resources(self):
        for host in ('claude', 'codex'):
            manifest = json.loads((ROOT / f'.{host}-plugin/plugin.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['version'], release_descriptor(ROOT)['plugin_version'])
            self.assertTrue((ROOT / 'docs/setup-and-usage.md').is_file())
        self.assertEqual(release_descriptor(ROOT)['host_protocol_version'], 1)
