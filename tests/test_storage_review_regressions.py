"""Public recovery and independent-discovery boundaries from whole-branch review."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from commands.state import dispatch
from control_store_fixtures import legacy_root
from workflow_lib import sqlite_store as sql, store, storage_maintenance as maintenance
from workflow_lib.storage_format import DATABASE_FILE
from workflow_lib.storage_access import read_current,read_history,find_entity_id,document_diff_approved
from workflow_lib.storage_pins import reserve

class StorageReviewRegressionTests(unittest.TestCase):
    def setUp(self):
        self.base=Path(self.enterContext(tempfile.TemporaryDirectory()))
    def root(self,name='control',*,legacy=False,data=None):
        root=self.base/name
        if legacy:legacy_root(root)
        store.transact(root,0,'seed',{'kind':'fixture','payload':data if data is not None else {
            'runs':{'closed':{'id':'closed','status':'discarded','active_attempt':None}}}})
        return root
    def command(self,root,action,operation,**kw):
        values=dict(root=str(root),state_command=action,operation_id=operation,
            operation_id_explicit=True,actor_id='owner',details=False,apply=False,resume=False)
        values.update(kw)
        return dispatch(SimpleNamespace(**values))
    def corrupt(self,root,statement,parameters=()):
        conn=sql._sqlite().connect(root/DATABASE_FILE)
        try:
            conn.execute('PRAGMA foreign_keys=ON');conn.execute(statement,parameters);conn.commit()
        finally:conn.close()
    def snapshot(self,path):
        return {p.relative_to(path).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path(path).rglob('*') if p.is_file()}
    def interrupt_compaction(self,root,phase):
        plan=maintenance.compaction_plan(root);original=maintenance._write_intent
        def interrupt(root_,intent):
            original(root_,intent)
            if intent['phase']==phase:raise OSError('owned durable phase interruption')
        with patch.object(maintenance,'_write_intent',side_effect=interrupt):
            with self.assertRaises((OSError,store.WorkflowError)):
                maintenance.apply_authorized_compaction(root,plan['plan_hash'],operation_id='compact',actor_id='owner')
        return plan
    def interrupt_backup(self,root,output,operation='backup'):
        from workflow_lib import storage_backups
        original=storage_backups._copy_file
        def interrupt(source,target):
            original(source,target);raise OSError('owned copied-file interruption')
        with patch.object(storage_backups,'_copy_file',side_effect=interrupt):
            with self.assertRaises(OSError):self.command(root,'backup',operation,output=str(output))
        self.assertFalse((output/'backup.json').exists())

    def test_public_legacy_resume_after_each_preactivation_phase(self):
        for phase in ('database-committed','objects-synced','ready','guard-installed'):
            with self.subTest(phase=phase):
                root=self.root(phase,legacy=True);before=store.read_state(root)
                self.interrupt_compaction(root,phase)
                result=subprocess.run([sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),
                    'state','compact','--root',str(root),'--resume','--operation-id','compact','--actor-id','owner'],
                    cwd=ROOT,capture_output=True,encoding='utf-8',timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertTrue(json.loads(result.stdout)['completed'])
                self.assertEqual(store.read_state(root),before)
                self.assertTrue(maintenance.verify_store(root,full=True)['valid'])

    def test_public_backup_exact_retry_resumes_and_preserves_receipt(self):
        root=self.root();output=self.base/'backup';before=store.read_state(root)
        self.interrupt_backup(root,output)
        result=self.command(root,'backup','backup',output=str(output))
        self.assertTrue(result['completed']);self.assertEqual(store.read_state(output),before)
        store.transact(root,1,'newer',{'kind':'note','payload':{'later':True}})
        retry=self.command(root,'backup','backup',output=str(output))
        self.assertTrue(retry['replayed'])
        self.assertEqual({k:v for k,v in result.items() if k!='replayed'},{k:v for k,v in retry.items() if k!='replayed'})
        self.assertEqual(store.read_state(output),before)

    def test_new_backup_request_cannot_claim_another_snapshot(self):
        for source in ('different-root','same-root-newer-head'):
            with self.subTest(source=source):
                root=self.root(source);output=self.base/(source+'-backup')
                self.command(root,'backup','first',output=str(output));before=self.snapshot(output)
                if source=='different-root':root=self.root(source+'-other',data={'different':'source'})
                else:store.transact(root,1,'newer',{'kind':'note','payload':{'later':True}})
                with self.assertRaises(store.WorkflowError):self.command(root,'backup','second',output=str(output))
                self.assertEqual(self.snapshot(output),before)

    def test_another_backup_operation_cannot_adopt_incomplete_output(self):
        root=self.root();output=self.base/'backup';self.interrupt_backup(root,output,'first')
        before=self.snapshot(output)
        for _ in range(2):
            with self.assertRaises(store.WorkflowError):self.command(root,'backup','second',output=str(output))
            self.assertEqual(self.snapshot(output),before)
        self.assertTrue(self.command(root,'backup','first',output=str(output))['completed'])

    def test_resumed_compaction_rechecks_live_pins_before_generation_changes(self):
        root=self.root();self.interrupt_compaction(root,'preparing')
        with sql.connection(root) as conn:generation=sql._meta(conn,'generation')
        pin=reserve(root,'prepared-context')
        try:
            with self.assertRaises(store.WorkflowError) as caught:
                maintenance.apply_authorized_compaction(root,maintenance._read_json(root/'maintenance/intent.json')['plan']['plan_hash'],operation_id='compact',actor_id='owner')
            self.assertEqual(caught.exception.code,'MAINTENANCE_BLOCKED')
            with sql.connection(root) as conn:self.assertEqual(sql._meta(conn,'generation'),generation)
        finally:pin.close()
        self.assertTrue(self.command(root,'compact','compact',**{'resume':True})['completed'])

    def test_missing_global_namespace_cannot_downgrade_approval(self):
        from test_hosts import host_state
        from workflow_lib.repo_input_gate import require_current_spec
        data=host_state();data['spec_pair']={'repo_id':'missing','requirements_path':'requirements.md','design_path':'design.md'}
        root=self.root(data=data)
        with self.assertRaises(store.WorkflowError):require_current_spec(root,read_current(root),'before',record_drift=False)
        self.corrupt(root,'DELETE FROM spaces WHERE path=?',(sql._space(('spec_pair',)),))
        with self.assertRaises(store.WorkflowError) as caught:read_current(root)
        self.assertEqual(caught.exception.code,'CORRUPT_STORAGE')

    def test_empty_namespace_loss_is_not_genuine_absence(self):
        root=self.root(data={'approval':{}})
        self.corrupt(root,'DELETE FROM spaces WHERE path=?',(sql._space(('approval',)),))
        with self.assertRaises(store.WorkflowError):read_current(root,global_keys=('approval',))

    def test_empty_indexed_namespace_loss_fails_selected_discovery(self):
        for mode,namespace,value in (('history','runs',{}),('report','reports',[]),('entity','host_tasks',{}),('document','document_proposals',{})):
            with self.subTest(mode=mode):
                root=self.root(mode+'-empty',data={namespace:value})
                self.corrupt(root,'DELETE FROM spaces WHERE path=?',(sql._space((namespace,)),))
                with self.assertRaises(store.WorkflowError):
                    if mode=='history':read_history(root,'routing')
                    elif mode=='report':find_entity_id(root,'reports','absent')
                    elif mode=='entity':read_current(root,global_keys=(),entities=(('host_tasks','absent'),))
                    else:document_diff_approved(root,{},'repo','docs/a.md',{'before':'x'})

    def test_historical_run_discovery_cannot_hide_missing_authority(self):
        root=self.root();self.corrupt(root,'DELETE FROM entities WHERE space=? AND key=?',(sql._space(('runs',)),'closed'))
        with self.assertRaises(store.WorkflowError):read_history(root,'metrics')

    def test_attributed_usage_discovery_checks_independent_witnesses(self):
        root=self.root(data={'runs':{'closed':{'id':'closed','status':'discarded'}},'usage':{'events':[{'id':'usage','run_id':'closed','tokens':1}]}})
        self.corrupt(root,'DELETE FROM entities WHERE space=?',(sql._space(('usage','events')),))
        with self.assertRaises(store.WorkflowError):read_history(root,'metrics',run_id='closed',namespaces=('usage',))

    def test_frozen_report_discovery_cannot_hide_changed_identity(self):
        root=self.root(data={'reports':[{'id':'frozen','content':'retained'}]})
        self.assertEqual(find_entity_id(root,'reports','frozen'),{'id':'frozen','content':'retained'})
        self.corrupt(root,'UPDATE entities SET record_id=? WHERE space=?',('changed',sql._space(('reports',))))
        with self.assertRaises(store.WorkflowError):find_entity_id(root,'reports','frozen')

    def test_document_discovery_checks_authority_and_approval_witnesses(self):
        record={'before':'original','after':'updated'}
        for damage in ('index-row','index-header','approval-row'):
            with self.subTest(damage=damage):
                root=self.root(damage,data={'document_proposals':{'proposal':{'repo_id':'repo','proposal_hash':'proposal','files':{'docs/a.md':record}}},'document_approvals':{'proposal':{'approved':True}}})
                self.assertTrue(document_diff_approved(root,{},'repo','docs/a.md',record))
                if damage=='approval-row':self.corrupt(root,'DELETE FROM entities WHERE space=?',(sql._space(('document_approvals',)),))
                elif damage=='index-row':self.corrupt(root,'DELETE FROM document_files')
                else:self.corrupt(root,'UPDATE document_files SET path=?',('docs/changed.md',))
                with self.assertRaises(store.WorkflowError):document_diff_approved(root,{},'repo','docs/a.md',record)

    def archived_operations(self):
        root=self.root();store.transact(root,1,'newer',{'kind':'note','payload':{'later':True}})
        plan=maintenance.compaction_plan(root);maintenance.apply_compaction(root,plan['plan_hash'])
        return root
    def test_missing_archived_locator_is_not_absent_operation(self):
        root=self.archived_operations();self.corrupt(root,'DELETE FROM events WHERE operation_id=?',('seed',))
        with self.assertRaises(store.WorkflowError):sql.lookup_operation(root,'seed')
    def test_missing_archived_locator_cannot_reexecute_its_id(self):
        root=self.archived_operations();self.corrupt(root,'DELETE FROM events WHERE operation_id=?',('seed',))
        with self.assertRaises(store.WorkflowError):store.transact(root,2,'seed',{'kind':'note','payload':{'wrong':True}})
        conn=sql._sqlite().connect(root/DATABASE_FILE)
        try:self.assertEqual(json.loads(conn.execute('SELECT value FROM metadata WHERE key=?',('head',)).fetchone()[0]),2)
        finally:conn.close()
    def test_missing_operation_witness_blocks_lookup_and_full_audit(self):
        root=self.archived_operations()
        conn=sql._sqlite().connect(root/DATABASE_FILE)
        try:self.assertIsNotNone(conn.execute("SELECT name FROM sqlite_master WHERE name='operation_catalog'").fetchone(),'real independent operation catalog required')
        finally:conn.close()
        self.corrupt(root,'DELETE FROM operation_catalog WHERE operation_id=?',('seed',))
        with self.assertRaises(store.WorkflowError):sql.lookup_operation(root,'seed')
        self.assertFalse(maintenance.verify_store(root,full=True)['valid'])
