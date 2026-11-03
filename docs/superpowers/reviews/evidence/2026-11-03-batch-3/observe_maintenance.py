#!/usr/bin/env python3
"""Exercise public maintenance only on owned generated roots; no live-root input."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib import store
from workflow_lib.storage_backups import verify_backup
from workflow_lib.storage_format import detect_layout
from workflow_lib.storage_journal import read_raw_event
from workflow_lib.storage_objects import put_object
from workflow_lib.stored_records import digest

TELEMETRY = {'offload.jsonl', '.offload.lock', 'context-metrics.jsonl', '.context-metrics.lock'}


def files(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix() not in TELEMETRY}


def run(output, transcript):
    spec = importlib.util.spec_from_file_location('batch3_storage_fixture', ROOT / 'scripts/benchmark_control_storage.py')
    benchmark = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmark)
    calls = []
    owned = []
    with tempfile.TemporaryDirectory(prefix='autowork-batch3-maintenance-') as temporary:
        base = Path(temporary).resolve()
        fixture = benchmark._fixture(base / 'fixture', 40, 8 * 1024 * 1024)
        root = fixture['root']
        owned.append(root)
        original = store.read_state(root)
        original_hash = digest(original)
        original_event = next(iter(original['operations'].values()))
        raw = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'events').glob('*.json')}
        original_file_bytes = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())

        def cli(action, *args, selected_root=root):
            if not selected_root.resolve().is_relative_to(base):
                raise AssertionError('Maintenance root escaped the owned temporary directory.')
            argv = [sys.executable, '-B', str(ROOT / 'skills/workflow/scripts/run.py'),
                    'state', action, '--root', str(selected_root), *map(str, args)]
            started = time.perf_counter()
            child = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                                   encoding='utf-8', timeout=180)
            row = {'argv': argv, 'exit': child.returncode,
                   'elapsed_ms': (time.perf_counter() - started) * 1000,
                   'stdout': child.stdout, 'stderr': child.stderr}
            calls.append(row)
            transcript.write_text(json.dumps(calls, indent=2) + '\n', encoding='utf-8')
            if child.returncode:
                raise RuntimeError('Owned maintenance command failed: ' + child.stdout + child.stderr)
            return json.loads(child.stdout)

        assert detect_layout(root)['layout'] == 'legacy'
        before = files(root)
        first_plan = cli('compact', '--dry-run', '--details')
        assert not first_plan['blockers'] and files(root) == before
        legacy_backup = base / 'legacy backup é東京'
        owned.append(legacy_backup)
        legacy_receipt = cli('backup', '--output', legacy_backup,
                             '--operation-id', 'batch3-legacy-backup', '--actor-id', 'synthetic-fixture-owner')
        legacy_valid = verify_backup(legacy_backup)
        assert legacy_receipt['completed'] and legacy_valid['valid']
        assert digest(store.read_state(legacy_backup)) == original_hash
        assert cli('verify', '--full', selected_root=legacy_backup)['valid']

        plan = cli('compact', '--dry-run', '--details')
        assert not plan['blockers']
        apply_args = ['--apply', '--plan-hash', plan['plan_hash'],
                      '--operation-id', 'batch3-convert', '--actor-id', 'synthetic-fixture-owner']
        converted = cli('compact', *apply_args)
        converted_retry = cli('compact', *apply_args)
        assert converted['completed'] and converted_retry['replayed']
        assert {k: v for k, v in converted.items() if k != 'replayed'} == {
            k: v for k, v in converted_retry.items() if k != 'replayed'}
        assert detect_layout(root)['layout'] == 'v2'
        assert digest(store.read_state(root)) == original_hash
        assert store.read_state(root)['data']['runs']['current']['status'] == 'active'
        raw_preserved = True
        for name, checksum in raw.items():
            recovered = read_raw_event(root, int(Path(name).stem))
            raw_preserved &= recovered['name'] == name and hashlib.sha256(recovered['bytes']).hexdigest() == checksum
        assert raw_preserved
        retry = store.transact(root, -1, original_event['operation_id'],
                               {'kind': original_event['kind'], 'payload': original_event['payload']})
        assert retry['replayed'] and retry['event'] == original_event
        migrated_audit = cli('verify', '--full')
        assert migrated_audit['valid']

        v2_backup = base / 'v2 backup é東京'
        owned.append(v2_backup)
        v2_receipt = cli('backup', '--output', v2_backup,
                         '--operation-id', 'batch3-v2-backup', '--actor-id', 'synthetic-fixture-owner')
        v2_valid = verify_backup(v2_backup)
        assert v2_receipt['completed'] and v2_valid['valid']
        assert digest(store.read_state(v2_backup)) == original_hash
        assert cli('verify', '--full', selected_root=v2_backup)['valid']

        orphan = put_object(root, 'source-field', b'Owned unreachable evidence\n' * 2048)
        unknown = root / 'operator-notes.bin'
        unknown.write_bytes(b'Owned unknown provenance; preserve this content.\n')
        unknown_hash = hashlib.sha256(unknown.read_bytes()).hexdigest()
        before_gc = files(root)
        gc_plan = cli('gc', '--dry-run', '--details')
        assert files(root) == before_gc and not gc_plan['blockers']
        assert any(row.get('object_id') == orphan['object_id'] for row in gc_plan['candidates'])
        assert unknown.name in gc_plan['retained_unknown']
        gc_args = ['--apply', '--plan-hash', gc_plan['plan_hash'],
                   '--operation-id', 'batch3-gc', '--actor-id', 'synthetic-fixture-owner']
        collected = cli('gc', *gc_args)
        collected_retry = cli('gc', *gc_args)
        assert collected['completed'] and not collected['deferred'] and collected['reclaimed_bytes'] > 0
        assert collected_retry['replayed']
        assert {k: v for k, v in collected.items() if k != 'replayed'} == {
            k: v for k, v in collected_retry.items() if k != 'replayed'}
        assert all(not (root / row['path']).exists() for row in gc_plan['candidates'])
        assert collected['reclaimed_bytes'] == gc_plan['candidate_bytes']
        assert hashlib.sha256(unknown.read_bytes()).hexdigest() == unknown_hash
        final_hash = digest(store.read_state(root))
        final_audit = cli('verify', '--full')
        assert final_hash == original_hash and final_audit['valid']
        physical = benchmark._physical(root)
        source = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                check=True, capture_output=True, text=True).stdout.strip()
        result = {
            'success': True, 'source_sha': source,
            'environment': {'platform': platform.platform(), 'python': platform.python_version()},
            'fixture': {'terminal_runs': 40, 'review_body_bytes': 8 * 1024 * 1024,
                        'legacy_events': len(raw), 'legacy_logical_version': original['version'],
                        'legacy_file_bytes': original_file_bytes, 'synthetic': True},
            'original_logical_sha256': original_hash, 'final_logical_sha256': final_hash,
            'dry_run_content_unchanged': True, 'telemetry_exclusions': sorted(TELEMETRY),
            'legacy_backup': legacy_valid, 'v2_backup': v2_valid,
            'legacy_backup_logical_parity': True, 'v2_backup_logical_parity': True,
            'raw_event_sha256': raw, 'raw_event_bytes_preserved': raw_preserved,
            'exact_workflow_retry_event_sha256': digest(retry['event']),
            'exact_workflow_retry_preserved': True, 'idle_active_run_preserved': True,
            'compaction': converted, 'compaction_exact_retry': converted_retry,
            'post_conversion_full_audit': migrated_audit,
            'gc_candidate_bytes': gc_plan['candidate_bytes'], 'gc_candidate_count': len(gc_plan['candidates']),
            'gc': collected, 'gc_exact_retry': collected_retry,
            'unknown_file_retained': True, 'final_full_audit': final_audit,
            'final_physical': physical, 'command_count': len(calls),
            'limitations': [
                'Owned synthetic run metadata and hash-bound review bodies, not verifier-backed customer deliveries.',
                'No existing-root input; all maintenance and backup effects occur under the owned temporary directory.',
                'Dry-run comparison covers regular-file content in a generated tree, excluding four documented telemetry files; it is not a general filesystem metadata preservation claim.',
                'GC successful-unlink bytes are distinct from net root disk change and exclude filesystem allocation accounting.',
                'Physical maintenance receipts are separate from the complete logical state/operation digest.',
                'No production migration, signed-in dispatch, new native Windows validation or controlled-load guarantee.',
            ],
        }
    result['owned_roots_removed'] = all(not path.exists() for path in owned)
    assert result['owned_roots_removed']
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--transcript', required=True, type=Path)
    args = parser.parse_args()
    report = run(args.output, args.transcript)
    print(json.dumps({'success': report['success'], 'commands': report['command_count'],
                      'reclaimed_bytes': report['gc']['reclaimed_bytes'],
                      'logical_parity': report['original_logical_sha256'] == report['final_logical_sha256'],
                      'owned_roots_removed': report['owned_roots_removed']}))
