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
        self.assertEqual(descriptor['plugin_version'], '0.3.13')
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

class CrossPlatformPackageIdentityTests(unittest.TestCase):
    def test_release_identity_survives_git_checkout_with_autocrlf(self):
        sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
        from workflow_lib.releases import release_descriptor
        with tempfile.TemporaryDirectory(prefix='devflow-package-identity-') as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            for name in ('skills', 'adapters', 'definitions', '.claude-plugin', '.codex-plugin'):
                shutil.copytree(ROOT / name, source / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            shutil.copy2(ROOT / 'plugin.json', source / 'plugin.json')
            if (ROOT / '.gitattributes').exists():
                shutil.copy2(ROOT / '.gitattributes', source / '.gitattributes')
            # Auto text policy must preserve binary package assets byte-for-byte.
            binary = b'\x00asset\r\n\xff\x00'
            (source / 'adapters/binary-fixture.bin').write_bytes(binary)
            for argv in (['init', '-q'], ['config', 'core.autocrlf', 'false'], ['add', '.'],
                         ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'package']):
                subprocess.run(['git', *argv], cwd=source, check=True, capture_output=True)
            clone = root / 'windows-checkout'
            subprocess.run(['git', '-c', 'core.autocrlf=true', 'clone', '--no-local', '-q', str(source), str(clone)], check=True, capture_output=True)
            self.assertEqual(release_descriptor(clone), release_descriptor(source))
            self.assertEqual((clone / 'adapters/binary-fixture.bin').read_bytes(), binary)

    def test_routed_reference_bytes_survive_git_checkout_with_autocrlf(self):
        sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
        from workflow_lib.documentation import load_documentation_policy
        from workflow_lib.document_units import select_document_units
        policy = load_documentation_policy(ROOT)
        references = {sid: row for sid, row in policy['sources'].items() if row['path'].startswith('docs/reference/')}
        with tempfile.TemporaryDirectory(prefix='devflow-reference-identity-') as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            for row in references.values():
                target = source / row['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / row['path']).read_bytes().replace(b'\r\n', b'\n'))
            shutil.copy2(ROOT / '.gitattributes', source / '.gitattributes')
            binary = b'\x00reference\r\n\xff\x00'
            (source / 'docs/reference/binary-fixture.bin').write_bytes(binary)
            for argv in (['init', '-q'], ['config', 'core.autocrlf', 'false'], ['add', '.'],
                         ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'references']):
                subprocess.run(['git', *argv], cwd=source, check=True, capture_output=True)
            clone = root / 'windows-checkout'
            subprocess.run(['git', '-c', 'core.autocrlf=true', 'clone', '--no-local', '-q', str(source), str(clone)], check=True, capture_output=True)
            def observed(base):
                sources = {sid: {'root': str(base), 'path': row['path']} for sid, row in references.items()}
                selected = select_document_units(sources, [{'source_id': sid} for sid in sources], policy)
                return {u['id']: (u['content_hash'], len(u['content'].encode('utf-8'))) for u in selected['units']}
            self.assertEqual(observed(clone), observed(source))
            self.assertEqual((clone / 'docs/reference/binary-fixture.bin').read_bytes(), binary)
