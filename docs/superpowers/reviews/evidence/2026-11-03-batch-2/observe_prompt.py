#!/usr/bin/env python3
"""Read-only fresh-session observation; never attach or evaluate mapped work."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib import host_hook, store
from workflow_lib.host_locators import locator_path


def inventory(directory):
    result = {}
    if not directory.exists():
        return result
    for parent, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not (Path(parent) / name).is_symlink())
        for name in sorted(files):
            path = Path(parent) / name
            if path.is_symlink():
                result[str(path.relative_to(directory))] = {'symlink': os.readlink(path)}
                continue
            checksum = hashlib.sha256()
            try:
                with path.open('rb') as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                        checksum.update(chunk)
                stat = path.stat()
                result[str(path.relative_to(directory))] = {
                    'sha256': checksum.hexdigest(), 'size': stat.st_size,
                    'mtime_ns': stat.st_mtime_ns,
                }
            except FileNotFoundError:
                result[str(path.relative_to(directory))] = {'unavailable': 'disappeared during inventory'}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    project = args.project.resolve()
    discovered = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=project,
                                capture_output=True, text=True, check=True).stdout.strip()
    if Path(discovered).resolve() != project:
        raise RuntimeError('Select an exact Git project root.')
    metadata = project / '.devflow'
    control = metadata / 'control'
    if not control.is_dir():
        raise RuntimeError('Existing project control root required; no initialization is permitted.')
    if args.output.resolve().is_relative_to(project):
        raise RuntimeError('Evidence must be written outside the observed project.')
    session = 'autowork-batch2-read-only-' + uuid.uuid4().hex
    locator = locator_path(project, 'claude', session)
    hints = [locator, locator.with_suffix('.tasks.json'), locator.with_suffix('.brief.json')]
    if any(path.exists() for path in hints):
        raise RuntimeError('Fresh session unexpectedly has discovery hints.')
    before = inventory(metadata)
    counts = {'journal': 0, 'state': 0}
    original_open = Path.open

    def deny_journal(*unused, **kwargs):
        counts['journal'] += 1
        raise AssertionError('Undiscoverable optional refresh attempted a journal read.')

    def deny_state(*unused, **kwargs):
        counts['state'] += 1
        raise AssertionError('Undiscoverable optional refresh attempted a state read.')

    def guarded_open(path, mode='r', *positional, **kwargs):
        resolved = path.resolve()
        if resolved.is_relative_to(metadata) and any(flag in mode for flag in 'wax+'):
            raise AssertionError('Fresh-session observation attempted to write project metadata.')
        if resolved.is_relative_to(control):
            raise AssertionError('Undiscoverable optional refresh attempted to open control storage.')
        return original_open(path, mode, *positional, **kwargs)

    with patch.object(store, '_read_journal', side_effect=deny_journal), \
            patch.object(store, 'read_state', side_effect=deny_state), \
            patch.object(Path, 'open', guarded_open):
        started = time.perf_counter()
        decision = host_hook.evaluate(project, session, 'UserPromptSubmit')
        direct_seconds = time.perf_counter() - started

    def invoke(argv, payload=None):
        started = time.perf_counter()
        child = subprocess.run(argv, input=payload, capture_output=True,
                               text=True, encoding='utf-8', timeout=12)
        return {'exit': child.returncode, 'elapsed_seconds': time.perf_counter() - started,
                'stdout': child.stdout, 'stderr': child.stderr}

    cli = invoke([sys.executable, '-B', str(ROOT / 'skills/workflow/scripts/run.py'),
                  'host', 'hook-evaluate', '--project-dir', str(project),
                  '--session-id', session, '--event', 'UserPromptSubmit'])
    adapter = invoke([sys.executable, '-B', str(ROOT / 'adapters/claude-code/hook.py')],
                     json.dumps({'cwd': str(project), 'session_id': session,
                                 'hook_event_name': 'UserPromptSubmit'}))
    after = inventory(metadata)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    source = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    passed = (decision['status'] == 'inactive' and decision['reason_code'] == 'ATTACHMENT_NOT_DISCOVERED'
              and json.loads(cli['stdout']) == decision and cli['exit'] == 0
              and adapter['exit'] == 0 and adapter['stdout'] == ''
              and counts == {'journal': 0, 'state': 0}
              and not any(path.exists() for path in hints) and not changed)
    report = {
        'success': passed, 'source_sha': source, 'project': str(project), 'session_id': session,
        'environment': {'platform': platform.platform(), 'python': platform.python_version()},
        'state_bytes': (control / 'state.json').stat().st_size,
        'events': len(list((control / 'events').glob('*.json'))),
        'metadata_files_before': len(before), 'metadata_files_after': len(after),
        'metadata_bytes_before': sum(row.get('size', 0) for row in before.values()),
        'metadata_manifest_sha256_before': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
        'metadata_manifest_sha256_after': hashlib.sha256(json.dumps(after, sort_keys=True).encode()).hexdigest(),
        'metadata_unchanged': not changed, 'changed_metadata_paths': changed,
        'session_hints_absent_after': not any(path.exists() for path in hints),
        'direct': {'result': decision, 'elapsed_seconds': direct_seconds, 'storage_read_calls': counts},
        'cli': cli, 'adapter': adapter,
        'limitations': ['Fresh undiscoverable session only; no attached production refresh or run next.',
                        'Storage-read instrumentation and write guards apply to the direct Python call only.',
                        'CLI and adapter are real subprocesses; before/after content and mtime inventories cover all project .devflow metadata.',
                        'An active external workflow can change inventories; such a change makes this observation unsuccessful and requires investigation.',
                        'No signed-in host dispatch, load guarantee, model turn or native Windows observation.'],
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'success': passed, 'state_bytes': report['state_bytes'],
                      'direct_seconds': direct_seconds, 'cli_seconds': cli['elapsed_seconds'],
                      'adapter_seconds': adapter['elapsed_seconds'], 'changed_metadata_paths': changed}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
