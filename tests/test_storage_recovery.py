"""Process-death boundaries resume one selected history, preserving newer tails."""
import importlib
import importlib.util
import json
from pathlib import Path
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib import store, sqlite_store
from control_store_fixtures import owned_control, legacy_root

class StorageRecoveryTests(unittest.TestCase):
    def backend(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.storage_maintenance'))
        return importlib.import_module('workflow_lib.storage_maintenance')

    def seeded(self, root):
        legacy_root(root)
        store.transact(root, 0, 'one', {'kind': 'note', 'payload': {'text': 'é東京', 'unknown': [1, 2]}})

    def crash(self, root, phase, plan_hash):
        code = "import os,sys;from pathlib import Path;from workflow_lib import storage_maintenance as m\noriginal=m._write_intent\ndef crash(root,intent):\n original(root,intent)\n if intent['phase']==sys.argv[2]:os._exit(39)\nm._write_intent=crash\nm.apply_compaction(Path(sys.argv[1]),sys.argv[3])"
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'skills/workflow/scripts')}
        result = subprocess.run([sys.executable, '-B', '-c', code, str(root), phase, plan_hash], env=env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 39, result.stderr)

    def test_activation_crash_matrix(self):
        maintenance = self.backend()
        for phase in ('database-committed', 'objects-synced', 'ready', 'guard-installed', 'activated', 'cleanup'):
            with self.subTest(phase=phase), owned_control() as root:
                self.seeded(root); before = store.read_state(root)
                plan = maintenance.compaction_plan(root)
                self.crash(root, phase, plan['plan_hash'])
                receipt = maintenance.resume_compaction(root)
                self.assertTrue(receipt['completed'])
                self.assertEqual(store.read_state(root)['data'], before['data'])
                self.assertEqual(store.read_state(root)['operations'], before['operations'])
                self.assertTrue(maintenance.verify_store(root, full=True)['valid'])

    def test_resume_never_omits_newer_tail(self):
        maintenance = self.backend()
        with owned_control() as root:
            self.seeded(root)
            plan = maintenance.compaction_plan(root)
            self.crash(root, 'activated', plan['plan_hash'])
            store.transact(root, 1, 'new-tail', {'kind': 'note', 'payload': {'tail': True}})
            maintenance.resume_compaction(root)
            self.assertEqual(store.read_state(root)['version'], 2)
            self.assertTrue(store.read_state(root)['data']['tail'])
            self.assertIsNotNone(sqlite_store.lookup_operation(root, 'new-tail'))

    def test_changed_legacy_tail_refuses_resume(self):
        maintenance = self.backend()
        with owned_control() as root:
            self.seeded(root); plan = maintenance.compaction_plan(root)
            self.crash(root, 'ready', plan['plan_hash'])
            path = root / 'events/00000002.json'
            path.write_text(json.dumps({'schema_version': 1, 'sequence': 2, 'operation_id': 'new-tail',
                                      'kind': 'note', 'payload': {'tail': True}}))
            with self.assertRaises(store.WorkflowError): maintenance.resume_compaction(root)
            self.assertEqual(json.loads(path.read_text())['operation_id'], 'new-tail')
            self.assertFalse((root / 'format.json').exists())

    def test_disk_full_refuses_before_activation(self):
        maintenance = self.backend()
        from collections import namedtuple
        usage = namedtuple('usage', 'total used free')
        with owned_control() as root:
            self.seeded(root); plan = maintenance.compaction_plan(root)
            with patch.object(maintenance.shutil, 'disk_usage', return_value=usage(100, 100, 0)):
                with self.assertRaises(store.WorkflowError): maintenance.apply_compaction(root, plan['plan_hash'])
            self.assertFalse((root / 'format.json').exists())
            self.assertEqual(store.read_state(root)['version'], 1)

    def test_corrupt_checkpoint_fails_without_repair(self):
        maintenance = self.backend()
        with owned_control() as root:
            self.seeded(root); plan = maintenance.compaction_plan(root)
            self.crash(root, 'ready', plan['plan_hash'])
            intent = json.loads((root / 'maintenance/intent.json').read_text())
            ref = intent['checkpoint']
            manifest = root / 'objects/manifests' / ref['object_id'][:2] / (ref['object_id'][2:] + '.json')
            manifest.write_text('{}')
            with self.assertRaises(store.WorkflowError): maintenance.resume_compaction(root)
            self.assertFalse((root / 'format.json').exists())

    def test_missing_schema_trigger_fails_closed(self):
        maintenance = self.backend()
        import sqlite3
        with owned_control() as root:
            sqlite_store.initialize_store(root)
            conn = sqlite3.connect(root / 'store-v2/control.sqlite3')
            try: conn.execute('DROP TRIGGER dependency_insert'); conn.commit()
            finally: conn.close()
            with self.assertRaises(store.WorkflowError): store.read_state(root)


    def test_segment_catalog_cannot_omit_archived_events(self):
        maintenance = self.backend()
        import sqlite3
        with owned_control() as root:
            sqlite_store.initialize_store(root)
            store.transact(root, 0, 'one', {'kind': 'note', 'payload': {'x': 1}})
            plan = maintenance.compaction_plan(root); maintenance.apply_compaction(root, plan['plan_hash'])
            conn = sqlite3.connect(root / 'store-v2/control.sqlite3')
            try: conn.execute('DELETE FROM event_segments'); conn.commit()
            finally: conn.close()
            self.assertFalse(maintenance.verify_store(root, full=True)['valid'])

    def test_interrupted_backup_is_not_complete_and_can_resume(self):
        maintenance = self.backend()
        from workflow_lib import storage_backups
        with owned_control() as root, owned_control() as output:
            self.seeded(root)
            artifact = root / 'artifacts/evidence-wal'
            artifact.parent.mkdir(); artifact.write_bytes(b'original evidence')
            original = storage_backups._copy_file
            def interrupted(source, target):
                original(source, target)
                raise OSError('simulated interrupted copy')
            with patch.object(storage_backups, '_copy_file', side_effect=interrupted):
                with self.assertRaises(OSError): maintenance.backup_control(root, output)
            self.assertFalse(maintenance.verify_backup(output)['valid'])
            self.assertEqual(store.read_state(root)['version'], 1)
            result = maintenance.backup_control(root, output, resume=True)
            self.assertTrue(result['completed'])
            self.assertEqual((output / 'artifacts/evidence-wal').read_bytes(), b'original evidence')

    def test_initialization_intent_resumes_without_empty_authority_guess(self):
        maintenance = self.backend()
        with owned_control() as root:
            original = store._atomic_json
            def crash(path, value):
                if path.name == 'format.json': raise OSError('activation interrupted')
                return original(path, value)
            with patch.object(store, '_atomic_json', side_effect=crash):
                with self.assertRaises(OSError): sqlite_store.initialize_store(root)
            with self.assertRaises(store.WorkflowError): store.read_state(root)
            self.assertTrue(maintenance.resume_compaction(root)['completed'])
            self.assertEqual(store.read_state(root)['version'], 0)

    def test_streamed_checkpoint_file_publication(self):
        self.backend()
        from workflow_lib.storage_objects import CHUNK_BYTES, put_file, put_object, read_object
        with owned_control() as root:
            root.mkdir(); source = root / 'checkpoint-source'
            value = b'x' * CHUNK_BYTES + b'final page'
            source.write_bytes(value)
            reference = put_file(root, 'sqlite-checkpoint', source)
            self.assertEqual(put_object(root, 'sqlite-checkpoint', value), reference)
            self.assertEqual(read_object(root, reference, max_bytes=len(value)), value)

    def test_disk_failure_during_staging_resumes_without_loss(self):
        maintenance = self.backend()
        with owned_control() as root:
            self.seeded(root); plan = maintenance.compaction_plan(root)
            with patch.object(maintenance, 'put_object', side_effect=OSError('no space left')):
                with self.assertRaises(store.WorkflowError): maintenance.apply_compaction(root, plan['plan_hash'])
            self.assertFalse((root / 'format.json').exists())
            self.assertTrue(maintenance.resume_compaction(root)['completed'])
            self.assertEqual(store.read_state(root)['version'], 1)

    def test_newer_generation_is_never_overwritten_on_resume(self):
        maintenance = self.backend()
        from workflow_lib.run_archives import archive_run
        with owned_control() as root:
            sqlite_store.initialize_store(root)
            store.transact(root, 0, 'one', {'kind': 'note', 'payload': {'x': 1}})
            plan = maintenance.compaction_plan(root)
            self.crash(root, 'activated', plan['plan_hash'])
            store.transact(root, 1, 'new', {'kind': 'run.started', 'payload': {'run': {
                'id': 'new', 'status': 'discarded', 'active_attempt': None}}})
            archive_run(root, 'new')
            with self.assertRaises(store.WorkflowError): maintenance.resume_compaction(root)
            self.assertEqual(store.read_state(root)['version'], 2)
            self.assertIn('new', store.read_state(root)['data']['runs'])

    @unittest.skipUnless(os.name == 'nt', 'native Windows file-handle semantics')
    def test_windows_open_snapshot_cleanup_resumes(self):
        maintenance = self.backend()
        with owned_control() as root:
            self.seeded(root); plan = maintenance.compaction_plan(root)
            with (root / 'state.json').open('rb'):
                receipt = maintenance.apply_compaction(root, plan['plan_hash'])
                self.assertFalse(receipt['completed'])
                self.assertTrue(receipt['activated'])
                self.assertEqual(store.read_state(root)['version'], 1)
            self.assertTrue(maintenance.resume_compaction(root)['completed'])


    def test_locked_staging_cleanup_remains_resumable(self):
        maintenance = self.backend()
        with owned_control() as root:
            self.seeded(root); plan = maintenance.compaction_plan(root)
            with patch.object(maintenance.shutil, 'rmtree', side_effect=PermissionError('open handle')):
                receipt = maintenance.apply_compaction(root, plan['plan_hash'])
            self.assertFalse(receipt['completed'])
            self.assertTrue(receipt['activated'])
            self.assertTrue((root / 'maintenance/intent.json').exists())
            self.assertEqual(store.read_state(root)['version'], 1)
            self.assertTrue(maintenance.resume_compaction(root)['completed'])


    def test_missing_legacy_guard_cannot_authorize_new_work(self):
        self.backend()
        with owned_control() as root:
            sqlite_store.initialize_store(root)
            (root / 'events/00000001.json').unlink()
            with self.assertRaises(store.WorkflowError):
                store.transact(root, 0, 'unsafe', {'kind': 'note', 'payload': {'fork': True}})


    def test_corrupt_metadata_is_actionable_before_work(self):
        self.backend()
        import sqlite3
        for key, value in [('head', '{'), ('generation', 'true'), ('position', '-1')]:
            with self.subTest(key=key), owned_control() as root:
                sqlite_store.initialize_store(root)
                conn = sqlite3.connect(root / 'store-v2/control.sqlite3')
                try: conn.execute('UPDATE metadata SET value=? WHERE key=?', (value,key)); conn.commit()
                finally: conn.close()
                with self.assertRaises(store.WorkflowError) as caught: store.read_state(root)
                self.assertEqual(caught.exception.code, 'CORRUPT_STORAGE')
