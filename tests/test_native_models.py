import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from test_hosts import host_state, attachment
from workflow_lib.hosts import apply_host_event
from workflow_lib.store import WorkflowError, read_state, transact

class NativeModelTests(unittest.TestCase):
    def backend(self):
        from workflow_lib.native_models import CodexBackend
        return CodexBackend
    def test_codex_inventory_pagination_efforts_and_private_account_stamp(self):
        Backend=self.backend()
        from unittest.mock import Mock
        rpc=Mock();rpc.request.side_effect=[{'account':{'type':'chatgpt','email':'private@example.test','planType':'pro'}},{'data':[{'model':'candidate','supportedReasoningEfforts':[{'reasoningEffort':'high'}]}],'nextCursor':'more'},{'data':[{'model':'other','supportedReasoningEfforts':[{'reasoningEffort':'low'}]}],'nextCursor':None}]
        backend=Backend(tempfile.gettempdir(),rpc=rpc);identity=backend.identity();context=backend.discover()
        self.assertNotIn('private@example.test',json.dumps(identity));self.assertEqual(len(identity['account_key']),64)
        self.assertEqual(context['capabilities']['model_efforts']['candidate'],['high']);self.assertEqual(context['discovery']['models']['other'],'available')
        self.assertEqual(rpc.request.call_args_list[-1].args[1]['cursor'],'more')
    def test_codex_inventory_exposes_version_but_not_inferred_model_revision(self):
        from unittest.mock import Mock
        rpc = Mock()
        rpc.request.return_value = {'data': [{'model': 'alias',
                                              'supportedReasoningEfforts': [{'reasoningEffort': 'high'}]}],
                                    'nextCursor': None}
        with patch('workflow_lib.native_models._cli_version', return_value='1.2.3'):
            context = self.backend()(tempfile.gettempdir(), rpc=rpc).discover()
        self.assertEqual(context['discovery']['host_version'], '1.2.3')
        self.assertNotIn('alias', context['discovery']['model_revisions'])
    def test_codex_configuration_uses_effective_host_response(self):
        Backend=self.backend();from unittest.mock import Mock
        rpc=Mock();rpc.request.return_value={'model':'substitute','modelProvider':'openai','reasoningEffort':'low','thread':{'id':'actual-thread','sessionId':'actual-session'}}
        backend=Backend(tempfile.gettempdir(),rpc=rpc);result=backend.configure({'provider':'openai','model':'candidate','effort':'high'},'bounded context','read-only')
        self.assertEqual(result['observed']['model'],'substitute');self.assertEqual(result['observed']['effort'],'low');self.assertEqual(result['invocation_ref'],'codex://actual-thread')
        self.assertEqual(rpc.request.call_args.args[1]['config']['model_reasoning_effort'],'high')
        self.assertEqual(rpc.request.call_args.args[1]['sandbox'],'read-only')
    def test_claude_launch_uses_argv_native_agent_controls_and_no_effort_claim(self):
        from workflow_lib.native_models import ClaudeBackend
        from unittest.mock import Mock
        result=Mock(returncode=0,stdout=json.dumps({'session_id':'actual-session','result':'done','modelUsage':{'claude-fixture':{}}}),stderr='')
        with patch('workflow_lib.native_models.run_bounded',return_value=result) as runner:
            backend=ClaudeBackend(tempfile.gettempdir());output=backend.invoke({'provider':'anthropic','model':'claude-fixture','effort':'medium'},'Return a bounded review.','actor;$(echo nope)','read-only',30)
        argv=runner.call_args.args[0];self.assertEqual(argv[0],'claude');self.assertIn('--agents',argv);self.assertIn('--agent',argv)
        self.assertEqual(output['observed']['model'],'claude-fixture');self.assertIsNone(output['observed']['effort']);self.assertEqual(output['observation_source'],'host-invocation-metadata')
        self.assertFalse(runner.call_args.kwargs.get('shell',False));self.assertNotIn('Bash',argv[argv.index('--tools')+1])
    def test_native_cache_is_account_policy_release_and_time_scoped(self):
        from workflow_lib.native_models import NativeCache
        with tempfile.TemporaryDirectory() as temp:
            cache=NativeCache(Path(temp));context={'capabilities':{'models':['candidate']},'discovery':{'models':{'candidate':'available'}}}
            cache.put('codex','account','policy','release',context,100,60)
            self.assertEqual(cache.get('codex','account','policy','release',120),context)
            for account,policy,release,now in [('other','policy','release',120),('account','new','release',120),('account','policy','changed',120),('account','policy','release',161)]:self.assertIsNone(cache.get('codex',account,policy,release,now))
            cache.invalidate('codex','account','policy','release');self.assertIsNone(cache.get('codex','account','policy','release',120))
    def test_runtime_candidate_selection_is_honestly_unvalidated(self):
        from workflow_lib.model_policy import resolve_profile
        policy=json.loads((ROOT/'definitions/model-policy.json').read_text())
        cap={'configure':True,'observe':False,'models':['new-model'],'efforts':['medium'],'model_efforts':{'new-model':['medium']}}
        result=resolve_profile(policy,{'host':'codex','stage':'implementation','pin':'new-model','allow_unvalidated':True},cap,{'models':{'new-model':'available'}},None)
        self.assertEqual(result['reason_code'],'UNVALIDATED_ADVISORY');self.assertFalse(result['capability_validated']);self.assertIsNone(result['validation_ref'])
    def test_model_effort_is_checked_for_selected_model(self):
        from workflow_lib.model_policy import resolve_profile
        policy=json.loads((ROOT/'definitions/model-policy.json').read_text())
        cap={'configure':True,'observe':False,'models':['new-model'],'efforts':['high','medium'],'model_efforts':{'new-model':['high']}}
        result=resolve_profile(policy,{'host':'codex','stage':'implementation','pin':'new-model','allow_unvalidated':True},cap,{'models':{'new-model':'available'}},None)
        self.assertEqual(result['status'],'block')
    def test_running_native_invocation_blocks_transfer_and_detach(self):
        state=host_state();apply_host_event(state,'attach',attachment())
        started=apply_host_event(state,'native-start',{'binding_id':'b1','revision':1,'invocation_id':'native','stage':'implementation','decision':{'status':'allow','mode':'advisory','resolved':{'model':'candidate','effort':'medium'}},'request_hash':'request','policy_revision':0})
        self.assertEqual(started['scope']['token'],'t')
        for kind,request in [('detach',{'binding_id':'b1','revision':1}),('handoff-prepare',{'binding_id':'b1','revision':1,'handoff_id':'h','target_host':'claude','target_actor_id':'next'})]:
            with self.assertRaises(WorkflowError):apply_host_event(state,kind,request)
        with self.assertRaises(WorkflowError):apply_host_event(state,'native-start',{'binding_id':'b1','revision':1,'invocation_id':'duplicate','stage':'implementation','decision':{'status':'allow'},'request_hash':'duplicate','policy_revision':0})
    def test_native_finish_receipt_and_interruption_preserve_attempt(self):
        state=host_state();apply_host_event(state,'attach',attachment())
        apply_host_event(state,'native-start',{'binding_id':'b1','revision':1,'invocation_id':'native','stage':'implementation','decision':{'status':'allow','mode':'advisory','resolved':{'model':'candidate','effort':'medium'}},'request_hash':'request','policy_revision':0})
        result=apply_host_event(state,'native-finish',{'binding_id':'b1','revision':1,'invocation_id':'native','result':{'status':'interrupted','error_kind':'quota','output_ref':'artifact'}})
        self.assertEqual(result['scope']['token'],'t');self.assertEqual(state['runs']['run']['active_attempt']['token'],'t');self.assertFalse(state['runs']['run']['model_interruptions'][0]['retry_allowed'])
        self.assertEqual(state['runs']['run']['model_receipts']['native']['reason_code'],'INVOCATION_INTERRUPTED')
    def test_coordinator_records_actual_result_and_exact_retry_never_launches_twice(self):
        from workflow_lib.native_runtime import invoke
        from unittest.mock import Mock
        state=host_state();apply_host_event(state,'attach',attachment());apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'pin':'candidate','allow_unvalidated':True})
        backend=Mock();backend.identity.return_value={'account_key':'account','cacheable':True};backend.discover.return_value={'capabilities':{'configure':True,'observe':True,'models':['candidate'],'efforts':['medium'],'model_efforts':{'candidate':['medium']}},'discovery':{'models':{'candidate':'available'}}}
        backend.configure.return_value={'observed':{'provider':'openai','model':'candidate','effort':'medium'},'observation_source':'host-effective-configuration','invocation_ref':'codex://actual'}
        backend.invoke.return_value={'status':'completed','observed':{'provider':'openai','model':'candidate','effort':'medium'},'observation_source':'host-effective-configuration','invocation_ref':'codex://actual','output':'real bounded result'}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);transact(root,0,'seed',{'kind':'fixture','payload':state})
            request={'binding_id':'b1','revision':1,'invocation_id':'work','stage':'implementation','prompt':'Review this bounded change.'}
            with patch('workflow_lib.native_runtime.CodexBackend',return_value=backend):
                result=invoke(root,request,'native');retry=invoke(root,request,'native')
            self.assertEqual(result['status'],'allow');self.assertEqual(result['scope']['token'],'t');self.assertEqual(result['observed']['effort'],'medium');self.assertTrue(retry['replayed']);backend.invoke.assert_called_once()
            self.assertEqual((root/result['output_ref']).read_text(),'real bounded result');self.assertEqual(read_state(root)['data']['runs']['run']['active_attempt']['token'],'t')
    def test_transport_limits_output_and_timeout(self):
        from workflow_lib.native_models import run_bounded,NativeError
        with self.assertRaises(NativeError):run_bounded([sys.executable,'-c','import time; time.sleep(2)'],str(ROOT),.02)
        with self.assertRaises(NativeError):run_bounded([sys.executable,'-c','print("x"*3000000)'],str(ROOT),5)
    def test_failed_worker_is_interrupted_before_replacement(self):
        from workflow_lib.native_runtime import invoke
        from workflow_lib.native_models import NativeError
        from unittest.mock import Mock
        state=host_state();apply_host_event(state,'attach',attachment());apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'pin':'candidate','allow_unvalidated':True})
        backend=Mock();backend.identity.return_value={'account_key':'account','cacheable':True};backend.discover.return_value={'capabilities':{'configure':True,'observe':True,'models':['candidate'],'efforts':['medium'],'model_efforts':{'candidate':['medium']}},'discovery':{'models':{'candidate':'available'}}};backend.configure.return_value={'observed':{'provider':'openai','model':'candidate','effort':'medium'}};backend.invoke.side_effect=NativeError('quota')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);transact(root,0,'seed',{'kind':'fixture','payload':state});request={'binding_id':'b1','revision':1,'invocation_id':'failure','stage':'implementation','prompt':'bounded work'}
            with patch('workflow_lib.native_runtime.CodexBackend',return_value=backend):
                result=invoke(root,request,'failure');self.assertEqual(result['status'],'block')
                with self.assertRaises(WorkflowError):invoke(root,{**request,'invocation_id':'replacement'},'replacement')
            run=read_state(root)['data']['runs']['run'];self.assertEqual(run['active_attempt']['token'],'t');self.assertEqual(run['model_interruptions'][0]['error_kind'],'quota')
    def test_preferences_scope_host_without_erasing_shared_limits(self):
        from workflow_lib.model_policy import effective_preferences
        state=host_state();apply_host_event(state,'attach',attachment())
        apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'max_cost':1})
        apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'target_host':'claude','pin':'claude-choice','mode':'advisory'})
        run=state['runs']['run'];self.assertNotIn('pin',effective_preferences(run,'implementation','codex'));self.assertEqual(effective_preferences(run,'implementation','claude')['pin'],'claude-choice');self.assertEqual(effective_preferences(run,'implementation','claude')['max_cost'],1)
    def test_empty_allowlist_blocks_advisory_selection(self):
        from workflow_lib.model_policy import resolve_profile
        policy=json.loads((ROOT/'definitions/model-policy.json').read_text())
        decision=resolve_profile(policy,{'host':'codex','stage':'scan','allowed_models':[]},{'models':[],'efforts':[]},{},None)
        self.assertEqual(decision['status'],'block')
    def test_native_cache_corrupt_entry_is_only_a_miss(self):
        from workflow_lib.native_models import NativeCache
        with tempfile.TemporaryDirectory() as temp:
            cache=NativeCache(Path(temp));key=cache.key('codex','account','policy','release');cache.path.write_text(json.dumps({key:['broken']}))
            self.assertIsNone(cache.get('codex','account','policy','release',100))
    def test_attempt_cannot_be_abandoned_during_native_work(self):
        from workflow_lib.store import _apply_event
        state=host_state();state['runs']['run']['state_version']=1;apply_host_event(state,'attach',attachment())
        apply_host_event(state,'native-start',{'binding_id':'b1','revision':1,'invocation_id':'native','stage':'implementation','decision':{'status':'allow','mode':'advisory','resolved':{'model':'candidate','effort':'medium'}},'policy_revision':0})
        with self.assertRaises(WorkflowError):
            _apply_event({'data':state},{'kind':'run.attempt.abandoned','payload':{'run_id':'run','token':'t'}})
    def test_handoff_policy_revision_is_checked_under_lock(self):
        from workflow_lib.hosts import prepare_handoff,accept_handoff
        state=host_state();apply_host_event(state,'attach',attachment())
        prepare_handoff(state,{'binding_id':'b1','revision':1,'handoff_id':'h','target_host':'claude','target_actor_id':'next'})
        target=attachment();target.update(binding_id='b2',host='claude',actor_id='next',session_id='next')
        with self.assertRaises(WorkflowError):accept_handoff(state,{'handoff_id':'h','destination':target},target['release'],target['release'],{'status':'allow','policy_revision':99})
        self.assertEqual(state['host_bindings']['b1']['status'],'active')
    def test_reconcile_rejects_live_launcher_and_preserves_attempt(self):
        import os
        from workflow_lib.native_runtime import reconcile
        state=host_state();apply_host_event(state,'attach',attachment())
        apply_host_event(state,'native-start',{'binding_id':'b1','revision':1,'invocation_id':'native','stage':'implementation','decision':{'status':'allow','mode':'advisory','resolved':{'model':'candidate','effort':'medium'}},'policy_revision':0,'launcher_pid':os.getpid()})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);transact(root,0,'seed',{'kind':'fixture','payload':state})
            with self.assertRaises(WorkflowError):reconcile(root,{'binding_id':'b1','revision':1,'invocation_id':'native','worker_stop_confirmation':{'approved':True,'actor_id':'human'}},'reconcile')
            self.assertEqual(read_state(root)['data']['runs']['run']['active_attempt']['token'],'t')
    def test_network_replacement_without_authorization_is_bounded(self):
        state=host_state();apply_host_event(state,'attach',attachment())
        start={'binding_id':'b1','revision':1,'invocation_id':'first','stage':'implementation','decision':{'status':'allow','mode':'advisory','resolved':{'model':'candidate','effort':'medium'}},'policy_revision':0}
        apply_host_event(state,'native-start',start)
        apply_host_event(state,'native-finish',{'binding_id':'b1','revision':1,'invocation_id':'first','result':{'status':'interrupted','error_kind':'network'}})
        result=apply_host_event(state,'native-start',{**start,'invocation_id':'second','replacement_of':'first','replacement_authorization':None})
        self.assertEqual(result['retry_count'],1)
    def test_transport_stops_children_when_leader_exits(self):
        import time
        from workflow_lib.native_models import run_bounded,NativeError
        with tempfile.TemporaryDirectory() as temp:
            marker=Path(temp)/'escaped'
            child=f'import time;from pathlib import Path;time.sleep(.4);Path({str(marker)!r}).write_text("escaped")'
            parent=f'import subprocess,sys;subprocess.Popen([sys.executable,"-c",{child!r}])'
            with self.assertRaises(NativeError):run_bounded([sys.executable,'-c',parent],str(ROOT),.1)
            time.sleep(.6);self.assertFalse(marker.exists())
    def test_native_start_rejects_changed_attempt_scope(self):
        state=host_state();apply_host_event(state,'attach',attachment())
        from workflow_lib.hosts import invocation_scope
        scope=invocation_scope(state['host_bindings']['b1'],state['runs']['run'],'implementation',{})
        state['runs']['run']['active_attempt']['token']='new'
        with self.assertRaises(WorkflowError):apply_host_event(state,'native-start',{'binding_id':'b1','revision':1,'invocation_id':'native','stage':'implementation','decision':{'status':'allow','mode':'advisory','resolved':{'model':'candidate','effort':'medium'}},'policy_revision':0,'expected_scope':scope})
    def test_retry_rereads_completed_invocation_after_acquiring_lease(self):
        from workflow_lib.native_runtime import invoke
        from unittest.mock import Mock
        state=host_state();apply_host_event(state,'attach',attachment());apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'pin':'candidate','allow_unvalidated':True})
        backend=Mock();backend.identity.return_value={'account_key':'account','cacheable':True};backend.discover.return_value={'capabilities':{'configure':True,'observe':True,'models':['candidate'],'efforts':['medium'],'model_efforts':{'candidate':['medium']}},'discovery':{'models':{'candidate':'available'}}};backend.configure.return_value={'observed':{'provider':'openai','model':'candidate','effort':'medium'}};backend.invoke.return_value={'status':'completed','observed':{'provider':'openai','model':'candidate','effort':'medium'},'output':'once'}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);transact(root,0,'seed',{'kind':'fixture','payload':state});request={'binding_id':'b1','revision':1,'invocation_id':'work','stage':'implementation','prompt':'bounded work'}
            stale=read_state(root)
            with patch('workflow_lib.native_runtime.CodexBackend',return_value=backend):
                invoke(root,request,'once')
                original=read_state;count=0
                def stale_first(path):
                    nonlocal count
                    count+=1
                    return stale if count==1 else original(path)
                with patch('workflow_lib.native_runtime.read_state',side_effect=stale_first):result=invoke(root,request,'once')
            self.assertTrue(result['replayed']);backend.invoke.assert_called_once()
    def test_codex_reroute_is_reported_as_substitution(self):
        from workflow_lib.native_models import CodexBackend
        from unittest.mock import Mock
        rpc=Mock();rpc.notifications=[{'method':'model/rerouted','params':{'threadId':'thread','fromModel':'chosen','toModel':'substitute','turnId':'turn'}},{'method':'turn/completed','params':{'threadId':'thread','turn':{'status':'completed'}}}]
        backend=CodexBackend(tempfile.gettempdir(),rpc);backend.configured={'thread_id':'thread','observed':{'provider':'openai','model':'chosen','effort':'high'},'observation_source':'host-effective-configuration'}
        result=backend.invoke({'model':'chosen'},'bounded prompt','actor')
        self.assertEqual(result['status'],'interrupted');self.assertEqual(result['observed']['model'],'substitute')
    def test_rpc_send_obeys_deadline_when_host_stops_reading(self):
        import time
        from workflow_lib.native_models import RPC,NativeError
        server='import sys,json,time;v=json.loads(sys.stdin.readline());print(json.dumps({"id":v["id"],"result":{}}),flush=True);time.sleep(5)'
        rpc=RPC(str(ROOT),[sys.executable,'-c',server]);started=time.monotonic()
        try:
            with self.assertRaises(NativeError):rpc.request('fixture',{'prompt':'x'*200000},timeout=.1)
            self.assertLess(time.monotonic()-started,1)
        finally:rpc.close()
    def test_native_finish_retries_safe_journal_cas_conflict(self):
        from workflow_lib.native_runtime import _commit
        state=host_state();apply_host_event(state,'attach',attachment())
        apply_host_event(state,'native-start',{'binding_id':'b1','revision':1,'invocation_id':'native','stage':'implementation','decision':{'status':'allow','mode':'advisory','resolved':{'model':'candidate','effort':'medium'}},'policy_revision':0})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);transact(root,0,'seed',{'kind':'fixture','payload':state});calls=0
            def conflict_once(path,version,identifier,event):
                nonlocal calls
                calls+=1
                if calls==1:raise WorkflowError('STALE_STATE','Concurrent unrelated append.')
                return transact(path,version,identifier,event)
            with patch('workflow_lib.native_runtime.transact',side_effect=conflict_once):
                result=_commit(root,'finish','native-finish',{'binding_id':'b1','revision':1,'invocation_id':'native','result':{'status':'completed','observed':{'model':'candidate','effort':'medium'}}},state['host_bindings']['b1'])
            self.assertEqual(result['status'],'allow');self.assertEqual(calls,2)
    def test_preferences_cannot_remove_limits_with_null_or_invalid_values(self):
        state=host_state();apply_host_event(state,'attach',attachment())
        for value in ({'max_cost':None},{'allowed_models':None},{'allowed_models':'candidate'},{'pin':None},{'replacement_authorization':'human'}):
            if 'replacement_authorization' in value:continue
            with self.assertRaises(WorkflowError):apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,**value})
    def test_native_handoff_checks_destination_access_without_transferring_owner(self):
        from workflow_lib.native_runtime import handoff_preflight
        state=host_state();apply_host_event(state,'attach',attachment());apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'target_host':'claude','pin':'candidate','allow_unvalidated':True})
        target=attachment();target.update(binding_id='b2',host='claude',actor_id='next',session_id='next')
        context={'capabilities':{'configure':True,'observe':False,'models':['candidate'],'efforts':['medium'],'model_efforts':{'candidate':['medium']}},'discovery':{'models':{'candidate':'available'}}}
        with patch('workflow_lib.native_runtime.discover',return_value=context),patch('workflow_lib.native_runtime.probe',return_value={'status':'block','reason_code':'NATIVE_QUOTA'}) as probe:
            result=handoff_preflight(tempfile.gettempdir(),state,target)
        self.assertEqual(result['reason_code'],'NATIVE_QUOTA');probe.assert_called_once();self.assertEqual(state['host_bindings']['b1']['status'],'active')
    def test_candidate_probe_cannot_bypass_unknown_cost(self):
        from workflow_lib.native_runtime import candidate_intent
        state=host_state();apply_host_event(state,'attach',attachment());apply_host_event(state,'model-override',{'binding_id':'b1','revision':1,'pin':'candidate','allow_unvalidated':True,'max_cost':1})
        context={'capabilities':{'configure':True,'observe':False,'models':[],'efforts':['medium'],'model_efforts':{}},'discovery':{'models':{}}}
        result=candidate_intent(state,state['host_bindings']['b1'],'implementation',context)
        self.assertEqual(result['status'],'block');self.assertEqual(result['reason_code'],'COST_UNKNOWN')
    def test_reconcile_closed_orphan_is_interrupted_without_relaunch(self):
        from workflow_lib.native_runtime import reconcile
        state=host_state();apply_host_event(state,'attach',attachment())
        apply_host_event(state,'native-start',{'binding_id':'b1','revision':1,'invocation_id':'native','stage':'implementation','decision':{'status':'allow','mode':'advisory','resolved':{'model':'candidate','effort':'medium'}},'policy_revision':0})
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);transact(root,0,'seed',{'kind':'fixture','payload':state})
            result=reconcile(root,{'binding_id':'b1','revision':1,'invocation_id':'native','worker_stop_confirmation':{'approved':True,'actor_id':'human'}},'reconcile')
            self.assertEqual(result['status'],'block');self.assertEqual(result['reason_code'],'NATIVE_ORPHAN_RECONCILED');self.assertEqual(read_state(root)['data']['runs']['run']['active_attempt']['token'],'t')
            retry=reconcile(root,{'binding_id':'b1','revision':1,'invocation_id':'native','worker_stop_confirmation':{'approved':True,'actor_id':'human'}},'reconcile')
            self.assertTrue(retry['replayed'])
