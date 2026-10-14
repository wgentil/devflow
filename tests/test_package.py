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
    def test_claude_marketplace_packages_shared_root(self):
        marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
        claude = json.loads((ROOT / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))
        codex = json.loads((ROOT / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
        self.assertEqual(marketplace['name'], 'devflow-marketplace')
        self.assertEqual(len(marketplace['plugins']), 1)
        self.assertEqual(marketplace['plugins'][0]['name'], 'devflow')
        self.assertEqual(marketplace['plugins'][0]['source'], '.')
        self.assertEqual(claude['name'], codex['name'])
        self.assertEqual(claude['version'], codex['version'])
        self.assertTrue((ROOT / claude['hooks']).is_file())

    def test_version_from_unrelated_cwd(self):
        result = subprocess.run(
            [sys.executable, str(ENTRY), "version"],
            cwd=Path(tempfile.gettempdir()), text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        descriptor = json.loads(result.stdout)
        self.assertEqual(descriptor['plugin'], 'devflow')
        self.assertEqual(descriptor['plugin_version'], '0.3.7')
        self.assertEqual(descriptor['state_schema_version'], 1)
        self.assertEqual(len(descriptor['fingerprint']), 64)

    def test_manifest_skills_resolve(self):
        manifest = json.loads((ROOT / "plugin.json").read_text(encoding='utf-8'))
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
            manifest = json.loads((relocated / "plugin.json").read_text(encoding='utf-8'))
            self.assertEqual(len(manifest["skills"]), 11)
            for skill in manifest["skills"]:
                self.assertTrue((relocated / skill / "SKILL.md").is_file(), skill)
            control = Path(temp_name) / "control"
            layer = Path(temp_name) / "org.json"
            layer.write_text(json.dumps({"slices": {"architecture": {"status": "answered", "value": "ports"}}}))
            original = subprocess.run([sys.executable, str(ENTRY), "context", "set", "--root", str(control),
                "--layer", "org", "--file", str(layer)], cwd=tempfile.gettempdir(), capture_output=True, text=True, check=False)
            self.assertEqual(original.returncode, 0, original.stderr + original.stdout)
            first_event = (control / "events/00000001.json").read_bytes()
            relocated_entry = relocated / "skills/workflow/scripts/run.py"
            result = subprocess.run([sys.executable, str(relocated_entry), "context", "resolve", "--root", str(control)],
                cwd=tempfile.gettempdir(), capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((control / "events/00000001.json").read_bytes(), first_event)
            self.assertIn('"version":2', (control / "state.json").read_text(encoding='utf-8'))


if __name__ == "__main__":
    unittest.main()

class HostResourceTests(unittest.TestCase):
    def test_shared_guides_and_host_resources_resolve(self):
        import re
        files=list((ROOT/'skills').glob('*/SKILL.md'))+list((ROOT/'skills').glob('*/GUIDE.md'))+[ROOT/'docs/setup-and-usage.md',ROOT/'docs/hosts.md',ROOT/'docs/skills.md']
        for file in files:
            for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',file.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):continue
                path=(file.parent/target.split('#')[0]).resolve()
                self.assertTrue(path.exists(),f'{file.relative_to(ROOT)}: {target}')
        hooks=json.loads((ROOT/'adapters/claude-code/hooks.json').read_text(encoding='utf-8'))['hooks']
        self.assertEqual(set(hooks),{'SessionStart','UserPromptSubmit','TaskCompleted','Stop'})
        self.assertEqual(json.loads((ROOT/'.codex-plugin/plugin.json').read_text(encoding='utf-8'))['skills'],'./skills/')
    def test_host_examples_cover_attachment_mapping_and_handoff(self):
        attach=json.loads((ROOT/'docs/examples/host-attach.json').read_text(encoding='utf-8'))
        task=json.loads((ROOT/'docs/examples/host-task.json').read_text(encoding='utf-8'))
        handoff=json.loads((ROOT/'docs/examples/host-handoff.json').read_text(encoding='utf-8'))
        self.assertEqual(attach['role'],'implementer')
        self.assertEqual(task['binding_id'],attach['binding_id'])
        self.assertEqual(handoff['binding_id'],attach['binding_id'])
        self.assertEqual(task['scope'],'item')

class PortableHookTests(unittest.TestCase):
    def test_claude_hooks_use_shell_free_python_launcher(self):
        hooks=json.loads((ROOT/'adapters/claude-code/hooks.json').read_text(encoding='utf-8'))['hooks']
        for event in ('SessionStart','UserPromptSubmit','TaskCompleted','Stop'):
            handler=hooks[event][0]['hooks'][0]
            self.assertEqual(handler['command'],'python3')
            self.assertEqual(handler['args'],['-B','${CLAUDE_PLUGIN_ROOT}/adapters/claude-code/hook.py'])
