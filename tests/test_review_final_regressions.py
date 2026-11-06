"""Independent-review regressions using owned sources and labeled transport fixtures."""
import copy,json,subprocess,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
import test_review_driver,test_review_dispatch,test_standalone_review

class FinalReviewRegressions(unittest.TestCase):
    def fixture(self,kind):
        cls={'driver':test_review_driver.ReviewDriverTests,'dispatch':test_review_dispatch.ReviewDispatchTests,'standalone':test_standalone_review.StandaloneReviewTests}[kind]
        case=cls();self.addCleanup(case.doCleanups);return case
    def corrupt(self,root):
        for path in (root/'context-artifacts').glob('*.json'):
            value=json.loads(path.read_text())
            if value.get('identity',{}).get('kind')=='review-input':
                value['value']['package']['review_contract']={'request':{'intent':'FORGED authority'}}
                path.write_text(json.dumps(value));return
        self.fail('Expected an actual published review artifact.')
    def test_standalone_artifact_change_before_turn_never_invokes(self):
        from workflow_lib.review_dispatch import dispatch_session_review
        case=self.fixture('standalone');base,repo,path=case.model_fixture();settings=self.fixture('dispatch');marker=base/'invoked'
        parent=self
        class Backend:
            def __init__(self,*args):pass
            def discover(self):
                parent.corrupt(path.with_name(path.name+'.artifacts'))
                return {'capabilities':settings.capabilities(),'discovery':settings.discovery()}
            def configure(self,resolved,*args):return {'observed':resolved,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configured'}
            def invoke(self,resolved,*args):
                marker.write_text('actual-turn');return {'status':'completed','observed':resolved,'observation_source':'host-invocation-metadata','invocation_ref':'fixture:actual-turn','output':'{"verdict":"block","findings":[],"diagnostic":true}'}
            def close(self):pass
        with patch('workflow_lib.native_runtime.policy',return_value=settings.policy()),patch('workflow_lib.session_models.CodexBackend',Backend):
            result=dispatch_session_review(path,{'perspective':'security','host':'codex','actor_id':'reviewer','estimated_cost':1,'diagnostic':True},'artifact-corrupt')
        self.assertFalse(marker.exists(),result)
    def test_workflow_artifact_change_after_configuration_never_invokes(self):
        from workflow_lib.review_dispatch import dispatch_workflow_review
        case=self.fixture('dispatch');root,repo,request,backend=case.native_fixture();observed=backend.configure.return_value
        def configure(*args,**kwargs):self.corrupt(root);return observed
        backend.configure.side_effect=configure
        with patch('workflow_lib.native_runtime.policy',return_value=case.policy()),patch('workflow_lib.native_runtime.CodexBackend',return_value=backend):
            try:dispatch_workflow_review(root,request,'corrupt-workflow')
            except Exception as error:
                from workflow_lib.store import WorkflowError
                self.assertIsInstance(error,WorkflowError)
        self.assertEqual(backend.invoke.call_count,0)
    def test_configured_substitution_never_starts_a_codex_turn(self):
        from workflow_lib.review_dispatch import dispatch_session_review
        from workflow_lib.native_models import CodexBackend
        from workflow_lib.review_sessions import read_session
        case=self.fixture('standalone');base,repo,path=case.model_fixture();settings=self.fixture('dispatch');calls=[]
        class RPC:
            def __init__(self):self.notifications=[]
            def request(self,method,args):
                calls.append(method)
                if method=='model/list':return {'data':[{'model':'small-sounding-preferred','supportedReasoningEfforts':[{'reasoningEffort':'high'}]}]}
                if method=='config/read':return {'config':{}}
                if method=='thread/start':return {'thread':{'id':'owned-thread'},'modelProvider':'openai','model':'SUBSTITUTED-WEAK','reasoningEffort':'low'}
                if method=='turn/start':
                    self.notifications=[{'method':'turn/completed','params':{'threadId':'owned-thread','turn':{'status':'completed'}}}];return {}
                raise AssertionError(method)
            def close(self):pass
        class Backend(CodexBackend):
            def __init__(self,project):super().__init__(project,rpc=RPC())
        with patch('workflow_lib.native_runtime.policy',return_value=settings.policy()),patch('workflow_lib.session_models.CodexBackend',Backend),patch('workflow_lib.native_models._cli_version',return_value='owned-fixture'):
            result=dispatch_session_review(path,{'perspective':'security','host':'codex','actor_id':'reviewer','estimated_cost':1,'diagnostic':True},'substitution')
        self.assertNotIn('turn/start',calls,result);self.assertFalse(result['dispatch'])
        self.assertEqual(read_session(path)['subject']['effects']['substitution']['status'],'failed')
    def test_sealed_deferred_minor_does_not_block_actual_repair_completion(self):
        from workflow_lib.review_driver import run_orchestration
        from workflow_lib.review_sessions import read_session
        case=self.fixture('driver');base,repo,path,request=case.owned_session();policy,backend=case.transport(path,base)
        class Minor(backend):
            def invoke(self,resolved,prompt,actor,access,timeout):
                result=super().invoke(resolved,prompt,actor,access,timeout)
                if actor=='review-security':
                    report=json.loads(result['output']);report['findings']=[{'id':'naming','severity':'minor','path':'app.py','line':1,
                        'evidence_refs':['repo-1:app.py:1'],'failure_scenario':'A maintainer reads the short name.','impact':'Readability only.',
                        'requested_correction':'Consider a descriptive name.','disposition':{'status':'deferred','reason':'No behavior impact; retain follow-up.'}}]
                    result['output']=json.dumps(report)
                return result
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',Minor):result=run_orchestration(path,request,'minor-repair',30)
        subject=read_session(path)['subject'];self.assertEqual(result['status'],'complete',result)
        self.assertEqual(next(f for f in subject['unresolved_findings'] if f['id']=='naming')['status'],'deferred')
        self.assertEqual((base/'worker-count').read_text(),'x')
    def test_independent_perspectives_share_one_actual_correction_round(self):
        from workflow_lib.reviews import validate_review_contract
        from workflow_lib.review_policy import new_review_policy
        subject={'review_policy':new_review_policy(),'review_packages':{'pkg':{'source_identity':'source-1'},'new':{'source_identity':'source-2'}},'reviews':{'branch':[]}}
        def review(p,package='pkg',diagnostic=False):return {'role':'branch','actor_id':p,'invocation_ref':'fixture:'+p+':'+package,'perspective':p,'package_hash':package,'verdict':'request-changes','findings':[{'id':p}],'diagnostic':diagnostic}
        for p in ('code','test','architecture','security'):
            row=review(p);validate_review_contract(subject,row);subject['reviews']['branch'].append(row)
        with self.assertRaisesRegex(ValueError,'correction limit'):validate_review_contract(subject,review('code','new'))
    def test_diagnostic_reports_do_not_spend_correction_rounds(self):
        from workflow_lib.reviews import validate_review_contract
        from workflow_lib.review_policy import new_review_policy
        prior={'role':'branch','actor_id':'diagnostic','invocation_ref':'fixture:diagnostic','perspective':'code','package_hash':'old','verdict':'request-changes','findings':[{'id':'prior'}],'diagnostic':True}
        subject={'review_policy':new_review_policy(),'review_packages':{'old':{'source_identity':'old'},'new':{'source_identity':'new'}},'reviews':{'branch':[prior]}}
        validate_review_contract(subject,{**prior,'actor_id':'actual','invocation_ref':'fixture:actual','package_hash':'new','diagnostic':False})
    def test_interactive_known_preflight_failure_finishes_claim_and_replays(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        from workflow_lib.storage_access import read_current
        from test_task_routing import task
        case=self.fixture('dispatch');root,repo,request,backend=case.native_fixture()
        context={'account_key':'fixture','capabilities':case.capabilities(),'discovery':{**case.discovery(),'host_version':'1.2.3'},'controls':{
            'schema_version':1,'host_version':'1.2.3','source':'enclosing-host','supported':True,'account_key':'fixture','configuration_hash':'fixture-config',
            'model_efforts':case.capabilities()['model_efforts'],'custom_agent':{'model_reasoning_effort':'low'},'agent_defaults':{},'parent':{},'overrides':{}}}
        class Bridge:
            def capabilities(self):return copy.deepcopy(context)
            def spawn(self,*args):raise AssertionError('Known preflight rejection cannot spawn')
        request={**request,'stage':'review','execution_path':'interactive-nonfork','task':task(actor_id='independent',stage='review',kind='review',scope=['code.py'])}
        with patch('workflow_lib.interactive_routing.policy',return_value=case.policy()):
            first=dispatch_delegation(root,request,'blocked-interactive',Bridge())
            subject=read_current(root,run_id='run')['data']['runs']['run']
            self.assertTrue(subject['effects']);self.assertTrue(all(e['status']=='failed' for e in subject['effects'].values()),first)
            again=dispatch_delegation(root,request,'blocked-interactive',Bridge())
        self.assertTrue(again['replayed']);self.assertFalse(again['dispatch'])
        self.assertEqual(len(read_current(root,run_id='run')['data']['runs']['run']['effects']),1)
    def test_failed_configured_gate_maps_into_shared_repair_scope(self):
        import test_review_orchestration
        from workflow_lib.review_orchestration import orchestration_next
        from workflow_lib.document_units import digest
        subject=test_review_orchestration.OrchestrationTests().configure();subject['unresolved_findings']=[]
        subject['plan']['work_items'][0]['repo_id']='repo'
        subject['required_hardening_gates']=['lint'];subject['hardening_config']={'lint':{'repo_id':'repo','command':['fixture-lint'],'pre_review':True,'kind':'lint','item_ids':['W1']}}
        subject['hardening_config_hash']=digest(subject['hardening_config']);subject['hardening_proofs']={'lint':{'passed':False,'config_hash':subject['hardening_config_hash'],'source_identity':subject['source_identity'],'failure':'LINT_ERRORS'}}
        action=orchestration_next(subject,1100)
        self.assertIn('lint',action['scope'].get('gate_ids',[]));self.assertEqual(action['scope'].get('item_id'),'W1')
        self.assertNotIn(action['kind'],{'package','review','complete','workflow-stage'})

    def test_standalone_post_turn_artifact_corruption_blocks_admission_but_retains_execution(self):
        from workflow_lib.review_dispatch import dispatch_session_review
        from workflow_lib.review_sessions import read_session
        from workflow_lib.review_summary import summarize_review
        case=self.fixture('standalone');base,repo,path=case.model_fixture();settings=self.fixture('dispatch');parent=self;calls=[]
        class Backend:
            def __init__(self,*args):pass
            def discover(self):return {'capabilities':settings.capabilities(),'discovery':settings.discovery()}
            def configure(self,resolved,*args):return {'observed':resolved,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configured'}
            def invoke(self,resolved,*args):
                calls.append('turn');parent.corrupt(path.with_name(path.name+'.artifacts'))
                return {'status':'completed','observed':resolved,'observation_source':'host-invocation-metadata','invocation_ref':'fixture:actual-corrupt-turn','output':'{"verdict":"block","findings":[],"diagnostic":true}'}
            def close(self):pass
        with patch('workflow_lib.native_runtime.policy',return_value=settings.policy()),patch('workflow_lib.session_models.CodexBackend',Backend):
            result=dispatch_session_review(path,{'perspective':'security','host':'codex','actor_id':'reviewer','estimated_cost':1,'diagnostic':True},'post-turn-corrupt')
        subject=read_session(path)['subject'];self.assertEqual(calls,['turn']);self.assertEqual(result['status'],'block',result)
        self.assertNotEqual(result['report_status'],'recorded');self.assertEqual(subject['effects']['post-turn-corrupt']['status'],'completed')
        self.assertTrue(result['dispatch']);self.assertEqual(summarize_review(subject)['model_invocations'],1)
    def test_workflow_post_turn_artifact_corruption_retains_completed_effect_without_pass(self):
        from workflow_lib.review_dispatch import dispatch_workflow_review
        from workflow_lib.storage_access import read_current
        from workflow_lib.store import WorkflowError
        case=self.fixture('dispatch');root,repo,request,backend=case.native_fixture();response=copy.deepcopy(backend.invoke.return_value)
        def invoke(*args,**kwargs):self.corrupt(root);return copy.deepcopy(response)
        backend.invoke.side_effect=invoke
        with patch('workflow_lib.native_runtime.policy',return_value=case.policy()),patch('workflow_lib.native_runtime.CodexBackend',return_value=backend):
            try:dispatch_workflow_review(root,request,'post-turn-workflow')
            except WorkflowError:pass
        subject=read_current(root,run_id='run')['data']['runs']['run'];receipt=subject['model_receipts'][request['invocation_id']]
        self.assertEqual(backend.invoke.call_count,1);self.assertEqual(receipt['status'],'block')
        self.assertEqual(subject['effects'][request['invocation_id']]['status'],'completed');self.assertFalse(receipt.get('review_report_hash'))


    def test_actual_gate_only_repair_keeps_original_proof_and_independent_review(self):
        from workflow_lib.review_driver import run_orchestration
        from workflow_lib.storage_access import read_current
        case=self.fixture('driver');base,repo,root,request=case.owned_workflow(2,gate_only=True)
        policy,backend=case.transport(root,base)
        request['reviewers']={'item':{p:{'host':'codex','binding_id':'review-'+p,'actor_id':'review-'+p,'session_id':'session-'+p,'estimated_cost':1} for p in ('code','test','architecture','security')}}
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.native_runtime.CodexBackend',backend):result=run_orchestration(root,request,'gate-only',40)
        subject=read_current(root,run_id='run')['data']['runs']['run']
        self.assertEqual(subject['items']['W1']['status'],'complete',result.get('next_action'))
        self.assertEqual(subject['unresolved_findings'],[],'Checks must not invent review findings.')
        self.assertTrue(subject['hardening_proofs']['lint']['passed']);self.assertEqual((base/'gate-counter').read_text(),'xx')
        self.assertEqual((base/'worker-count').read_text(),'x')
        self.assertEqual({p['phase'] for p in subject['verification_proofs'].values()},{'RED','GREEN'})
        self.assertEqual(len(subject['reviews']['item']),4)
        self.assertEqual(result['next_action']['scope']['role'],'branch')
    def test_unmapped_gate_never_guesses_edit_scope(self):
        from workflow_lib.review_driver import run_orchestration
        case=self.fixture('driver');base,repo,root,request=case.owned_workflow(2,gate_only=True,gate_mapping=False)
        result=run_orchestration(root,request,'unmapped-gate',10)
        self.assertEqual(result['next_action']['reason_code'],'AFFECTED_ITEM_MAPPING_REQUIRED')
        self.assertFalse((base/'worker-count').exists());self.assertEqual((repo/'app.py').read_text(),'VALUE = 60\n')
    def test_direct_gate_cause_rejects_malformed_or_cross_repository_mapping(self):
        from workflow_lib.implementation_contracts import gate_failure_binding
        base={'source_identity':'s','hardening_config_hash':'c','required_hardening_gates':['lint'],
            'plan':{'work_items':[{'id':'W1','repo_id':'r'},{'id':'W2','repo_id':'other'}]},
            'hardening_config':{'lint':{'pre_review':True,'repo_id':'r','item_ids':['W1']}},
            'hardening_proofs':{'lint':{'passed':False,'source_identity':'s','config_hash':'c','execution_id':'actual','exit_code':1,'failure':'GATE_FAILED'}}}
        self.assertTrue(gate_failure_binding(base,'lint',{'item_id':'W1'}))
        for mapping in ('W1',['W1','W1'],['W1','W2'],['W1','missing'],[['W1']]):
            subject=copy.deepcopy(base);subject['hardening_config']['lint']['item_ids']=mapping
            with self.subTest(mapping=mapping):self.assertIsNone(gate_failure_binding(subject,'lint',{'item_id':'W1'}))
    def test_interactive_artifact_rejection_before_spawn_is_known_nondispatch(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        from workflow_lib.storage_access import read_current
        from test_task_routing import task
        case=self.fixture('dispatch');root,repo,request,backend=case.native_fixture()
        context={'account_key':'fixture','capabilities':case.capabilities(),'discovery':{**case.discovery(),'host_version':'1.2.3'},'controls':{
            'schema_version':1,'host_version':'1.2.3','source':'enclosing-host','supported':True,'account_key':'fixture','configuration_hash':'fixture-config',
            'model_efforts':case.capabilities()['model_efforts'],'custom_agent':{},'agent_defaults':{},'parent':{},'overrides':{}}}
        class Bridge:
            def capabilities(self):return copy.deepcopy(context)
            def spawn(self,*args):raise AssertionError('Corrupt input cannot spawn')
        request={**request,'stage':'review','execution_path':'interactive-nonfork','task':task(actor_id='independent',stage='review',kind='review',scope=['code.py'])}
        from workflow_lib.effect_claims import validate_active_dispatch
        def last_guard(*args,**kwargs):
            result=validate_active_dispatch(*args,**kwargs);self.corrupt(root);return result
        with patch('workflow_lib.interactive_routing.policy',return_value=case.policy()),patch('workflow_lib.effect_claims.validate_active_dispatch',side_effect=last_guard):
            first=dispatch_delegation(root,request,'corrupt-interactive',Bridge())
            self.assertFalse(first['dispatch'],first)
            again=dispatch_delegation(root,request,'corrupt-interactive',Bridge())
        self.assertTrue(again['replayed']);self.assertFalse(again['dispatch'])
        subject=read_current(root,run_id='run')['data']['runs']['run']
        self.assertTrue(all(e['status']=='failed' for e in subject['effects'].values()))
