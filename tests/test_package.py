import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "skills/workflow/scripts/run.py"


class PackageTests(unittest.TestCase):
    def test_version_from_unrelated_cwd(self):
        result = subprocess.run(
            [sys.executable, str(ENTRY), "version"],
            cwd=Path("/tmp"), text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        descriptor = json.loads(result.stdout)
        self.assertEqual(descriptor['plugin'], 'devflow')
        self.assertEqual(descriptor['plugin_version'], '0.1.0')
        self.assertEqual(descriptor['state_schema_version'], 1)
        self.assertEqual(len(descriptor['fingerprint']), 64)

    def test_manifest_skills_resolve(self):
        manifest = json.loads((ROOT / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "devflow")
        for skill in manifest["skills"]:
            skill_file = (ROOT / skill / "SKILL.md").resolve()
            self.assertTrue(skill_file.is_relative_to(ROOT.resolve()))
            self.assertTrue(skill_file.is_file(), skill)

    def test_package_relocation_and_existing_journal(self):
        with tempfile.TemporaryDirectory() as temp_name:
            relocated = Path(temp_name) / "plugin"
            relocated.mkdir()
            shutil.copytree(ROOT / "skills", relocated / "skills")
            shutil.copy2(ROOT / "plugin.json", relocated / "plugin.json")
            manifest = json.loads((relocated / "plugin.json").read_text())
            self.assertEqual(len(manifest["skills"]), 10)
            for skill in manifest["skills"]:
                self.assertTrue((relocated / skill / "SKILL.md").is_file(), skill)
            control = Path(temp_name) / "control"
            layer = Path(temp_name) / "org.json"
            layer.write_text(json.dumps({"slices": {"architecture": {"status": "answered", "value": "ports"}}}))
            original = subprocess.run([sys.executable, str(ENTRY), "context", "set", "--root", str(control),
                "--layer", "org", "--file", str(layer)], cwd="/tmp", capture_output=True, text=True, check=False)
            self.assertEqual(original.returncode, 0, original.stderr + original.stdout)
            first_event = (control / "events/00000001.json").read_bytes()
            relocated_entry = relocated / "skills/workflow/scripts/run.py"
            result = subprocess.run([sys.executable, str(relocated_entry), "context", "resolve", "--root", str(control)],
                cwd="/tmp", capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((control / "events/00000001.json").read_bytes(), first_event)
            self.assertIn('"version":2', (control / "state.json").read_text())


if __name__ == "__main__":
    unittest.main()
