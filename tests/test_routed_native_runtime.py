import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from test_hosts import host_state,attachment
from test_task_routing import task
from workflow_lib.hosts import apply_host_event,invocation_scope
from workflow_lib.native_runtime import invoke
from workflow_lib.store import transact,read_state,WorkflowError


class RoutedNativeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.state=host_state();apply_host_event(self.state,'attach',attachment())
        apply_host_event(self.state,'model-override',{'binding_id':'b1','revision':1,'pin':'candidate','allow_unvalidated':True})
        transact(self.root,0,'seed',{'kind':'fixture','payload':self.state})
        self.context={'capabilities':{'configure':True,'observe':True,'models':['candidate'],'efforts':['medium','high'],
            'model_efforts':{'candidate':['medium','high']}},'discovery':{'models':{'candidate':'available'},'host_version':'1.2.3'}}
        self.backend=Mock();self.backend.identity.return_value={'account_key':'account','cacheable':True}
        self.backend.discover.side_effect=lambda:copy.deepcopy(self.context)
        self.backend.configure.side_effect=lambda selected,*args:{'observed':copy.deepcopy(selected),'observation_source':'host-effective-configuration'}
        self.backend.invoke.side_effect=lambda selected,*args:{'status':'completed','observed':copy.deepcopy(selected),
            'observation_source':'host-effective-configuration','invocation_ref':'codex://test','output':self.completed_output()}
        self.request={'binding_id':'b1','revision':1,'invocation_id':'routed','stage':'implementation',
            'prompt':'Perform scoped work','task':task(actor_id='a1',uncertainty='material')}
    def completed_output(self):
        state=read_state(self.root)['data'];binding=state['host_bindings']['b1']
        scope=invocation_scope(binding,state['runs']['run'],'implementation',{})
        return json.dumps({'status':'completed','scope':scope,'completed_scope':['W1'],
                           'evidence_refs':['fixture:run:W1:t'],'unresolved_facts':[]})
    def call(self,request=None):
        with patch('workflow_lib.native_runtime.CodexBackend',return_value=self.backend):
            return invoke(self.root,request or self.request,'routed-op')
    def test_enforced_native_dispatch_requires_known_cost_before_worker(self):
        state=read_state(self.root);run=state['data']['runs']['run']
        run['enforcement']={'protocol':'devflow.python-enforcement/v1', 'policy_version':1}
        run['effect_policy']={'max_attempts':1,'max_estimated_cost':1,'max_elapsed_ms':100000}
        transact(self.root,state['version'],'enforce',{'kind':'fixture','payload':state['data']})
        with self.assertRaises(WorkflowError) as caught:self.call()
        self.assertEqual(caught.exception.code,'PRICE_UNKNOWN')
        self.backend.invoke.assert_not_called()

    def enable_enforcement_fixture(self, limit=1):
        import subprocess
        repo=Path(self.temp.name)/'owned-repo';repo.mkdir()
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'source.py').write_text('value=1')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','base'],cwd=repo,check=True)
        state=read_state(self.root);run=state['data']['runs']['run']
        run['enforcement']={'protocol':'devflow.python-enforcement/v1', 'policy_version':1};run['effect_policy']={'max_attempts':limit,'max_estimated_cost':limit,'max_elapsed_ms':100000}
        run['repositories']={'repo':{'location':str(repo)}};state['data']['repositories']=copy.deepcopy(run['repositories'])
        state['data']['host_bindings']['b1']['project_dir']=str(repo)
        transact(self.root,state['version'],'enforce-real-fixture',{'kind':'fixture','payload':state['data']})

    def test_enforced_native_timeout_cannot_exceed_remaining_elapsed_budget(self):
        self.enable_enforcement_fixture()
        self.call({**self.request, 'estimated_cost': 1})
        timeout = self.backend.invoke.call_args.args[4]
        self.assertGreater(timeout, 0)
        self.assertLessEqual(timeout, 100)

    def test_reviewer_reservation_is_limited_to_its_attached_package(self):
        from workflow_lib.effect_dispatch import reserve_dispatch
        from workflow_lib.store import HOST_CONTEXT
        self.enable_enforcement_fixture(limit=3)
        state=read_state(self.root)
        state['data']['runs']['run']['review_packages']={'pkg':{'role':'item','package_hash':'pkg'}}
        state['data']['runs']['run']['clarifications']={'q':{'id':'q','version':1,'status':'pending','scope':['W1']}}
        apply_host_event(state['data'],'attach',attachment(binding_id='review',session_id='rs',
            actor_id='reviewer',role='item-reviewer',item_id='W1',package_hash='pkg',
            project_dir=state['data']['host_bindings']['b1']['project_dir']))
        transact(self.root,state['version'],'attach-review-fixture',{'kind':'fixture','payload':state['data']})
        binding=state['data']['host_bindings']['review']
        token=HOST_CONTEXT.set({'binding_id':'review','revision':binding['revision'],'release':binding['release']})
        try:
            receipt=reserve_dispatch(self.root,'run','review-call','review:item-reviewer:pkg',1,
                'review-claim',{'item_id':'W1'},owner_binding=binding)
            self.assertEqual(receipt['owner_binding']['actor_id'],'reviewer')
            with self.assertRaises(WorkflowError):
                reserve_dispatch(self.root,'run','foreign','implementation',1,'foreign-claim',{},owner_binding=binding)
        finally:HOST_CONTEXT.reset(token)

    def test_enforced_native_completion_retains_claim_lineage(self):
        self.enable_enforcement_fixture()
        request={**self.request,'estimated_cost':1}
        result=self.call(request)
        self.assertEqual(result['status'],'allow')
        run=read_state(self.root)['data']['runs']['run']
        self.assertEqual(run['effects']['routed']['status'],'completed')
        self.assertEqual(run['effects']['routed']['estimated_cost'],1)
        self.assertTrue(self.call(request)['replayed'])
        self.backend.invoke.assert_called_once()

    def test_finished_transport_with_partial_work_does_not_leave_uncertain_worker(self):
        self.enable_enforcement_fixture(limit=3)
        self.backend.invoke.side_effect=lambda selected,*args:{'status':'completed',
            'observed':copy.deepcopy(selected),'observation_source':'host-effective-configuration',
            'invocation_ref':'codex://partial','output':'{}'}
        result=self.call({**self.request,'estimated_cost':1})
        self.assertEqual(result['status'],'block')
        run=read_state(self.root)['data']['runs']['run']
        self.assertEqual(run['effects']['routed']['status'],'completed')
        self.assertEqual(result['worker_outcome']['status'],'partial')

    def test_uncertain_native_worker_blocks_replacement_with_budget_remaining(self):
        from workflow_lib.native_models import NativeError
        self.enable_enforcement_fixture(limit=3)
        self.backend.invoke.side_effect=NativeError('unavailable')
        result=self.call({**self.request,'estimated_cost':1})
        self.assertEqual(result['status'],'block')
        run=read_state(self.root)['data']['runs']['run']
        self.assertEqual(run['effects']['routed']['status'],'uncertain')
        with patch('workflow_lib.native_runtime.CodexBackend',return_value=self.backend):
            with self.assertRaises(WorkflowError) as caught:
                invoke(self.root,{**self.request,'invocation_id':'replacement','estimated_cost':1},'replacement-op')
        self.assertEqual(caught.exception.code,'EFFECT_BLOCKED')
        self.backend.invoke.assert_called_once()

    def test_crash_after_launch_keeps_uncertain_claim_and_history(self):
        self.enable_enforcement_fixture(limit=3)
        self.backend.invoke.side_effect=RuntimeError('injected after launch')
        with self.assertRaises(RuntimeError):self.call({**self.request,'estimated_cost':1})
        run=read_state(self.root)['data']['runs']['run']
        self.assertEqual(run['effects']['routed']['status'],'uncertain')
        self.assertEqual([row['to'] for row in run['effects']['routed']['history']],['launching','uncertain'])
        self.assertEqual(run['effects']['routed']['estimated_cost'],1)

    def test_legacy_opaque_enforcement_metadata_is_not_adoption(self):
        state=read_state(self.root)
        state['data']['runs']['run']['enforcement']=None
        transact(self.root,state['version'],'opaque-legacy',{'kind':'fixture','payload':state['data']})
        self.assertEqual(self.call()['status'],'allow')

    def test_recorded_user_answer_is_in_required_worker_context(self):
        from workflow_lib.enforcement_live import source_observation
        self.enable_enforcement_fixture()
        state=read_state(self.root);run=state['data']['runs']['run']
        source=source_observation(run)['source_identity'];spec_hash=run['plan']['spec_hash']
        transact(self.root,state['version'],'question',{'kind':'domain.enforcement.question','payload':{'request':{'run_id':'run','record':{
            'id':'q','text':'Which retention window applies?','scope':['W1'],'source_identity':source,'spec_hash':spec_hash}}}})
        state=read_state(self.root)
        transact(self.root,state['version'],'answer',{'kind':'domain.enforcement.answer','payload':{'request':{'run_id':'run','record':{
            'id':'q','question_version':1,'answer':'Thirty days.','actor_id':'fixture-user','material':False,'spec_hash':spec_hash,
            'provenance':{'kind':'user-message','ref':'fixture-real-message'}}}}})
        self.assertEqual(self.call({**self.request,'estimated_cost':1})['status'],'allow')
        prompt=self.backend.invoke.call_args.args[1]
        self.assertEqual(prompt.count('Thirty days.'),1)
        self.assertIn('fixture-real-message',prompt)

    def test_task_specific_effort_reaches_launch_and_retry_is_exact(self):
        result=self.call()
        self.assertEqual(result['resolved']['effort'],'high')
        self.assertEqual(result['observed']['effort'],'high')
        self.assertEqual(result['routing']['task_facts']['task_id'],'T1')
        self.assertEqual(self.backend.configure.call_args.args[0]['effort'],'high')
        self.assertTrue(self.call()['replayed']);self.backend.invoke.assert_called_once()
        with self.assertRaises(WorkflowError):self.call({**self.request,'task':task(actor_id='a1')})
    def test_task_scope_mismatch_cannot_launch(self):
        with self.assertRaises(WorkflowError):
            self.call({**self.request,'task':task(actor_id='other')})
        self.backend.invoke.assert_not_called()
    def test_configuration_race_blocks_before_worker_effects(self):
        old=copy.deepcopy(self.context);new=copy.deepcopy(self.context);new['discovery']['host_version']='1.2.4'
        self.backend.discover.side_effect=[old,new]
        result=self.call()
        self.assertEqual(result['status'],'block')
        self.assertEqual(result['reason_code'],'ROUTING_CONFIGURATION_CHANGED')
        self.backend.invoke.assert_not_called()
    def test_effective_substitution_is_rejected_before_codex_work(self):
        self.backend.configure.side_effect=lambda selected,*args:{'observed':{**selected,'effort':'low'},'observation_source':'host-effective-configuration'}
        result=self.call()
        self.assertEqual(result['reason_code'],'MODEL_SUBSTITUTED');self.backend.invoke.assert_not_called()
    def test_strict_unvalidated_or_empty_allowlist_never_launches(self):
        state=read_state(self.root)
        apply_host_event(state['data'],'model-override',{'binding_id':'b1','revision':1,'mode':'strict'})
        transact(self.root,state['version'],'strict',{'kind':'fixture','payload':state['data']})
        self.assertEqual(self.call()['status'],'block');self.backend.invoke.assert_not_called()

    def test_claude_unknown_effort_is_not_promoted_to_observed(self):
        state=read_state(self.root)
        state['data']['host_bindings']['b1']['host']='claude'
        transact(self.root,state['version'],'claude-seed',{'kind':'fixture','payload':state['data']})
        self.context['capabilities']['observe']=False
        self.context['discovery']['host_version']='2.1.299'
        self.backend.invoke.side_effect=lambda selected,*args:{'status':'completed',
            'observed':{'provider':'anthropic','model':'candidate','effort':None},
            'observation_source':'host-invocation-metadata','output':self.completed_output()}
        with patch('workflow_lib.native_runtime.ClaudeBackend',return_value=self.backend),patch.dict('os.environ',{key:value for key,value in os.environ.items() if key not in {'CLAUDE_CODE_EFFORT_LEVEL','CLAUDE_CODE_SUBAGENT_MODEL','CLAUDE_CODE_SUBAGENT_MODEL_FORCE'}},clear=True):
            result=invoke(self.root,self.request,'claude-task')
        self.assertEqual(result['status'],'allow')
        self.assertEqual(result['resolved']['effort'],'high')
        self.assertIsNone(result['observed']['effort'])
        self.assertFalse(result['effective_identity_available'])

    def test_authorized_escalation_uses_new_invocation_without_another_permission(self):
        from workflow_lib.native_models import NativeError
        facts=task(actor_id='a1')
        original={**self.request,'task':facts}
        self.backend.invoke.side_effect=NativeError('unavailable')
        first=self.call(original)
        self.assertEqual(first['status'],'block')
        self.backend.invoke.side_effect=lambda selected,*args:{'status':'completed','observed':copy.deepcopy(selected),
            'observation_source':'host-effective-configuration','output':self.completed_output()}
        metadata=first['routing']
        authorization={'approved':True,'actor_id':'human','lineage_id':metadata['lineage_id'],
            'task_hash':metadata['task_hash'],'policy_hash':metadata['policy_hash'],
            'configuration_hash':metadata['configuration_hash'],'host':'codex','stage':'implementation',
            'max_escalations':1,'eligible_routes':[{'model':'candidate','effort':'high'}]}
        request={**original,'invocation_id':'escalated','predecessor_invocation_id':'routed',
            'escalation_evidence':{'kind':'reasoning','reason':'Unresolved diagnosis','evidence_refs':['verification:failed']},
            'escalation_authorization':authorization}
        with patch('workflow_lib.native_runtime.CodexBackend',return_value=self.backend):
            result=invoke(self.root,request,'escalated-op')
        self.assertEqual(result['status'],'allow')
        self.assertEqual(result['resolved']['effort'],'high')
        self.assertEqual(result['routing']['escalation_index'],1)
        state=read_state(self.root)['data']['runs']['run']
        self.assertEqual(state['routing_lineages'][metadata['lineage_id']]['count'],1)

    def test_fresh_model_revision_availability_or_observation_invalidates_dispatch(self):
        from test_model_policy import ReleasedMappingTests
        validated=ReleasedMappingTests();validated.setUp()
        policy=copy.deepcopy(validated.policy);policy['stages']['implementation']='deep-reasoning'
        old={'capabilities':validated.cap,'discovery':validated.discovery}
        for change in ('revision','availability','observation'):
            fixture=RoutedNativeRuntimeTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
            state=read_state(fixture.root);state['data']['runs']['run']['model_overrides']=[]
            apply_host_event(state['data'],'model-override',{'binding_id':'b1','revision':1,'mode':'strict'})
            transact(fixture.root,state['version'],'validated',{'kind':'fixture','payload':state['data']})
            fresh=copy.deepcopy(old)
            if change=='revision':fresh['discovery']['model_revisions']['model']='rev2'
            elif change=='availability':fresh['discovery']['models']['model']='retired'
            else:fresh['capabilities']['observe']=False
            fixture.backend.discover.side_effect=[copy.deepcopy(old),fresh]
            with self.subTest(change=change),patch('workflow_lib.native_runtime.policy',return_value=policy):
                result=fixture.call({**fixture.request,'invocation_id':'drift-'+change})
                self.assertEqual(result['status'],'block')
                fixture.backend.configure.assert_not_called();fixture.backend.invoke.assert_not_called()

    def test_network_retry_after_escalation_retains_route_and_count(self):
        from workflow_lib.native_models import NativeError
        original={**self.request,'task':task(actor_id='a1')}
        self.backend.invoke.side_effect=NativeError('unavailable')
        first=self.call(original);metadata=first['routing']
        auth={'approved':True,'actor_id':'human','lineage_id':metadata['lineage_id'],
            'task_hash':metadata['task_hash'],'policy_hash':metadata['policy_hash'],
            'configuration_hash':metadata['configuration_hash'],'host':'codex','stage':'implementation',
            'max_escalations':1,'eligible_routes':[{'model':'candidate','effort':'high'}]}
        self.backend.invoke.side_effect=NativeError('network')
        escalated={**original,'invocation_id':'escalated','predecessor_invocation_id':'routed',
            'escalation_evidence':{'kind':'reasoning','reason':'Unresolved diagnosis','evidence_refs':['verification:failed']},
            'escalation_authorization':auth}
        with patch('workflow_lib.native_runtime.CodexBackend',return_value=self.backend):
            second=invoke(self.root,escalated,'escalate-network')
            self.assertEqual(second['resolved']['effort'],'high')
            self.backend.invoke.side_effect=lambda selected,*args:{'status':'completed','observed':copy.deepcopy(selected),
                'observation_source':'host-effective-configuration','output':self.completed_output()}
            retry={**original,'invocation_id':'retry','replacement_of':'escalated'}
            result=invoke(self.root,retry,'retry-network')
        self.assertEqual(result['status'],'allow');self.assertEqual(result['resolved']['effort'],'high')
        run=read_state(self.root)['data']['runs']['run']
        self.assertEqual(run['routing_lineages'][metadata['lineage_id']]['count'],1)
        self.assertEqual(run['native_invocations']['retry']['retry_count'],2)
        self.assertEqual(run['native_invocations']['retry']['decision']['routing']['retry_of'],'escalated')
        from workflow_lib.routing_evaluation import routing_statistics
        stats=routing_statistics(read_state(self.root)['data'],{'run_id':'run'})
        self.assertEqual(stats['escalations'],1);self.assertEqual(stats['retries'],1)
