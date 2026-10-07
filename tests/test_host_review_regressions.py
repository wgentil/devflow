import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from test_hosts import host_state, attachment
from workflow_lib.hosts import apply_host_event
from workflow_lib.store import transact, WorkflowError, HOST_CONTEXT
from workflow_lib.model_policy import check_model_receipt

class ReviewRegressions(unittest.TestCase):
    def test_wrong_root_locator_known_task_blocks(self):
        from workflow_lib.host_locators import write_locator, write_task_index
        from workflow_lib.host_hook import evaluate
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)/'project';project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True)
            root=Path(temp)/'control';wrong=Path(temp)/'wrong'
            state=host_state(str(project.resolve()));apply_host_event(state,'attach',attachment(str(project.resolve()),host='claude'))
            apply_host_event(state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'mapped','scope':'item','item_id':'W1','token':'t'})
            transact(root,0,'seed',{'kind':'fixture','payload':state});transact(wrong,0,'wrong',{'kind':'fixture','payload':{}})
            write_task_index(project,'claude','s1',root,['mapped']);write_locator(project,'claude','s1',wrong,'b1')
            self.assertEqual(evaluate(project,'s1','TaskCompleted','mapped')['status'],'block')
            self.assertEqual(evaluate(project,'s1','TaskCompleted','ordinary')['status'],'inactive')
    def test_detached_locator_cannot_hide_current_mapping(self):
        from workflow_lib.host_locators import write_locator, write_task_index
        from workflow_lib.host_hook import evaluate
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)/'project';project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True)
            root=Path(temp)/'control';state=host_state(str(project.resolve()))
            apply_host_event(state,'attach',attachment(str(project.resolve()),host='claude'))
            apply_host_event(state,'detach',{'binding_id':'b1','revision':1})
            apply_host_event(state,'attach',attachment(str(project.resolve()),host='claude',binding_id='b2'))
            apply_host_event(state,'task-bind',{'binding_id':'b2','revision':1,'task_id':'mapped','scope':'item','item_id':'W1','token':'t'})
            transact(root,0,'seed',{'kind':'fixture','payload':state});write_locator(project,'claude','s1',root,'b1');write_task_index(project,'claude','s1',root,['mapped'])
            self.assertEqual(evaluate(project,'s1','TaskCompleted','mapped')['status'],'block')
    def test_unrelated_receipt_cannot_map_implementation(self):
        state=host_state();apply_host_event(state,'attach',attachment())
        apply_host_event(state,'model-receipt',{'binding_id':'b1','revision':1,'receipt':{'invocation_id':'old','stage':'planning','status':'allow','mode':'advisory'}})
        with self.assertRaises(WorkflowError):apply_host_event(state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t','invocation_id':'old'})
    def test_advisory_does_not_erase_explicit_decision_block(self):
        for reason in ('PIN_UNAVAILABLE','COST_UNKNOWN'):
            self.assertEqual(check_model_receipt({'status':'block','reason_code':reason},'advisory')['status'],'block')
    def test_stage_preference_preserves_global_constraints(self):
        from commands.host import _resolve_model
        state=host_state();binding=apply_host_event(state,'attach',attachment())
        apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'max_cost':1,'allowed_models':['permitted']})
        apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'stage':'planning','mode':'advisory'})
        result=_resolve_model(state,binding,'planning')
        self.assertEqual(result['reason_code'],'COST_UNKNOWN');self.assertEqual(result['override']['allowed_models'],['permitted'])
    def test_explicit_detached_upgrade_resume(self):
        state=host_state();apply_host_event(state,'attach',attachment());apply_host_event(state,'detach',{'binding_id':'b1','revision':1})
        release=copy.deepcopy(attachment()['release']);release['fingerprint']='new';release['release_id']='new';release['version']='0.2.1'
        result=apply_host_event(state,'attach',attachment(release=release,resume=True,revision=2))
        self.assertEqual(result['revision'],3);self.assertEqual(len(result['release_history']),2);self.assertEqual(state['runs']['run']['active_attempt']['token'],'t')
        with self.assertRaises(WorkflowError):apply_host_event(state,'attach',attachment(release=release,resume=True,revision=2))
    def test_detach_cli_exact_retry_after_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);state=host_state();apply_host_event(state,'attach',attachment());transact(root,0,'seed',{'kind':'fixture','payload':state})
            file=root/'detach.json';file.write_text(json.dumps({'binding_id':'b1','revision':1}))
            argv=[sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),'host','detach','--root',str(root),'--file',str(file),'--operation-id','detach']
            first=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(first.returncode,0,first.stdout+first.stderr)
            retry=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(retry.returncode,0,retry.stdout+retry.stderr);self.assertTrue(json.loads(retry.stdout)['replayed'])
            file.write_text(json.dumps({'binding_id':'b1','revision':2}))
            conflict=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(json.loads(conflict.stdout)['error'],'OPERATION_CONFLICT')
    def test_reviewer_cannot_record_other_item_or_role(self):
        state=host_state();run=state['runs']['run'];run['items']['W2']={'status':'pending','attempts':[]};run['plan']['work_items'].append({'id':'W2','kind':'code','requirement_ids':['R1']});run['review_packages']={'pkg':{'role':'item','package_hash':'pkg'}}
        apply_host_event(state,'attach',attachment(binding_id='reviewer',role='item-reviewer',actor_id='reviewer',item_id='W1',package_hash='pkg'))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);transact(root,0,'seed',{'kind':'fixture','payload':state});guard=HOST_CONTEXT.set({'binding_id':'reviewer','revision':1})
            try:
                for role,item in (('item','W2'),('branch','W1')):
                    with self.assertRaises(WorkflowError):transact(root,1,role,{'kind':'review.recorded','payload':{'run_id':'run','review':{'role':role,'item_id':item,'actor_id':'reviewer','package_hash':'pkg','verdict':'pass','findings':[],'review_id':role,'invocation_ref':'actual','fresh':True}}})
            finally:HOST_CONTEXT.reset(guard)
    def test_completion_without_receipt_still_enforces_budget(self):
        from test_host_completion import CompletionTests
        from workflow_lib.host_completion import check_completion
        fixture=CompletionTests();fixture.setUp();fixture.green()
        apply_host_event(fixture.state,'model-override',{'binding_id':'b1','revision':1,'max_cost':1})
        self.assertEqual(check_completion(fixture.state,fixture.binding,'task',False)['reason_code'],'COST_UNKNOWN')
    def test_receipt_captures_scope_and_only_its_work_keeps_historical_mode(self):
        from test_host_completion import CompletionTests
        from workflow_lib.host_completion import check_completion
        from workflow_lib.journal_domains import digest
        fixture=CompletionTests();fixture.setUp();state=fixture.state
        receipt=apply_host_event(state,'model-receipt',{'binding_id':'b1','revision':1,'receipt':{'invocation_id':'work','stage':'implementation','mode':'advisory','status':'allow','scope':{'actor_id':'fake'},'policy_revision':999}})
        self.assertEqual(receipt['scope']['actor_id'],'a1');self.assertEqual(receipt['scope']['token'],'t');self.assertEqual(receipt['policy_revision'],0)
        apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'mode':'strict'})
        old=state['host_tasks']['codex:s1:task']
        apply_host_event(state,'task-bind',{**old,'invocation_id':'work','replace':True,'previous_mapping_hash':digest(old)})
        fixture.green();self.assertEqual(check_completion(state,fixture.binding,'task',False)['status'],'allow')
        state['runs']['run']['model_receipts']['work']['scope']['token']='other'
        self.assertEqual(check_completion(state,fixture.binding,'task',False)['reason_code'],'INVOCATION_SCOPE_MISMATCH')
    def test_interruption_cannot_use_another_binding_invocation(self):
        state=host_state();apply_host_event(state,'attach',attachment())
        apply_host_event(state,'model-receipt',{'binding_id':'b1','revision':1,'receipt':{'invocation_id':'work','stage':'implementation','mode':'advisory','status':'allow'}})
        apply_host_event(state,'detach',{'binding_id':'b1','revision':1});apply_host_event(state,'attach',attachment(binding_id='b2',session_id='s2',actor_id='a2'))
        with self.assertRaises(WorkflowError):apply_host_event(state,'model-interrupt',{'binding_id':'b2','revision':1,'invocation':{'invocation_id':'work'},'error_kind':'network'})
    def test_preference_removal_is_explicit_and_stage_scoped(self):
        from workflow_lib.model_policy import effective_preferences
        state=host_state();apply_host_event(state,'attach',attachment())
        apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'max_cost':1,'allowed_models':['permitted']})
        apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'stage':'planning','clear':['max_cost']})
        run=state['runs']['run'];self.assertNotIn('max_cost',effective_preferences(run,'planning'));self.assertEqual(effective_preferences(run,'implementation')['max_cost'],1)
    def test_resume_cannot_transfer_or_waive_protocol(self):
        state=host_state();apply_host_event(state,'attach',attachment());apply_host_event(state,'detach',{'binding_id':'b1','revision':1})
        with self.assertRaises(WorkflowError):apply_host_event(state,'attach',attachment(resume=True,revision=2,actor_id='different'))
        release=copy.deepcopy(attachment()['release']);release['host_protocol_version']=2
        with self.assertRaises(WorkflowError):apply_host_event(state,'attach',attachment(resume=True,revision=2,release=release))
    def test_receipt_resolution_policy_race_rejected(self):
        state=host_state();apply_host_event(state,'attach',attachment());apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'mode':'strict'})
        with self.assertRaises(WorkflowError):apply_host_event(state,'model-receipt',{'binding_id':'b1','revision':1,'resolution_policy_revision':0,'receipt':{'invocation_id':'stale','stage':'implementation','status':'allow','mode':'advisory'}})
    def test_cli_exact_retry_after_refresh_is_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);project=root/'project';project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True)
            state=host_state(str(project.resolve()));transact(root,0,'seed',{'kind':'fixture','payload':state})
            release=root/'release.json';release.write_text(json.dumps(attachment()['release']))
            file=root/'attach.json';request=attachment(str(project.resolve()));request.pop('release');file.write_text(json.dumps(request))
            argv=[sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),'host','attach','--root',str(root),'--file',str(file),'--loaded-release',str(release),'--operation-id','attach']
            result=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout)
            refresh=root/'refresh.json';refresh.write_text(json.dumps({**request,'refresh':True,'revision':1}))
            result=subprocess.run(argv[:argv.index('--file')]+['--file',str(refresh),'--loaded-release',str(release),'--operation-id','refresh'],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout)
            retry=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(retry.returncode,0,retry.stdout);self.assertTrue(json.loads(retry.stdout)['replayed'])
            from workflow_lib.store import read_state
            self.assertEqual(read_state(root)['data']['host_bindings']['b1']['revision'],2)
    def test_cli_compatible_detached_resume_retains_token(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);project=root/'project';project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True)
            state=host_state(str(project.resolve()));old=copy.deepcopy(attachment()['release']);old['fingerprint']='old';old['release_id']='old'
            apply_host_event(state,'attach',attachment(str(project.resolve()),release=old));apply_host_event(state,'detach',{'binding_id':'b1','revision':1});transact(root,0,'seed',{'kind':'fixture','payload':state})
            release=root/'release.json';release.write_text(json.dumps(attachment()['release']));file=root/'resume.json';request=attachment(str(project.resolve()),resume=True,revision=2);request.pop('release');file.write_text(json.dumps(request))
            argv=[sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),'host','attach','--root',str(root),'--file',str(file),'--loaded-release',str(release),'--operation-id','resume']
            result=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout);self.assertEqual(json.loads(result.stdout)['revision'],3)
            from workflow_lib.store import read_state
            self.assertEqual(read_state(root)['data']['runs']['run']['active_attempt']['token'],'t')
            self.assertEqual(len(read_state(root)['data']['host_bindings']['b1']['release_history']),2)
    def test_deterministic_delivery_does_not_need_model_receipt(self):
        from test_host_completion import CompletionTests
        from workflow_lib.host_completion import check_completion
        fixture=CompletionTests();fixture.setUp();apply_host_event(fixture.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'delivery','scope':'delivery'})
        apply_host_event(fixture.state,'model-override',{'binding_id':'b1','revision':1,'mode':'strict','max_cost':1})
        fixture.state['runs']['run'].update(status='delivered',delivery={'actual_result':{'status':'merged'},'manifest_hash':'hash'})
        self.assertEqual(check_completion(fixture.state,fixture.binding,'delivery',False)['status'],'allow')
