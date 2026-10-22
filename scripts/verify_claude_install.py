"""Verify an isolated Claude marketplace install and its packaged hooks."""
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.utf8_io import write_utf8

PLUGIN_ID = 'devflow@devflow-marketplace'


def find_installed_plugin(records, expected_version):
    matches = [record for record in records if record.get('id') == PLUGIN_ID]
    if len(matches) != 1:
        raise ValueError(f'expected one {PLUGIN_ID} install, found {len(matches)}')
    record = matches[0]
    if record.get('enabled') is not True or record.get('version') != expected_version:
        raise ValueError('installed DevFlow is disabled or has a different version')
    path = Path(record.get('installPath') or '').resolve()
    manifest = path / '.claude-plugin/plugin.json'
    hook = path / 'adapters/claude-code/hook.py'
    descriptor = path / 'adapters/claude-code/hooks.json'
    if not all(item.is_file() for item in (manifest, hook, descriptor)):
        raise ValueError('installed DevFlow is missing its manifest or hook files')
    if json.loads(manifest.read_text(encoding='utf-8')).get('version') != expected_version:
        raise ValueError('installed manifest version differs from the marketplace record')
    return path


def main(listing_file):
    expected = json.loads((ROOT / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))['version']
    installed = find_installed_plugin(json.loads(Path(listing_file).read_text(encoding='utf-8-sig')), expected)
    environment = dict(os.environ, DEVFLOW_HOOK_PATH=str(installed / 'adapters/claude-code/hook.py'))
    write_utf8(f'Installed {PLUGIN_ID} {expected}: {installed}\n')
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                             '-p', 'test_claude_hooks.py', '-v'], cwd=ROOT, env=environment,
                            check=False, timeout=120)
    return result.returncode


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: verify_claude_install.py PLUGIN_LIST_JSON')
    raise SystemExit(main(sys.argv[1]))
