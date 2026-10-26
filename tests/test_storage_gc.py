"""Only proven unreferenced content may be removed; every history remains live."""
import importlib.util
import multiprocessing
import os
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib import store,sqlite_store
from workflow_lib.storage_objects import put_object,read_object
from workflow_lib.run_archives import archive_run
from workflow_lib.storage_pins import reserve

def killed_gc(root,plan_hash):
    from workflow_lib.storage_gc import apply_gc
    from unittest.mock import patch
    original=Path.unlink
    def die(path,*args,**kwargs):
        result=original(path,*args,**kwargs)
        if 'objects' in path.parts:os._exit(61)
        return result
    with patch.object(Path,'unlink',die):apply_gc(Path(root),plan_hash,operation_id='interrupted',actor_id='owner')

class StorageGCTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory());self.root=(Path(self.temp)/'control').resolve();sqlite_store.initialize_store(self.root)
        store.transact(self.root,0,'seed',{'kind':'fixture','payload':{'runs':{'closed':{'id':'closed','status':'discarded','active_attempt':None,'text':'archived-only payload é東京'}}}})
        archive_run(self.root,'closed');self.original=store.read_state(self.root)
    def backend(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.storage_gc'),'reachability collector is missing')
        from workflow_lib import storage_gc
        return storage_gc
    def test_gc_preserves_archived_and_pinned_roots(self):
        gc=self.backend();orphan=put_object(self.root,'source-field',b'unreferenced orphan')
        plan=gc.gc_plan(self.root);self.assertGreater(plan['candidate_bytes'],0)
        self.assertTrue(any(orphan['object_id'] in row.get('object_id','') for row in plan['candidates']))
        with reserve(self.root,'prepared-context'):
            with self.assertRaises(store.WorkflowError):gc.apply_gc(self.root,plan['plan_hash'],operation_id='gc',actor_id='owner')
        fresh=gc.gc_plan(self.root);receipt=gc.apply_gc(self.root,fresh['plan_hash'],operation_id='gc',actor_id='owner')
        self.assertGreater(receipt['reclaimed_bytes'],0);self.assertEqual(store.read_state(self.root),self.original)
        with self.assertRaises(store.WorkflowError):read_object(self.root,orphan,max_bytes=1024)
    def test_physical_operation_ids_cannot_be_reused_by_workflow(self):
        gc=self.backend();put_object(self.root,'source-field',b'orphan');plan=gc.gc_plan(self.root)
        gc.apply_gc(self.root,plan['plan_hash'],operation_id='physical',actor_id='owner')
        before=store.read_state(self.root)
        with self.assertRaises(store.WorkflowError):
            store.transact(self.root,before['version'],'physical',{'kind':'fixture','payload':{'wrong':True}})
        self.assertEqual(store.read_state(self.root),before)

    def test_new_publication_stales_plan(self):
        gc=self.backend();put_object(self.root,'source-field',b'old orphan');plan=gc.gc_plan(self.root)
        put_object(self.root,'source-field',b'new publication')
        with self.assertRaises(store.WorkflowError):gc.apply_gc(self.root,plan['plan_hash'],operation_id='stale',actor_id='owner')
    def test_interrupted_unlink_resumes_without_losing_history(self):
        gc=self.backend();orphan=put_object(self.root,'source-field',b'interrupted orphan');plan=gc.gc_plan(self.root)
        ctx=multiprocessing.get_context('spawn');child=ctx.Process(target=killed_gc,args=(str(self.root),plan['plan_hash']));child.start();child.join(15)
        self.assertEqual(child.exitcode,61);self.assertEqual(store.read_state(self.root),self.original)
        receipt=gc.apply_gc(self.root,plan['plan_hash'],operation_id='interrupted',actor_id='owner')
        self.assertFalse(receipt['deferred']);self.assertGreater(receipt['absent_after_interruption'],0)
        for row in plan['candidates']:self.assertFalse((self.root/row['path']).exists())
        retry=gc.apply_gc(self.root,plan['plan_hash'],operation_id='interrupted',actor_id='owner')
        self.assertTrue(retry['replayed']);self.assertEqual(store.read_state(self.root),self.original)

    def test_backup_retains_pending_maintenance_operation_identity(self):
        from workflow_lib.storage_audit import perform,operation_reserved
        from workflow_lib.storage_maintenance import backup_control
        def interrupted(audit):raise KeyboardInterrupt('owned interrupted maintenance')
        with self.assertRaises(KeyboardInterrupt):perform(self.root,'gc',{'plan_hash':'f'*64},'pending','owner',interrupted)
        backup=Path(self.temp)/'backup';backup_control(self.root,backup)
        self.assertIsNotNone(operation_reserved(backup,'pending'))
        with self.assertRaises(store.WorkflowError):store.transact(backup,1,'pending',{'kind':'fixture','payload':{'wrong':True}})

    def test_checkpoint_database_keeps_prior_projection_objects(self):
        from workflow_lib.storage_journal import checkpoint
        gc=self.backend();state=store.read_state(self.root)
        run={'id':'large','status':'active','active_attempt':None,'opaque':'x'*100000}
        store.transact(self.root,state['version'],'large',{'kind':'fixture','payload':{'runs':{'large':run}}})
        with sqlite_store.connection(self.root) as conn:
            codec,payload=conn.execute('SELECT codec,payload FROM entities WHERE space=? AND key=?',(sqlite_store._space(('runs',)),'large')).fetchone()
        self.assertEqual(codec,'run-record-object');old=json.loads(payload)
        with store._exclusive(self.root):checkpoint(self.root,'owned-checkpoint')
        current=store.read_state(self.root);run['opaque']='changed'*20000
        store.transact(self.root,current['version'],'update',{'kind':'fixture','payload':{'runs':{'large':run}}})
        plan=gc.gc_plan(self.root)
        self.assertNotIn(old['object_id'],{row.get('object_id') for row in plan['candidates']})
        self.assertTrue(read_object(self.root,old,max_bytes=256*1024))

    def test_unknown_chunk_content_is_retained(self):
        gc=self.backend();path=self.root/'objects/chunks/gzip/aa'/('b'*62+'.blob')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'unknown user content')
        plan=gc.gc_plan(self.root);relative=path.relative_to(self.root).as_posix()
        self.assertNotIn(relative,{row['path'] for row in plan['candidates']})
        self.assertIn(relative,plan['retained_unknown'])

    def test_full_verify_rejects_corrupt_physical_audit(self):
        from workflow_lib.storage_audit import paths
        from workflow_lib.storage_maintenance import verify_store
        gc=self.backend();plan=gc.gc_plan(self.root);gc.apply_gc(self.root,plan['plan_hash'],operation_id='audit',actor_id='owner')
        receipt=paths(self.root,'audit')[0];record=json.loads(receipt.read_text());record['body']['actor_id']='tampered';receipt.write_text(json.dumps(record))
        self.assertFalse(verify_store(self.root,full=True)['valid'])

    def test_backup_refuses_in_flight_publication(self):
        from workflow_lib.storage_maintenance import backup_control
        with reserve(self.root,'context-publication'):
            with self.assertRaises(store.WorkflowError):backup_control(self.root,Path(self.temp)/'inflight-backup')
        self.assertFalse((Path(self.temp)/'inflight-backup/backup.json').exists())

    def test_pin_from_another_root_cannot_be_reconciled(self):
        from workflow_lib.storage_pins import reconcile
        pin=reserve(self.root,'prepared-context');path=pin.path;body=json.loads(path.read_text());pin.close()
        body['root_id']='0'*32;path.write_text(json.dumps(body))
        with self.assertRaises(store.WorkflowError):reconcile(self.root)
        self.assertTrue(path.exists())

    def test_symlink_escape_blocks_gc_and_preserves_external_file(self):
        gc=self.backend();external=Path(self.temp)/'external';external.write_bytes(b'owned external')
        link=self.root/'objects/unknown-link'
        try:link.symlink_to(external)
        except OSError as exc:self.skipTest('symlink creation unavailable: '+str(exc))
        with self.assertRaises(store.WorkflowError):gc.gc_plan(self.root)
        self.assertEqual(external.read_bytes(),b'owned external')

    def test_unknown_record_kind_does_not_become_a_gc_candidate(self):
        gc=self.backend();put_object(self.root,'future-record',b'{"record_version":1,"node":{"map":{}}}')
        with self.assertRaises(store.WorkflowError):gc.gc_plan(self.root)

    def test_live_process_pin_blocks_actual_gc(self):
        from test_storage_pins import pin_process
        gc=self.backend();orphan=put_object(self.root,'source-field',b'process-pinned orphan');plan=gc.gc_plan(self.root)
        ctx=multiprocessing.get_context('spawn');ready,stop=ctx.Event(),ctx.Event()
        child=ctx.Process(target=pin_process,args=(str(self.root),ready,stop));child.start()
        try:
            self.assertTrue(ready.wait(10))
            with self.assertRaises(store.WorkflowError):gc.apply_gc(self.root,plan['plan_hash'],operation_id='process-gc',actor_id='owner')
            self.assertEqual(read_object(self.root,orphan,max_bytes=1024),b'process-pinned orphan')
        finally:stop.set();child.join(10)
        self.assertEqual(child.exitcode,0)
        plan=gc.gc_plan(self.root);gc.apply_gc(self.root,plan['plan_hash'],operation_id='process-gc',actor_id='owner')
        self.assertEqual(store.read_state(self.root),self.original)

    def test_missing_graph_blocks_deletion(self):
        gc=self.backend();put_object(self.root,'source-field',b'orphan')
        with sqlite_store.connection(self.root) as conn:
            record=json.loads(conn.execute("SELECT payload FROM entities WHERE space=? AND key='closed'",(sqlite_store._space(('runs',)),)).fetchone()[0])
        ref=record['reference'];manifest=self.root/'objects/manifests'/ref['object_id'][:2]/(ref['object_id'][2:]+'.json');manifest.unlink()
        with self.assertRaises(store.WorkflowError):gc.gc_plan(self.root)
    def test_failed_unlink_does_not_claim_reclamation(self):
        gc=self.backend();put_object(self.root,'source-field',b'orphan');plan=gc.gc_plan(self.root)
        original=Path.unlink
        def locked(path,*args,**kwargs):
            if path.is_relative_to(self.root/'objects'):raise PermissionError('simulated Windows sharing violation')
            return original(path,*args,**kwargs)
        with patch.object(Path,'unlink',locked):receipt=gc.apply_gc(self.root,plan['plan_hash'],operation_id='locked',actor_id='owner')
        self.assertEqual(receipt['reclaimed_bytes'],0);self.assertTrue(receipt['deferred'])
        self.assertEqual(store.read_state(self.root),self.original)
