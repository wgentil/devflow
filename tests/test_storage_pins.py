"""Durable reservations, current storage identity and actual process ownership."""
import importlib.util
import multiprocessing
import queue
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib import store,sqlite_store
from workflow_lib.storage_maintenance import compaction_plan,apply_compaction

def pin_process(root,ready,stop):
    from workflow_lib.storage_pins import reserve
    with reserve(Path(root),'prepared-context'):
        ready.set();stop.wait(15)

def prepare_process(root,ready,publish,published,stop):
    from workflow_lib.storage_access import read_current
    from workflow_lib.context_preparation import prepare_context,compose_prepared
    from workflow_lib.context_transport import store_preparation,remove_preparation
    from workflow_lib.context_artifacts import store_context_artifact
    root=Path(root);state=read_current(root,run_id='current')
    p=prepare_context(root,state['data']['runs']['current'],{'run_id':'current'},['W1'],stage='implementation',state=state)
    ref=store_preparation(root,p)
    try:
        ready.set();publish.wait(15)
        view=compose_prepared(p.payload);artifact=store_context_artifact(root,view,{'binding_hash':p.binding_hash})
        (root/'published-test.json').write_text(__import__('json').dumps(artifact))
        published.set();stop.wait(15)
    finally:remove_preparation(root,ref);p.release()

def acquire_root(root,ready,result):
    ready.set()
    with store._exclusive(Path(root)):result.put('acquired')

def close_inherited_pin(pin):pin.close()

class StoragePinTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory());self.root=Path(self.temp)/'control';sqlite_store.initialize_store(self.root)
    def component(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.storage_pins'),'durable reservations are missing')
        from workflow_lib import storage_pins
        return storage_pins
    def test_gc_race_cannot_delete_prepared_or_dispatched_context(self):
        pins=self.component();ctx=multiprocessing.get_context('spawn');ready,stop=ctx.Event(),ctx.Event()
        child=ctx.Process(target=pin_process,args=(str(self.root),ready,stop));child.start()
        try:
            self.assertTrue(ready.wait(10));plan=compaction_plan(self.root)
            self.assertTrue(plan['pins']);self.assertTrue(plan['blockers'])
            with self.assertRaises(store.WorkflowError):apply_compaction(self.root,plan['plan_hash'])
            with self.assertRaises(store.WorkflowError):pins.reconcile(self.root)
        finally:stop.set();child.join(10)
        self.assertEqual(child.exitcode,0);self.assertEqual(compaction_plan(self.root)['pins'],[])
    def test_crashed_pin_requires_ownership_reconciliation(self):
        pins=self.component();ctx=multiprocessing.get_context('spawn');ready,stop=ctx.Event(),ctx.Event()
        child=ctx.Process(target=pin_process,args=(str(self.root),ready,stop));child.start()
        self.assertTrue(ready.wait(10));child.terminate();child.join(10)
        self.assertTrue(compaction_plan(self.root)['blockers'])
        result=pins.reconcile(self.root);self.assertEqual(result['released'],1)
        self.assertEqual(compaction_plan(self.root)['pins'],[])
    def test_legacy_preparation_blocks_conversion(self):
        pins=self.component();legacy=Path(self.temp)/'legacy'
        store.transact(legacy,0,'seed',{'kind':'fixture','payload':{'runs':{}}})
        with pins.reserve(legacy,'prepared-context'):
            plan=compaction_plan(legacy)
            self.assertTrue(plan['pins'])
            with self.assertRaises(store.WorkflowError):apply_compaction(legacy,plan['plan_hash'])

    def test_real_preparation_publication_and_maintenance_interleave(self):
        from large_context_fixtures import make_context_project
        from workflow_lib.context_artifacts import inspect_context_artifact
        fixture=make_context_project(Path(self.temp)/'publication');root=fixture['root']
        plan=compaction_plan(root);apply_compaction(root,plan['plan_hash'])
        ctx=multiprocessing.get_context('spawn');ready,publish,published,stop=[ctx.Event() for _ in range(4)]
        child=ctx.Process(target=prepare_process,args=(str(root),ready,publish,published,stop));child.start()
        try:
            self.assertTrue(ready.wait(10));plan=compaction_plan(root)
            self.assertTrue(plan['pins'])
            with self.assertRaises(store.WorkflowError):apply_compaction(root,plan['plan_hash'])
            publish.set();self.assertTrue(published.wait(10))
            import json
            ref=json.loads((root/'published-test.json').read_text(encoding="utf-8"))
            view=inspect_context_artifact(root,ref['artifact_id'])
            self.assertEqual(view['task_view']['coverage']['missing_ids'],[])
            self.assertTrue(compaction_plan(root)['blockers'])
        finally:publish.set();stop.set();child.join(10)
        self.assertEqual(child.exitcode,0);self.assertEqual(compaction_plan(root)['pins'],[])

    @unittest.skipUnless('fork' in multiprocessing.get_all_start_methods(),'POSIX fork ownership probe')
    def test_reentrant_coordination_does_not_cross_process_owner(self):
        ctx=multiprocessing.get_context('fork');ready=ctx.Event();result=ctx.Queue()
        child=ctx.Process(target=acquire_root,args=(str(self.root),ready,result))
        try:
            with store._exclusive(self.root):
                child.start();self.assertTrue(ready.wait(5))
                with self.assertRaises(queue.Empty):result.get(timeout=.25)
            self.assertEqual(result.get(timeout=5),'acquired')
        finally:child.join(5)
        self.assertEqual(child.exitcode,0)

    @unittest.skipUnless('fork' in multiprocessing.get_all_start_methods(),'POSIX inherited lease ownership probe')
    def test_fork_child_cannot_release_parent_pin(self):
        pins=self.component()
        with pins.reserve(self.root,'prepared-context') as pin:
            child=multiprocessing.get_context('fork').Process(target=close_inherited_pin,args=(pin,));child.start();child.join(5)
            self.assertEqual(child.exitcode,0);self.assertTrue(pin.path.exists())
            with self.assertRaises(store.WorkflowError):pins.reconcile(self.root)
        self.assertEqual(compaction_plan(self.root)['pins'],[])

    def test_layout_change_invalidates_prepared_commit(self):
        from large_context_fixtures import make_context_project
        from workflow_lib.context_preparation import prepare_context,assert_preparation_current
        from workflow_lib.storage_access import read_current
        fixture=make_context_project(Path(self.temp)/'project');root=fixture['root'];plan=compaction_plan(root);apply_compaction(root,plan['plan_hash'])
        state=read_current(root,run_id='current');p=prepare_context(root,state['data']['runs']['current'],{'run_id':'current'},['W1'],stage='implementation',state=state)
        try:
            with store._exclusive(root),sqlite_store.connection(root,write=True) as conn:
                sqlite_store._set_meta(conn,'generation',sqlite_store._meta(conn,'generation')+1)
            with self.assertRaises(store.WorkflowError):assert_preparation_current(root,p,state)
        finally:
            if hasattr(p,'release'):p.release()

    def test_live_pin_metadata_is_readable_without_releasing_ownership(self):
        import json,hashlib
        from workflow_lib.storage_backups import file_hash
        pins=self.component()
        with pins.reserve(self.root,'readable-metadata') as pin:
            raw=pin.path.read_bytes();body=json.loads(raw)
            self.assertEqual(body['pin_version'],2)
            self.assertLess(len(raw),65536)
            self.assertEqual(file_hash(pin.path),hashlib.sha256(raw).hexdigest())
            self.assertTrue(compaction_plan(self.root)['blockers'])
            with self.assertRaises(store.WorkflowError) as caught:pins.reconcile(self.root)
            self.assertEqual(caught.exception.code,'PIN_OWNER_ACTIVE')
            self.assertEqual(pin.path.read_bytes(),raw)
        self.assertFalse(pin.path.exists())

    def test_legacy_pin_ownership_is_proved_before_reconciliation(self):
        import json,os
        from workflow_lib.platform_lock import exclusive_file
        from workflow_lib.storage_format import detect_layout
        pins=self.component();layout=detect_layout(self.root);directory=self.root/'pins';directory.mkdir(exist_ok=True)
        path=directory/('a'*32+'.json');body={'pin_version':1,'id':path.stem,'kind':'legacy-candidate','pid':1,
            'root_id':layout['root_id'],'layout_id':layout['layout_id']}
        raw=json.dumps(body).encode('utf-8');path.write_bytes(raw)
        with path.open('r+b') as handle,exclusive_file(handle):
            with self.assertRaises(store.WorkflowError) as caught:pins.reconcile(self.root)
            self.assertEqual(caught.exception.code,'PIN_OWNER_ACTIVE')
        self.assertEqual(path.read_bytes(),raw)
        self.assertEqual(pins.reconcile(self.root)['released'],1)
        self.assertFalse(path.exists())

    def test_empty_pin_reconciliation_preserves_original_bytes(self):
        pins=self.component();directory=self.root/'pins';directory.mkdir(exist_ok=True)
        path=directory/('b'*32+'.json');path.write_bytes(b'')
        with self.assertRaises(store.WorkflowError) as caught:pins.reconcile(self.root)
        self.assertEqual(caught.exception.code,'INVALID_STORAGE_PIN')
        self.assertEqual(path.read_bytes(),b'')
