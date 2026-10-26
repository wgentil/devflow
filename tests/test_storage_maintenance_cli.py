"""Manual maintenance must be reviewable, idempotent and independent of telemetry."""
import hashlib
import contextlib
import io
import tarfile
from unittest.mock import patch
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib import store,sqlite_store
from workflow_lib.storage_format import detect_layout
from workflow_lib.storage_backups import verify_backup
from control_store_fixtures import legacy_root

class MaintenanceCLITests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory());self.base=Path(self.temp);self.root=self.base/'control é東京'
        from control_store_fixtures import legacy_root
        legacy_root(self.root) # Explicit legacy conversion and old-client fixtures.
        store.transact(self.root,0,'seed',{'kind':'fixture','payload':{'runs':{'closed':{'id':'closed','status':'discarded','active_attempt':None}}}})
    def cli(self,*args,expected=0):
        result=subprocess.run([sys.executable,str(ROOT/'skills/workflow/scripts/run.py'),'state',*map(str,args)],cwd=ROOT,capture_output=True,encoding='utf-8',timeout=45)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        return json.loads(result.stdout)
    def files(self):
        return {p.relative_to(self.root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file() and p.name not in {'offload.jsonl','.offload.lock','context-metrics.jsonl','.context-metrics.lock'}}
    def test_maintenance_plan_and_retry_contracts(self):
        before=self.files();plan=self.cli('compact','--root',self.root)
        self.assertEqual(self.files(),before);self.assertEqual(detect_layout(self.root)['layout'],'legacy')
        self.assertNotIn('files',plan);self.assertIn('plan_hash',plan)
        # CLI dry-run telemetry must not invalidate this exact plan.
        applied=self.cli('compact','--root',self.root,'--apply','--plan-hash',plan['plan_hash'],'--operation-id','compact','--actor-id','owner')
        self.assertTrue(applied['completed']);self.assertEqual(detect_layout(self.root)['layout'],'v2')
        retry=self.cli('compact','--root',self.root,'--apply','--plan-hash',plan['plan_hash'],'--operation-id','compact','--actor-id','owner')
        self.assertEqual({k:v for k,v in applied.items() if k!='replayed'},{k:v for k,v in retry.items() if k!='replayed'})
        self.assertEqual(self.cli('compact','--root',self.root,'--apply','--plan-hash',plan['plan_hash'],'--operation-id','compact','--actor-id','different',expected=2)['error'],'OPERATION_CONFLICT')
        fresh=self.cli('compact','--root',self.root)
        state=store.read_state(self.root);store.transact(self.root,state['version'],'changed',{'kind':'fixture','payload':{'new':True}})
        self.assertEqual(self.cli('compact','--root',self.root,'--apply','--plan-hash',fresh['plan_hash'],'--operation-id','stale','--actor-id','owner',expected=2)['error'],'STALE_MAINTENANCE_PLAN')
    def test_backup_is_consistent(self):
        plan=self.cli('compact','--root',self.root)
        self.cli('compact','--root',self.root,'--apply','--plan-hash',plan['plan_hash'],'--operation-id','migrate','--actor-id','owner')
        before=store.read_state(self.root);output=self.base/'backup'
        self.cli('backup','--root',self.root,'--output',output,'--operation-id','backup','--actor-id','owner')
        self.assertTrue(verify_backup(output)['valid']);self.assertEqual(store.read_state(output),before)
    def test_policy_defaults_and_malformed_settings(self):
        self.assertNotIn('maintenance_policy',store.read_state(self.root)['data'])
        policy=self.base/'policy.json';policy.write_text('{"schema_version":1,"post_terminal_compaction":true}')
        self.cli('policy','--root',self.root,'--file',policy,'--operation-id','policy','--actor-id','owner')
        self.assertTrue(store.read_state(self.root)['data']['maintenance_policy']['post_terminal_compaction'])
        policy.write_text('{"schema_version":1,"post_terminal_compaction":"true"}')
        self.cli('policy','--root',self.root,'--file',policy,'--operation-id','invalid-policy','--actor-id','owner',expected=2)
    def test_post_terminal_failure_preserves_delivery_receipt(self):
        from storage_event_cases import captured_event_streams
        stream=next(stream for stream in captured_event_streams() if any(event['kind']=='delivery.recorded' for event in stream))
        index=next(i for i,event in enumerate(stream) if event['kind']=='delivery.recorded')
        root=self.base/'automatic';sqlite_store.initialize_store(root)
        for version,event in enumerate(stream[:index]):store.transact(root,version,event['operation_id'],event)
        store.transact(root,index,'policy',{'kind':'maintenance.policy.recorded','payload':{'maintenance_policy_authorization':{'actor_id':'owner','operation_id':'policy'},'maintenance_policy':{'schema_version':1,'post_terminal_compaction':True}}})
        event=stream[index];diagnostics=io.StringIO()
        with contextlib.redirect_stderr(diagnostics),patch('workflow_lib.storage_maintenance.apply_authorized_compaction',side_effect=OSError('owned failure')):
            receipt=store.transact(root,index+1,'terminal',event)
        self.assertEqual(store.read_state(root)['data']['runs'][event['payload']['run_id']]['status'],'delivered')
        self.assertIn('post-terminal',diagnostics.getvalue())
        retry=store.transact(root,-1,'terminal',event)
        self.assertTrue(retry['replayed']);self.assertEqual(retry['event'],receipt['event'])
        self.assertEqual(store.read_state(root)['version'],index+2)

    def test_opt_in_compaction_advances_storage_after_terminal_commit(self):
        root=self.base/'automatic';sqlite_store.initialize_store(root)
        store.transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':{'id':'r','status':'active','active_attempt':None}}}})
        store.transact(root,1,'policy',{'kind':'maintenance.policy.recorded','payload':{'maintenance_policy_authorization':{'actor_id':'owner','operation_id':'policy'},'maintenance_policy':{'schema_version':1,'post_terminal_compaction':True}}})
        result=store.transact(root,2,'terminal',{'kind':'run.discarded','payload':{'run_id':'r','actor_id':'owner','reason':'owned completion'}})
        self.assertEqual(result['event']['sequence'],3)
        with sqlite_store.connection(root) as conn:
            self.assertGreater(sqlite_store._meta(conn,'generation'),0)
            self.assertEqual(conn.execute('SELECT codec FROM entities WHERE space=? AND key=?',(sqlite_store._space(('runs',)),'r')).fetchone()[0],'archive2')
        self.assertEqual(store.read_state(root)['version'],3)

    def test_missing_apply_identity_and_changed_root_refuse_effects(self):
        plan=self.cli('compact','--root',self.root);before=self.files()
        for options in (('--apply','--plan-hash',plan['plan_hash'],'--actor-id','owner'),
                        ('--apply','--plan-hash',plan['plan_hash'],'--operation-id','missing-actor'),
                        ('--apply','--operation-id','missing-plan','--actor-id','owner')):
            self.cli('compact','--root',self.root,*options,expected=2)
        self.assertEqual(self.files(),before)
        other=self.base/'other';legacy_root(other);store.transact(other,0,'seed',{'kind':'fixture','payload':{'runs':{}}})
        self.assertEqual(self.cli('compact','--root',other,'--apply','--plan-hash',plan['plan_hash'],'--operation-id','wrong-root','--actor-id','owner',expected=2)['error'],'STALE_MAINTENANCE_PLAN')
        self.assertEqual(detect_layout(other)['layout'],'legacy')

    def test_policy_race_rejects_another_committed_request(self):
        from commands.state import dispatch
        from types import SimpleNamespace
        policy=self.base/'policy.json';policy.write_text('{"schema_version":1,"post_terminal_compaction":true}')
        parsed=SimpleNamespace(root=str(self.root),state_command='policy',operation_id='raced',operation_id_explicit=True,actor_id='owner',file=str(policy))
        def competitor(*args,**options):
            store.transact(self.root,1,'raced',{'kind':'maintenance.policy.recorded','payload':{'maintenance_policy_authorization':{'actor_id':'other','operation_id':'raced'},'maintenance_policy':{'schema_version':1,'post_terminal_compaction':False}}})
            return None
        with patch('workflow_lib.storage_access.operation_lookup',side_effect=competitor):
            with self.assertRaises(store.WorkflowError):dispatch(parsed)
        self.assertFalse(store.read_state(self.root)['data']['maintenance_policy']['post_terminal_compaction'])

    def test_legacy_policy_keeps_actual_v0315_replay_meaning(self):
        policy=self.base/'legacy-policy.json';policy.write_text('{"schema_version":1,"post_terminal_compaction":false}')
        self.cli('policy','--root',self.root,'--file',policy,'--operation-id','legacy-policy','--actor-id','owner')
        archive=subprocess.run(['git','archive','v0.3.15','skills/workflow/scripts'],cwd=ROOT,capture_output=True,check=True).stdout
        old=self.base/'old-helper';old.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(old,filter='data')
        code="import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from workflow_lib.store import read_state;print(json.dumps(read_state(Path(sys.argv[2]))['data'],sort_keys=True))"
        result=subprocess.run([sys.executable,'-B','-c',code,str(old/'skills/workflow/scripts'),str(self.root)],capture_output=True,encoding='utf-8',check=True)
        self.assertEqual(json.loads(result.stdout),store.read_state(self.root)['data'])

    def test_documented_policy_example_and_stopped_pin_recovery(self):
        from workflow_lib.storage_pins import reserve
        result=self.cli('policy','--root',self.root,'--file',ROOT/'docs/examples/maintenance-policy.json','--operation-id','example-policy','--actor-id','owner')
        self.assertFalse(result['policy']['post_terminal_compaction'])
        root=self.base/'pin-recovery';sqlite_store.initialize_store(root)
        pin=reserve(root,'prepared-context');path=pin.path;raw=path.read_bytes()
        self.assertEqual(self.cli('pins','--root',root)['pins_count'],1)
        self.cli('pins','--root',root,'--reconcile','--operation-id','busy','--actor-id','owner',expected=2)
        pin.close();path.write_bytes(raw)
        reconciled=self.cli('pins','--root',root,'--reconcile','--operation-id','reconcile','--actor-id','owner')
        self.assertEqual(reconciled['released'],1)
        self.assertEqual(self.cli('pins','--root',root)['pins_count'],0)
        self.assertTrue(self.cli('verify','--root',root,'--full')['valid'])

    def test_reviewer_cannot_apply_root_maintenance(self):
        from workflow_lib.releases import release_descriptor
        from workflow_lib.storage_maintenance import compaction_plan,apply_authorized_compaction
        binding={'binding_id':'reviewer','revision':1,'status':'active','role':'branch-reviewer','actor_id':'reviewer','run_id':'closed','release':release_descriptor()}
        store.transact(self.root,1,'binding',{'kind':'fixture','payload':{'host_bindings':{'reviewer':binding}}})
        plan=compaction_plan(self.root);before=store.read_state(self.root)
        token=store.HOST_CONTEXT.set({'binding_id':'reviewer','revision':1})
        try:
            with self.assertRaises(store.WorkflowError):apply_authorized_compaction(self.root,plan['plan_hash'],operation_id='denied',actor_id='reviewer')
        finally:store.HOST_CONTEXT.reset(token)
        self.assertEqual(store.read_state(self.root),before);self.assertEqual(detect_layout(self.root)['layout'],'legacy')

    def test_legacy_full_verification_checks_physical_audits(self):
        from workflow_lib.storage_audit import paths
        from workflow_lib.storage_maintenance import verify_store
        self.cli('backup','--root',self.root,'--output',self.base/'legacy-backup','--operation-id','legacy-backup','--actor-id','owner')
        path=paths(self.root,'legacy-backup')[0];record=json.loads(path.read_text());record['body']['actor_id']='changed';path.write_text(json.dumps(record))
        self.assertFalse(verify_store(self.root,full=True)['valid'])

    def test_readonly_missing_root_does_not_create_authority(self):
        root=self.base/'missing';self.cli('compact','--root',root)
        self.assertFalse((root/'format.json').exists());self.assertFalse((root/'events').exists());self.assertFalse((root/'store-v2').exists())
