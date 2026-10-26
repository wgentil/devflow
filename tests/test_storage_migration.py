"""Explicit migration preserves complete logical and raw legacy history."""
import gzip
import importlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from copy import deepcopy
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib import store, sqlite_store
from control_store_fixtures import owned_control, legacy_root

class StorageMigrationTests(unittest.TestCase):
    def backend(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.storage_maintenance'))
        return importlib.import_module('workflow_lib.storage_maintenance')

    def test_migration_logical_and_retry_parity(self):
        maintenance = self.backend()
        from storage_event_cases import basic_event_streams, captured_event_streams, supplemental_domain_streams
        streams = list(basic_event_streams()) + captured_event_streams() + list(supplemental_domain_streams())
        for index, events in enumerate(streams):
            with self.subTest(stream=index), owned_control() as root:
                legacy_root(root)
                state = store._empty()
                for position, source in enumerate(events, 1):
                    event = {'schema_version': 1, 'sequence': position,
                        'operation_id': source.get('operation_id', source.get('id')),
                        'kind': source['kind'], 'payload': deepcopy(source['payload'])}
                    if source.get('host_binding'): event['host_binding'] = source['host_binding']
                    (root / 'events' / f'{position:08d}.json').write_text(json.dumps(event, indent=2, ensure_ascii=False), encoding='utf-8')
                    store._apply_event(state, event)
                # Owned fixtures explicitly model a quiescent snapshot without running
                # any abandoned test worker; no production lease bypass exists.
                runs = deepcopy(state['data'].get('runs', {}))
                for run in runs.values():
                    run['active_attempt'] = None
                    for row in run.get('native_invocations', {}).values():
                        if row.get('status') == 'running': row['status'] = 'interrupted'
                    for row in run.get('repair_cycles', []):
                        if row.get('status') == 'claimed': row['status'] = 'aborted'
                if runs:
                    n = len(events) + 1
                    event = {'schema_version': 1, 'sequence': n, 'operation_id': 'fixture-quiescent',
                             'kind': 'fixture.quiescent', 'payload': {'runs': runs}}
                    (root / 'events' / f'{n:08d}.json').write_text(json.dumps(event, indent=2), encoding='utf-8')
                before = store.read_state(root)
                raw = {p.name: p.read_bytes() for p in (root / 'events').glob('*.json')}
                plan = maintenance.compaction_plan(root)
                self.assertEqual(plan['blockers'], [])
                receipt = maintenance.apply_compaction(root, plan['plan_hash'])
                self.assertTrue(receipt['completed'])
                self.assertEqual(store.read_state(root)['data'], before['data'])
                self.assertEqual(store.read_state(root)['operations'], before['operations'])
                for name, content in raw.items():
                    self.assertEqual(maintenance.read_raw_event(root, int(name[:-5])), {'name': name, 'bytes': content})
                first = next(iter(before['operations'].values()))
                retry = store.transact(root, -1, first['operation_id'], {'kind': 'other', 'payload': {}})
                self.assertTrue(retry['replayed']); self.assertEqual(retry['event'], first)
                self.assertEqual(maintenance.apply_compaction(root, plan['plan_hash']), receipt)
                self.assertTrue(maintenance.verify_store(root, full=True)['valid'])

    def test_active_work_and_stale_plan_block_application(self):
        maintenance = self.backend()
        with owned_control() as root:
            legacy_root(root)
            store.transact(root, 0, 'run', {'kind': 'run.started', 'payload': {'run': {
                'id': 'r', 'status': 'active', 'active_attempt': {'token': 't'}}}})
            plan = maintenance.compaction_plan(root)
            self.assertTrue(plan['blockers'])
            with self.assertRaises(store.WorkflowError): maintenance.apply_compaction(root, plan['plan_hash'])
            self.assertFalse((root / 'format.json').exists())
        with owned_control() as root:
            legacy_root(root)
            store.transact(root, 0, 'one', {'kind': 'note', 'payload': {'x': 1}})
            plan = maintenance.compaction_plan(root)
            store.transact(root, 1, 'two', {'kind': 'note', 'payload': {'x': 2}})
            with self.assertRaises(store.WorkflowError) as caught: maintenance.apply_compaction(root, plan['plan_hash'])
            self.assertEqual(caught.exception.code, 'STALE_MAINTENANCE_PLAN')
            self.assertEqual(store.read_state(root)['version'], 2)

    def test_actual_v0315_reader_writer_compatibility(self):
        maintenance = self.backend()
        with owned_control() as root, tempfile.TemporaryDirectory() as temp:
            legacy_root(root)
            store.transact(root, 0, 'one', {'kind': 'note', 'payload': {'original': 'é東京'}})
            archive = subprocess.run(['git', 'archive', 'v0.3.15', 'skills/workflow/scripts'], cwd=ROOT,
                                     capture_output=True, check=True).stdout
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar: tar.extractall(temp, filter='data')
            helper = Path(temp) / 'skills/workflow/scripts'
            plan = maintenance.compaction_plan(root); maintenance.apply_compaction(root, plan['plan_hash'])
            for expression in ('read_state(root)', "transact(root,0,'old-write',{'kind':'note','payload':{'fork':True}})"):
                code = "import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from workflow_lib.store import *;root=Path(sys.argv[2])\ntry:\n " + expression + "\nexcept WorkflowError as exc:print(exc.code);sys.exit(3)"
                result = subprocess.run([sys.executable, '-B', '-c', code, str(helper), str(root)], capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 3, result.stderr)
                self.assertEqual(result.stdout.strip(), 'UNSUPPORTED_SCHEMA')
            self.assertEqual(store.read_state(root)['version'], 1)
            self.assertIsNone(sqlite_store.lookup_operation(root, 'old-write'))

    def test_consistent_backup_relocates_with_objects_and_history(self):
        maintenance = self.backend()
        with owned_control() as root, tempfile.TemporaryDirectory() as temp:
            sqlite_store.initialize_store(root)
            store.transact(root, 0, 'one', {'kind': 'note', 'payload': {'text': 'é東京' * 10000}})
            output = Path(temp) / 'relocated backup'
            receipt = maintenance.backup_control(root, output)
            self.assertTrue(receipt['completed'])
            self.assertTrue(maintenance.verify_backup(output)['valid'])
            self.assertEqual(store.read_state(output)['data'], store.read_state(root)['data'])
            self.assertEqual(sqlite_store.lookup_operation(output, 'one'), sqlite_store.lookup_operation(root, 'one'))
            self.assertTrue(maintenance.verify_store(output, full=True)['valid'])


    @unittest.skipIf(sys.platform == 'win32', 'POSIX private-file permission semantics')
    def test_sqlite_authority_and_backup_keep_private_file_permissions(self):
        maintenance = self.backend()
        with owned_control() as root, owned_control() as output:
            sqlite_store.initialize_store(root)
            self.assertEqual((root / 'store-v2/control.sqlite3').stat().st_mode & 0o077, 0)
            maintenance.backup_control(root, output)
            self.assertEqual((output / 'store-v2/control.sqlite3').stat().st_mode & 0o077, 0)


    def test_migrated_auxiliary_receipt_still_rejects_conflicting_retry(self):
        maintenance = self.backend()
        from commands.journal import commit
        from types import SimpleNamespace
        with owned_control() as root:
            legacy_root(root)
            args = SimpleNamespace(root=str(root), operation_id='register', operation_id_explicit=True,
                                   expected_version=None)
            before = commit(args, 'domain.host.init', {'repo_id': 'app', 'location': '/owned/project'})
            plan = maintenance.compaction_plan(root); maintenance.apply_compaction(root, plan['plan_hash'])
            retry = commit(args, 'domain.host.init', {'repo_id': 'app', 'location': '/owned/project'})
            self.assertEqual(retry['event_sequence'], before['event_sequence'])
            self.assertTrue(retry['replayed'])
            with self.assertRaises(store.WorkflowError) as caught:
                commit(args, 'domain.host.init', {'repo_id': 'different', 'location': '/owned/project'})
            self.assertEqual(caught.exception.code, 'OPERATION_CONFLICT')

    def test_missing_object_and_active_pin_refuse_before_intent(self):
        maintenance = self.backend()
        with owned_control() as root:
            sqlite_store.initialize_store(root)
            store.transact(root, 0, 'one', {'kind': 'note', 'payload': {'text': 'source'}})
            manifest = next((root / 'objects/manifests').rglob('*.json'))
            manifest.unlink()
            plan = maintenance.compaction_plan(root)
            with self.assertRaises(store.WorkflowError): maintenance.apply_compaction(root, plan['plan_hash'])
            self.assertFalse((root / 'maintenance/intent.json').exists())
        with owned_control() as root:
            legacy_root(root)
            store.transact(root, 0, 'one', {'kind': 'note', 'payload': {}})
            pins = root / 'pins'; pins.mkdir(); (pins / 'reader.json').write_text('{}')
            plan = maintenance.compaction_plan(root)
            self.assertTrue(plan['blockers'])
            with self.assertRaises(store.WorkflowError): maintenance.apply_compaction(root, plan['plan_hash'])
            self.assertFalse((root / 'maintenance/intent.json').exists())
