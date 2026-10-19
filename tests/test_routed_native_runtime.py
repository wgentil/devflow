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
