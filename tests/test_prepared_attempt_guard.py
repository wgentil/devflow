import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from large_context_fixtures import make_context_project
from workflow_lib.store import read_state,transact,WorkflowError
from workflow_lib.runs import issue_attempt
from workflow_lib.context_preparation import prepare_context
from workflow_lib import context_preparation as preparation

class PreparedAttemptGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve();self.f=make_context_project(self.base/'project');self.root=self.f['root']
    def proposal(self,state=None,envelope=None):
        state=state or read_state(self.root);updated=issue_attempt(state['data']['runs']['current'],'W1')
        p=prepare_context(self.root,updated,envelope or {'run_id':'current'},['W1'],stage='implementation',state=state)
        event={'kind':'run.attempt.issued','payload':{'run_id':'current','attempt':updated['active_attempt']}}
        return p,event
    def commit(self,p,event,operation='guarded'):
        return preparation.commit_prepared_attempt(self.root,p,operation,event)
    def test_new_token_uses_prepared_version(self):
        p,event=self.proposal();result=self.commit(p,event)
        self.assertEqual(result['event']['sequence'],p.journal_version+1)
        self.assertEqual(read_state(self.root)['data']['runs']['current']['active_attempt']['token'],p.scope['attempt_id'])
    def test_journal_change_after_worker_rejects_token(self):
        p,event=self.proposal();s=read_state(self.root);transact(self.root,s['version'],'other',{'kind':'fixture','payload':{'other':True}})
        with self.assertRaises(WorkflowError) as caught:self.commit(p,event)
        self.assertEqual(caught.exception.code,'CONTEXT_PREPARATION_STALE');self.assertIsNone(read_state(self.root)['data']['runs']['current']['active_attempt'])
    def test_filesystem_drift_after_worker_rejects_token(self):
        p,event=self.proposal();pair=self.f['state']['data']['spec_pair'];(self.f['repo']/pair['markdown_path']).write_text('unapproved drift',encoding='utf-8')
        with self.assertRaises(WorkflowError) as caught:self.commit(p,event)
        self.assertEqual(caught.exception.details['phase'],'commit')
        self.assertNotIn('guarded',read_state(self.root)['operations'])
    def test_relocation_or_host_revision_change_rejects_token(self):
        p,event=self.proposal();new=self.base/'relocated';self.f['repo'].rename(new);self.f['repo'].symlink_to(new,target_is_directory=True)
        with self.assertRaises(WorkflowError):self.commit(p,event)
        self.f['repo'].unlink();new.rename(self.f['repo'])
        from workflow_lib.hosts import apply_host_event
        from test_hosts import attachment
        state=read_state(self.root);data=copy.deepcopy(state['data']);apply_host_event(data,'attach',attachment(str(self.f['repo']),run_id='current'))
        transact(self.root,state['version'],'host',{'kind':'fixture','payload':data})
        p,event=self.proposal(envelope={'run_id':'current','binding_id':'b1','revision':1})
        state=read_state(self.root);bindings=copy.deepcopy(state['data']['host_bindings']);bindings['b1']['revision']=2
        transact(self.root,state['version'],'host-refresh',{'kind':'fixture','payload':{'host_bindings':bindings}})
        with self.assertRaises(WorkflowError):self.commit(p,event)
        self.assertIsNone(read_state(self.root)['data']['runs']['current']['active_attempt'])
    def test_failed_prepare_does_not_consume_operation_id(self):
        p,event=self.proposal();path=self.f['repo']/self.f['state']['data']['spec_pair']['markdown_path'];raw=path.read_bytes();path.write_text('drift',encoding='utf-8')
        with self.assertRaises(WorkflowError):self.commit(p,event,'retryable')
        self.assertNotIn('retryable',read_state(self.root)['operations']);path.write_bytes(raw)
        fresh,event=self.proposal();self.assertFalse(self.commit(fresh,event,'retryable')['replayed'])
    def test_exact_retry_uses_committed_token(self):
        p,event=self.proposal();first=self.commit(p,event)
        # An exact historical retry must survive source drift without executing its guard.
        (self.f['repo']/self.f['state']['data']['spec_pair']['markdown_path']).write_text('later drift',encoding='utf-8')
        again=self.commit(p,event);self.assertTrue(again['replayed']);self.assertEqual(again['event'],first['event'])
        self.assertEqual(len(again['state']['data']['runs']['current']['items']['W1']['attempts']),1)
    def test_reverification_proposal_is_bound(self):
        from workflow_lib.reverification import begin_reverification
        state=read_state(self.root);runs=copy.deepcopy(state['data']['runs']);run=runs['current'];run['state_version']=1
        run['items']['W1']={'status':'complete','attempts':[{'token':'1'*48,'item_id':'W1','state_version':1,'status':'result_recorded','result':{'outcome':'passed','offline_fixture':True}}]}
        transact(self.root,state['version'],'historical-fixture',{'kind':'fixture','payload':{'runs':runs}})
        state=read_state(self.root);updated=begin_reverification(state['data']['runs']['current'],'W1')
        p=prepare_context(self.root,updated,{'run_id':'current'},['W1'],stage='implementation',state=state)
        event={'kind':'run.reverification.started','payload':{'run_id':'current','attempt':updated['active_attempt'],'prior_token':'1'*48}}
        wrong=copy.deepcopy(event);wrong['payload']['attempt']['token']='2'*48
        with self.assertRaises(WorkflowError):self.commit(p,wrong)
        self.assertEqual(self.commit(p,event)['state']['data']['runs']['current']['active_attempt']['mode'],'reverify')
    def test_source_change_during_preflight_cannot_become_approved_binding(self):
        original=preparation.preflight_inputs
        def changed(*args,**kwargs):
            result=original(*args,**kwargs);(self.f['repo']/self.f['state']['data']['spec_pair']['markdown_path']).write_text('changed after validation',encoding='utf-8');return result
        with patch('workflow_lib.context_preparation.preflight_inputs',side_effect=changed):
            with self.assertRaises(WorkflowError):self.proposal()
    def test_caller_replay_time_is_reported(self):
        with patch('workflow_lib.context_preparation.time.perf_counter',side_effect=[100,106]):state=preparation.read_context_state(self.root)
        p,_=self.proposal(state=state);self.assertGreaterEqual(p.preflight_ms,6000)

    def cli(self):
        import importlib.util,io,json
        from contextlib import redirect_stdout
        path=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        spec=importlib.util.spec_from_file_location('guard_entry',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        output=io.StringIO()
        with redirect_stdout(output):code=module.main(['run','next','--root',str(self.root),'--run-id','current','--item','W1','--operation-id','cli-guard'])
        return code,json.loads(output.getvalue())
    def test_cli_uses_guard_after_actual_context_composition(self):
        from workflow_lib.lifecycle_hooks import prepared_context
        def drift(*args,**kwargs):
            result=prepared_context(*args,**kwargs)
            (self.f['repo']/self.f['state']['data']['spec_pair']['markdown_path']).write_text('changed after worker',encoding='utf-8')
            return result
        with patch('workflow_lib.lifecycle_hooks.prepared_context',side_effect=drift):code,response=self.cli()
        self.assertEqual(code,2);self.assertEqual(response['error'],'CONTEXT_SOURCE_CHANGED')
        self.assertIsNone(read_state(self.root)['data']['runs']['current']['active_attempt'])
    def test_cli_next_replays_only_initial_and_locked_commit(self):
        from workflow_lib.store import _read_journal
        calls=[]
        def counted(root):calls.append(root);return _read_journal(root)
        with patch('workflow_lib.store._read_journal',side_effect=counted):code,response=self.cli()
        self.assertEqual(code,0,response);self.assertTrue(response['attempt_id']);self.assertEqual(len(calls),2)

    def test_new_governing_manifest_after_worker_blocks_operation(self):
        p,event=self.proposal()
        (self.f['repo']/'docs/devflow-context.json').write_text('{"schema_version":1,"documents":[]}',encoding='utf-8')
        with self.assertRaises(WorkflowError):self.commit(p,event)
        self.assertIsNone(read_state(self.root)['data']['runs']['current']['active_attempt'])
    def test_documentation_policy_change_after_worker_blocks_operation(self):
        import shutil
        from workflow_lib.task_views import PACKAGE_ROOT
        copied=self.base/'installed';copied.mkdir()
        for part in ('definitions','docs','skills'):shutil.copytree(PACKAGE_ROOT/part,copied/part,ignore=shutil.ignore_patterns('__pycache__'))
        with patch('workflow_lib.task_views.PACKAGE_ROOT',copied):
            p,event=self.proposal()
            policy=copied/'definitions/documentation.json';policy.write_bytes(policy.read_bytes()+b'\n')
            with self.assertRaises(WorkflowError):self.commit(p,event)
        self.assertNotIn('guarded',read_state(self.root)['operations'])
