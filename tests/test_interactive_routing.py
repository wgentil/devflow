import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_routed_native_runtime as native_fixtures
from workflow_lib.store import read_state,WorkflowError


class Bridge:
    def __init__(self, context):
        self.context=copy.deepcopy(context);self.spawns=[]
    def capabilities(self):return copy.deepcopy(self.context)
    def spawn(self,prepared):
        self.spawns.append(copy.deepcopy(prepared));return {'id':'worker'}
    def collect(self,handle):
        return {'status':'completed','observed':{'provider':'openai','model':'candidate','effort':'high'},
            'observation_source':'host-invocation-metadata','invocation_ref':'codex://interactive-test',
            'output':'bounded worker output'}


class InteractiveRoutingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=native_fixtures.RoutedNativeRuntimeTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.request={**self.fixture.request,'execution_path':'interactive-nonfork'}
        self.context={**copy.deepcopy(self.fixture.context),'account_key':'account',
            'controls':{'schema_version':1,'host_version':'1.2.3','source':'enclosing-host',
                        'supported':True,'account_key':'account','configuration_hash':'config',
                        'model_efforts':{'candidate':['medium','high']},'custom_agent':{},
                        'agent_defaults':{},'parent':{},'overrides':{}}}
    def test_unavailable_bridge_prepares_but_never_dispatches_or_mints_receipts(self):
        from workflow_lib.interactive_routing import prepare_delegation,dispatch_delegation
        before=read_state(self.root)['version']
        prepared=prepare_delegation(self.root,self.request)
        self.assertEqual(prepared['status'],'not-dispatched');self.assertFalse(prepared['dispatch'])
        self.assertEqual(dispatch_delegation(self.root,self.request,'none')['status'],'not-dispatched')
        self.assertEqual(read_state(self.root)['version'],before)
        self.assertFalse(read_state(self.root)['data']['runs']['run'].get('native_invocations'))
    def test_supported_bridge_receives_scoped_controls_and_exact_retry_spawns_once(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        bridge=Bridge(self.context)
        result=dispatch_delegation(self.root,self.request,'interactive-op',bridge)
        self.assertEqual(result['resolved']['effort'],'high')
        self.assertEqual(result['routing']['execution_path'],'interactive-nonfork')
        self.assertEqual(result['scope']['token'],'t')
        again=dispatch_delegation(self.root,self.request,'interactive-op',bridge)
        self.assertTrue(again['replayed']);self.assertEqual(len(bridge.spawns),1)
        worker=bridge.spawns[0]['worker_input']
        self.assertEqual((worker['configuration_text']+worker['prompt']).count('Fixture required behavior'),1)
    def test_codex_custom_agent_conflict_and_stale_bridge_never_spawn(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        context=copy.deepcopy(self.context);context['controls']['custom_agent']={'model_reasoning_effort':'medium'}
        bridge=Bridge(context)
        result=dispatch_delegation(self.root,self.request,'conflict',bridge)
        self.assertEqual(result['status'],'not-dispatched');self.assertFalse(bridge.spawns)
        bridge=Bridge(self.context);calls=0
        def changing():
            nonlocal calls
            calls+=1
            value=copy.deepcopy(self.context)
            if calls>1:value['controls']['configuration_hash']='changed'
            return value
        bridge.capabilities=changing
        result=dispatch_delegation(self.root,self.request,'stale',bridge)
        self.assertFalse(bridge.spawns);self.assertEqual(result['reason_code'],'ROUTING_CONFIGURATION_CHANGED')
    def test_forks_are_not_treated_as_nonfork_supported_controls(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        bridge=Bridge(self.context)
        result=dispatch_delegation(self.root,{**self.request,'execution_path':'interactive-fork'},'fork',bridge)
        self.assertEqual(result['status'],'not-dispatched');self.assertFalse(bridge.spawns)
    def test_cli_payload_cannot_supply_a_bridge_or_trusted_observation(self):
        request_file=self.root/'request.json'
        request_file.write_text(json.dumps({**self.request,'host_context':self.context,'observed':{'effort':'high'}}))
        result=subprocess.run([sys.executable,str(native_fixtures.ROOT/'skills/workflow/scripts/run.py'),
            'host','delegation-prepare','--root',str(self.root),'--file',str(request_file)],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout)
        self.assertEqual(value['status'],'not-dispatched');self.assertFalse(value['dispatch'])

    def test_claude_version_boundary_and_unknown_observation(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        from workflow_lib.store import transact
        state=read_state(self.root);state['data']['host_bindings']['b1']['host']='claude'
        transact(self.root,state['version'],'claude',{'kind':'fixture','payload':state['data']})
        context=copy.deepcopy(self.context);context['capabilities']['observe']=False
        context['controls']['host_version']='2.1.291'
        bridge=Bridge(context)
        self.assertEqual(dispatch_delegation(self.root,self.request,'old',bridge)['status'],'not-dispatched')
        self.assertFalse(bridge.spawns)
        bridge.context['controls']['host_version']='2.1.299'
        bridge.collect=lambda handle:{'status':'completed','observed':{'provider':'anthropic','model':'candidate','effort':None},
            'observation_source':'host-invocation-metadata','output':'bounded worker output'}
        result=dispatch_delegation(self.root,self.request,'claude',bridge)
        self.assertEqual(result['status'],'allow');self.assertIsNone(result['observed']['effort'])

    def test_partial_and_unknown_collection_never_claim_completed_work(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        bridge=Bridge(self.context)
        bridge.collect=lambda handle:{'status':'partial','observed':{'provider':'openai','model':'candidate','effort':'high'},
            'observation_source':'host-invocation-metadata','output':'partial'}
        result=dispatch_delegation(self.root,self.request,'partial',bridge)
        self.assertEqual(result['status'],'block');self.assertEqual(result['reason_code'],'WORKER_PARTIAL')

    def test_failed_collection_keeps_running_until_stopped_reconciliation(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        bridge=Bridge(self.context)
        def fail(handle):raise OSError('Connection lost; worker may still run')
        bridge.collect=fail
        result=dispatch_delegation(self.root,self.request,'lost',bridge)
        self.assertEqual(result['reason_code'],'INTERACTIVE_RECONCILE_REQUIRED')
        self.assertEqual(read_state(self.root)['data']['runs']['run']['native_invocations']['routed']['status'],'running')
        with self.assertRaises(WorkflowError):dispatch_delegation(self.root,self.request,'lost',bridge)
        self.assertEqual(len(bridge.spawns),1)

    def test_authorized_interactive_escalation_reuses_durable_lineage(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        bridge=Bridge(self.context)
        request={**self.request,'task':{**self.request['task'],'uncertainty':'resolved'}}
        bridge.collect=lambda handle:{'status':'partial','observed':{'provider':'openai','model':'candidate','effort':'medium'},
            'observation_source':'host-invocation-metadata','output':'partial'}
        first=dispatch_delegation(self.root,request,'first',bridge)
        metadata=first['routing']
        authorization={'approved':True,'actor_id':'human','lineage_id':metadata['lineage_id'],
            'task_hash':metadata['task_hash'],'policy_hash':metadata['policy_hash'],
            'configuration_hash':metadata['configuration_hash'],'host':'codex','stage':'implementation',
            'max_escalations':1,'eligible_routes':[{'model':'candidate','effort':'high'}]}
        bridge.collect=lambda handle:{'status':'completed','observed':{'provider':'openai','model':'candidate','effort':'high'},
            'observation_source':'host-invocation-metadata','output':'completed'}
        request={**request,'invocation_id':'escalated','predecessor_invocation_id':'routed',
            'escalation_authorization':authorization,'escalation_evidence':{'kind':'reasoning',
                'reason':'Unresolved diagnosis','evidence_refs':['verification:failed']}}
        result=dispatch_delegation(self.root,request,'second',bridge)
        self.assertEqual(result['status'],'allow');self.assertEqual(result['resolved']['effort'],'high')
        self.assertEqual(result['routing']['escalation_index'],1)
