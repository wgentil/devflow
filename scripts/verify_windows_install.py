#!/usr/bin/env python3
"""Check isolated installed packages and real startup; never submit model work."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.releases import release_descriptor
from workflow_lib.native_models import RPC, run_bounded
from workflow_lib.utf8_io import write_utf8
from verify_claude_install import find_installed_plugin

PLUGIN_ID = 'devflow@devflow-marketplace'


def verify_package(package: Path, expected: dict) -> dict:
    if release_descriptor(package) != expected:
        raise ValueError('installed package fingerprint differs from the candidate checkout')
    manifest = json.loads((package / 'plugin.json').read_text(encoding='utf-8'))
    skills = manifest['skills']
    if len(skills) != 11 or len(set(skills)) != 11:
        raise ValueError('installed package must contain exactly eleven distinct skills')
    for skill in skills:
        path = (package / skill / 'SKILL.md').resolve()
        if not path.is_relative_to(package.resolve()) or not path.is_file():
            raise ValueError('installed skill is missing or escapes the package')
    return {'status': 'PASS', 'skill_count': len(skills), 'descriptor': expected}


def find_codex_plugin(records: dict, expected: dict, cache: Path) -> Path:
    installed = records.get('installed') if isinstance(records, dict) else None
    if not isinstance(installed, list):
        raise ValueError('Codex listing needs installed entries, not an available marketplace listing')
    matches = [row for row in installed if isinstance(row, dict) and row.get('pluginId') == PLUGIN_ID]
    if len(matches) != 1 or matches[0].get('installed') is not True or matches[0].get('enabled') is not True or matches[0].get('version') != expected['plugin_version']:
        raise ValueError('expected one enabled installed Codex candidate release')
    packages = []
    for path in (cache / 'devflow-marketplace/devflow').glob('*'):
        if not path.is_dir():
            continue
        try:
            verify_package(path, expected)
            packages.append(path.resolve())
        except (OSError, ValueError, KeyError, TypeError):
            continue
    if len(packages) != 1:
        raise ValueError('expected exactly one matching installed Codex package fingerprint')
    return packages[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-root', 'codex-list', 'codex-cache', 'claude-list', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    expected = release_descriptor(args.source_root)
    report = {'schema_version': 1, 'git_sha': os.environ.get('GITHUB_SHA'), 'descriptor': expected, 'gates': {},
              'authenticated_workflow': {'status': 'NOT_RUN', 'reason': 'Startup checks do not execute signed-in model tasks or live session events.'}}
    gates = report['gates']
    try:
        codex = find_codex_plugin(json.loads(args.codex_list.read_text(encoding='utf-8-sig')), expected, args.codex_cache)
        claude = find_installed_plugin(json.loads(args.claude_list.read_text(encoding='utf-8-sig')), expected['plugin_version'])
        gates['codex_install'] = verify_package(codex, expected)
        gates['claude_install'] = verify_package(claude, expected)
        for host in ('codex', 'claude'):
            result = run_bounded([host, '--version'], args.source_root, 15)
            if result.returncode:
                raise ValueError(host + ' installed executable startup failed')
            version = re.search(r'\d+\.\d+\.\d+', result.stdout)
            if not version:
                raise ValueError(host + ' version is unavailable')
            if host == 'claude' and tuple(map(int, version.group().split('.'))) < (2, 1, 295):
                raise ValueError('Claude 2.1.295+ is required for mandatory launcher failure policy')
            gates[host + '_startup'] = {'status': 'PASS', 'version': version.group()}
        rpc = RPC(args.source_root)
        try:
            status = rpc.request('account/read', {'refreshToken': False})
            if not isinstance(status, dict):
                raise ValueError('Codex account-status RPC returned an invalid response')
        finally:
            rpc.close()
        gates['codex_protocol'] = {'status': 'PASS', 'detail': 'initialize/account-status completed; no model turn submitted'}
        descriptor = json.loads((claude / 'adapters/claude-code/hooks.json').read_text(encoding='utf-8'))
        command = descriptor['hooks']['TaskCompleted'][0]['hooks'][0]['command']
        if not shutil.which(command):
            raise ValueError('required hook Python executable is unavailable: ' + command)
        check = subprocess.run([command, '-c', 'import sys;sys.exit(sys.version_info < (3,11))'], capture_output=True, timeout=10)
        if check.returncode:
            raise ValueError('required hook Python executable is older than 3.11')
        environment = {**os.environ, 'DEVFLOW_HOOK_PATH': str(claude / 'adapters/claude-code/hook.py')}
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_claude_hooks.py', '-v'],
            cwd=args.source_root, env=environment, capture_output=True, timeout=120)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.with_suffix('.hooks.log').write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise ValueError('installed hook-script suite failed; inspect hook log')
        gates['claude_hook_scripts'] = {'status': 'PASS', 'python_command': command, 'live_event_dispatch': 'NOT_RUN'}
        report['success'] = True
    except Exception as exc:
        report['success'] = False
        gates['failure'] = {'status': 'FAIL', 'reason': str(exc)[:1000]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_utf8(json.dumps(report, ensure_ascii=False) + '\n')
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
