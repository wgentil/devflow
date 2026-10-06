import json
import subprocess
import sys
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
        self.assertEqual(json.loads(result.stdout), {
            "plugin": "devflow", "plugin_version": "0.1.0", "state_schema_version": 1,
        })

    def test_manifest_skills_resolve(self):
        manifest = json.loads((ROOT / "plugin.json").read_text())
        self.assertEqual(manifest["name"], "devflow")
        for skill in manifest["skills"]:
            skill_file = (ROOT / skill / "SKILL.md").resolve()
            self.assertTrue(skill_file.is_relative_to(ROOT.resolve()))
            self.assertTrue(skill_file.is_file(), skill)


if __name__ == "__main__":
    unittest.main()
