"""Verify an isolated Claude marketplace install and its packaged hooks."""
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
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


def main():
    expected = json.loads((ROOT / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))['version']
    listing = subprocess.run(['claude', 'plugin', 'list', '--json'], capture_output=True,
                             text=True, check=True, timeout=30)
    installed = find_installed_plugin(json.loads(listing.stdout), expected)
    environment = dict(os.environ, DEVFLOW_HOOK_PATH=str(installed / 'adapters/claude-code/hook.py'))
    print(f'Installed {PLUGIN_ID} {expected}: {installed}', flush=True)
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests',
                             '-p', 'test_claude_hooks.py', '-v'], cwd=ROOT, env=environment,
                            check=False, timeout=120)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
