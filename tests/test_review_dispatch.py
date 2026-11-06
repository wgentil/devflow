"""Specialist selection and receipt checks with explicitly synthetic model catalogs."""
import copy,importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class ReviewDispatchTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.review_dispatch'))
        from workflow_lib import review_dispatch
        return review_dispatch
    def policy(self):
        def entry(model,effort):return {'provider':'openai','model':model,'efforts':[effort],
            'status':'validated','validation_ref':'fixture:validated','policy_version':'fixture'}
        return {'version':'fixture','profiles':{'deep-reasoning':{'effort':'high'},'fast-analysis':{'effort':'low'}},
            'stages':{'review':'deep-reasoning'},'hosts':{'codex':{'deep-reasoning':[
                entry('small-sounding-preferred','high'),entry('ultra-sounding-fallback','high')],
                'fast-analysis':[entry('economical','low')]}}}
    def capabilities(self):return {'configure':True,'observe':True,'efforts':['low','high'],
        'models':['small-sounding-preferred','ultra-sounding-fallback','economical'],
        'model_efforts':{'small-sounding-preferred':['high'],'ultra-sounding-fallback':['high'],'economical':['low']}}
    def discovery(self):return {'models':{m:'available' for m in self.capabilities()['models']}}
    def request(self,**kw):return {'host':'codex','stage':'review','perspective':'security','mode':'strict',**kw}
    def select(self,**kw):return self.api().select_review_route(self.policy(),self.request(**kw),self.capabilities(),self.discovery(),None)
    def test_empty_mappings_block_required_specialist(self):
        policy=self.policy();policy['hosts']={}
        self.assertEqual(self.api().select_review_route(policy,self.request(),{},{},None)['status'],'block')
    def test_strongest_eligible_configured_order_not_model_name(self):
        for perspective in ('code','test','architecture','security'):
            result=self.select(perspective=perspective)
            self.assertEqual(result['resolved']['model'],'small-sounding-preferred')
            self.assertEqual(result['resolved']['effort'],'high')
            self.assertEqual(result['profile'],'deep-reasoning')
        result=self.select(allowed_models=['ultra-sounding-fallback'])
        self.assertEqual(result['resolved']['model'],'ultra-sounding-fallback')
    def test_only_positive_lightweight_assessment_uses_economical_route(self):
        result=self.select(perspective='code',assessment={'status':'allow','risk_status':'current','lightweight':True,'assessment_hash':'fixture'})
        self.assertEqual(result['resolved']['model'],'economical')
        self.assertEqual(self.select(perspective='code',assessment={'lightweight':True})['profile'],'deep-reasoning')
        self.assertEqual(self.select(perspective='security',assessment={'status':'allow','risk_status':'current','lightweight':True,'assessment_hash':'fixture'})['profile'],'deep-reasoning')
    def test_restrictions_cannot_downgrade_substantive_profile_or_effort(self):
        self.assertEqual(self.select(profile='fast-analysis',effort='low')['status'],'block')
        self.assertEqual(self.select(allowed_models=[])['status'],'block')
    def test_missing_tools_effort_observation_and_prices_block(self):
        for case in ('configure','observe','effort','price'):
            cap=self.capabilities();request=self.request()
            if case in ('configure','observe'):cap[case]=False
            if case=='effort':cap['model_efforts']={}
            if case=='price':request.update(max_cost=1,estimated_tokens={'input':10,'output':10})
            with self.subTest(case=case):self.assertEqual(self.api().select_review_route(self.policy(),request,cap,self.discovery(),None)['status'],'block')
    def test_candidate_advisory_selection_is_not_relabelled_validated(self):
        policy=self.policy();policy['hosts']['codex']['deep-reasoning'][0]['status']='candidate'
        result=self.api().select_review_route(policy,self.request(mode='advisory',pin='small-sounding-preferred',allow_unvalidated=True),self.capabilities(),self.discovery(),None)
        self.assertEqual(result['status'],'allow');self.assertFalse(result['capability_validated'])
        self.assertEqual(result['reason_code'],'UNVALIDATED_ADVISORY')

    def receipt_fixture(self):
        from test_review_contracts import ContractTests
        subject=ContractTests().ready()
        package={'role':'item','item_id':'W1','package_hash':'package','source_identity':subject['source_identity']}
        binding={'role':'item-reviewer','item_id':'W1','perspective':'security'}
        scope={'actor_id':'independent','role':'item-reviewer','item_id':'W1','package_hash':'package','perspective':'security',
            'review_scope':self.api().specialist_scope(subject,binding)}
        selected={'provider':'openai','model':'small-sounding-preferred','effort':'high'}
        receipt={'policy_revision':0,'status':'allow','dispatch':True,'capability_validated':True,'validation_ref':'fixture:validated',
            'invocation_id':'actual-call','invocation_ref':'fixture:actual-invocation','scope':scope,'profile':'deep-reasoning',
            'resolved':selected,'observed':copy.deepcopy(selected),'observation_source':'host-effective-configuration'}
        subject['model_receipts']={'actual-call':receipt}
        review={'actor_id':'independent','perspective':'security','model_invocation_id':'actual-call','invocation_ref':'fixture:actual-invocation'}
        return subject,package,review
    def test_model_acceptance_requires_exact_actual_settings_identity_and_scope(self):
        self.assertEqual(self.api().validate_review_model(*self.receipt_fixture())['status'],'allow')
        for case in ('model','effort','provider','validation','source','package','actor','perspective','invocation','prepared'):
            subject,package,review=self.receipt_fixture();receipt=subject['model_receipts']['actual-call']
            if case in ('model','effort','provider'):receipt['observed'][case]='substituted'
            if case=='validation':receipt['capability_validated']=False
            if case=='source':subject['source_identity']='changed'
            if case=='package':package['package_hash']='different'
            if case=='actor':review['actor_id']='implementer'
            if case=='perspective':review['perspective']='code'
            if case=='invocation':review['invocation_ref']='claimed'
            if case=='prepared':receipt['dispatch']=False
            with self.subTest(case=case),self.assertRaises(WorkflowError):self.api().validate_review_model(subject,package,review)
    def test_current_recorded_lightweight_risk_reaches_specialist_scope(self):
        from workflow_lib.review_policy import record_risk,review_bindings,PERSPECTIVES
        subject,package,review=self.receipt_fixture();scope={'role':'item','item_id':'W1'}
        risk={'schema_version':1,'bindings':review_bindings(subject,scope),'classification':'lightweight',
            'triggers':[],'scope_evidence_refs':['fixture:scope-inspection'],'perspectives':{
                p:{'applicability':'not-applicable','reason':'Owned fixture has no effect.','evidence_refs':['fixture:scope']} for p in PERSPECTIVES}}
        subject=record_risk(subject,scope,risk)
        self.assertTrue(self.api().specialist_scope(subject,{'role':'item-reviewer','item_id':'W1','perspective':'code'})['lightweight'])
    def test_missing_eligible_route_never_constructs_backend(self):
        from unittest.mock import patch
        from test_hosts import host_state,attachment
        from workflow_lib.hosts import apply_host_event
        from workflow_lib.store import transact
        from workflow_lib.review_policy import new_review_policy
        import tempfile
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))/'control'
        state=host_state();run=state['runs']['run'];run['review_policy']=new_review_policy()
        run['enforcement']={'protocol':'devflow.python-enforcement/v1','policy_version':1}
        run['review_packages']={'package':{'role':'branch','package_hash':'package'}}
        apply_host_event(state,'attach',attachment(binding_id='review',session_id='review-session',actor_id='independent',
            role='branch-reviewer',package_hash='package',perspective='security'))
        transact(root,0,'owned-fixture',{'kind':'fixture','payload':state})
        with patch('workflow_lib.native_runtime.CodexBackend') as backend:
            result=self.api().dispatch_workflow_review(root,{'binding_id':'review','revision':1,
                'perspective':'security','invocation_id':'call','prompt':'Review owned scope.','estimated_cost':1},'op')
        self.assertEqual(result['status'],'block');backend.assert_not_called()

    def native_fixture(self):
        import subprocess,tempfile
        from unittest.mock import Mock
        from test_hosts import host_state,attachment
        from workflow_lib.hosts import apply_host_event
        from workflow_lib.store import transact
        from workflow_lib.review_policy import new_review_policy
        from workflow_lib.enforcement_live import source_observation
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.implementation_contracts import record_implementation_contract
        from workflow_lib.reviews import prepare_review
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();root=base/'control'
        for args in (['init','-q'],['config','user.name','Owned'],['config','user.email','owned@example.invalid']):subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'code.py').write_text('value=30\n');subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','Owned source'],cwd=repo,check=True)
        head=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,check=True,capture_output=True,text=True).stdout.strip()
        data=host_state(str(repo));run=data['runs']['run'];run['active_attempt']=None
        run['plan']['work_items'][0]['dependencies']=[]
        run.update(review_policy=new_review_policy(),enforcement={'protocol':'devflow.python-enforcement/v1','policy_version':1},
            effect_policy={'max_attempts':8,'max_estimated_cost':8,'max_elapsed_ms':120000},governing_digest='owned-fixture-governing')
        run['source_identity']=source_observation(run)['source_identity']
        inv={'paths':[],'governing_digest':run['governing_digest']}
        run['protected_inventories']={'repo':{'inventory':inv,'baseline':snapshot_protected(repo,inv)}}
        run=record_implementation_contract(run,{'scope':{'role':'item','item_id':'W1'},'source_identity':run['source_identity'],
            'behaviors':[{'id':'value','text':'Fixture approved behavior.','authority_refs':['spec:'+run['plan']['spec_hash']+'#R1']}],
            'invariants':[],'interfaces':[],'non_goals':[],'neighboring_disposition':{'applicability':'not-applicable',
                'reason':'Owned isolated fixture.','evidence_refs':['fixture:scope-inspection']}})
        package=prepare_review(run,'branch',{'repo':{'location':str(repo),'base':head,'head':head}})
        run['review_packages']={package['package_hash']:package};data['runs']['run']=run
        apply_host_event(data,'attach',attachment(project=str(repo),binding_id='review',session_id='review-session',actor_id='independent',
            role='branch-reviewer',package_hash=package['package_hash'],perspective='security'))
        transact(root,0,'owned-native-fixture',{'kind':'fixture','payload':data})
        backend=Mock();backend.identity.return_value={'account_key':'owned-fixture-account','cacheable':True}
        backend.discover.return_value={'capabilities':self.capabilities(),'discovery':self.discovery()}
        selected={'provider':'openai','model':'small-sounding-preferred','effort':'high'}
        backend.configure.return_value={'observed':selected,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configure'}
        backend.invoke.return_value={'status':'completed','observed':selected,'observation_source':'host-invocation-metadata',
            'invocation_ref':'fixture:actual-independent-call','output':'{"verdict":"pass","findings":[]}'}
        request={'binding_id':'review','revision':1,'perspective':'security','invocation_id':'specialist',
            'prompt':'Inspect owned fixture scope.','estimated_cost':1,'diagnostic':True}
        return root,repo,request,backend
    def native_call(self,root,request,backend,operation='specialist-op'):
        from unittest.mock import patch
        with patch('workflow_lib.native_runtime.policy',return_value=self.policy()),patch('workflow_lib.native_runtime.CodexBackend',return_value=backend):
            return self.api().dispatch_workflow_review(root,request,operation)
    def test_actual_native_receipt_retains_scope_and_exact_retry_never_relaunches(self):
        root,repo,request,backend=self.native_fixture();result=self.native_call(root,request,backend)
        self.assertEqual(result['status'],'allow',result)
        self.assertEqual(result['scope']['perspective'],'security')
        self.assertEqual(result['resolved']['effort'],'high')
        self.assertEqual(result['observed']['model'],'small-sounding-preferred')
        self.assertTrue(self.native_call(root,request,backend)['replayed']);backend.invoke.assert_called_once()
    def test_question_after_prepare_prevents_specialist_invoke(self):
        from unittest.mock import patch
        from workflow_lib import native_runtime
        from workflow_lib.store import read_state,transact
        root,repo,request,backend=self.native_fixture();original=native_runtime._commit
        def commit(*args,**kwargs):
            result=original(*args,**kwargs)
            if args[2]=='native-start':
                state=read_state(root);run=state['data']['runs']['run']
                transact(root,state['version'],'late-user-question',{'kind':'domain.enforcement.question','payload':{'request':{
                    'run_id':'run','record':{'id':'q','text':'Which retention rule applies?','scope':['W1'],
                        'source_identity':run['source_identity'],'spec_hash':run['plan']['spec_hash']}}}})
            return result
        with patch.object(native_runtime,'_commit',side_effect=commit),self.assertRaises(WorkflowError):
            self.native_call(root,request,backend)
        backend.invoke.assert_not_called()
    def test_uncertain_specialist_is_not_relaunched(self):
        from workflow_lib.native_models import NativeError
        root,repo,request,backend=self.native_fixture();backend.invoke.side_effect=NativeError('unavailable','Owned interruption.')
        first=self.native_call(root,request,backend);self.assertEqual(first['status'],'block')
        self.assertTrue(self.native_call(root,request,backend)['replayed'])
        with self.assertRaises(WorkflowError):self.native_call(root,{**request,'invocation_id':'replacement'},backend,'replacement-op')
        backend.invoke.assert_called_once()

    def test_known_prelaunch_block_releases_claim_without_refunding_attempt(self):
        from workflow_lib.store import read_state
        root,repo,request,backend=self.native_fixture();backend.discover.return_value['capabilities']['model_efforts']={}
        result=self.native_call(root,request,backend)
        self.assertEqual(result['status'],'block');backend.invoke.assert_not_called()
        run=read_state(root)['data']['runs']['run']
        self.assertEqual(run['effects']['specialist']['status'],'failed')
        self.assertEqual(len(run['effects']),1)
    def test_actual_owned_child_interruption_never_launches_a_replacement(self):
        import subprocess
        from workflow_lib.native_models import NativeError
        from workflow_lib.process_liveness import process_alive
        root,repo,request,backend=self.native_fixture();marker=repo.parent/'started';pids=[]
        def interrupted(*args):
            child=subprocess.Popen([sys.executable,'-c',
                'import os;from pathlib import Path;Path('+repr(str(marker))+').write_text(str(os.getpid()));os._exit(23)'])
            pids.append(child.pid);self.assertEqual(child.wait(timeout=10),23)
            raise NativeError('unavailable','Owned child stopped without a complete provider receipt.')
        backend.invoke.side_effect=interrupted
        self.assertEqual(self.native_call(root,request,backend)['status'],'block')
        self.assertTrue(marker.exists());self.assertFalse(process_alive(pids[0]))
        self.assertTrue(self.native_call(root,request,backend)['replayed']);self.assertEqual(len(pids),1)
    def test_four_perspectives_from_one_actual_invocation_are_not_independent(self):
        subject,package,report=self.receipt_fixture()
        subject['reviews']={'item':[{'review_id':'other','invocation_ref':report['invocation_ref'],
            'actor_id':'another-actor','perspective':'code','package_hash':package['package_hash']}]}
        with self.assertRaises(WorkflowError):self.api().validate_review_model(subject,package,report)

    def test_prelaunch_exact_retry_returns_original_blocked_receipt(self):
        root,repo,request,backend=self.native_fixture();backend.discover.return_value['capabilities']['model_efforts']={}
        first=self.native_call(root,request,backend);again=self.native_call(root,request,backend)
        self.assertTrue(again.pop('replayed'))
        self.assertEqual(first,again)
    def test_host_bridge_cannot_route_specialist_as_low_effort_task(self):
        from unittest.mock import patch
        from workflow_lib.interactive_routing import prepare_delegation
        from test_task_routing import task
        root,repo,request,backend=self.native_fixture()
        context={'account_key':'fixture','capabilities':self.capabilities(),'discovery':{**self.discovery(),'host_version':'1.2.3'},
            'controls':{'schema_version':1,'host_version':'1.2.3','source':'enclosing-host','supported':True,
                'account_key':'fixture','configuration_hash':'fixture-config','model_efforts':self.capabilities()['model_efforts'],
                'custom_agent':{},'agent_defaults':{},'parent':{},'overrides':{}}}
        facts=task(actor_id='independent',stage='review',kind='extraction',complexity='bounded',uncertainty='resolved')
        request={**request,'stage':'review','execution_path':'interactive-nonfork','task':facts}
        with patch('workflow_lib.interactive_routing.policy',return_value=self.policy()):
            prepared=prepare_delegation(root,request,context)
        self.assertEqual(prepared['decision']['resolved']['effort'],'high')
        self.assertEqual(prepared['decision']['profile'],'deep-reasoning')

    def test_acceptance_retains_independent_requirements_role_without_specialist_perspective(self):
        from workflow_lib.hosts import invocation_scope
        subject,package,review=self.receipt_fixture()
        binding={'binding_id':'acceptance','revision':1,'host':'codex','session_id':'independent-session',
            'actor_id':'requirements-reviewer','role':'acceptance-reviewer','run_id':'r','package_hash':'requirements-package'}
        scope=invocation_scope(binding,subject,'acceptance',{})
        self.assertNotIn('perspective',scope)
        self.assertEqual(scope['role'],'acceptance-reviewer')

    def test_public_dispatch_reports_missing_mapping_without_a_provider(self):
        import json,subprocess
        root,repo,request,backend=self.native_fixture();input_=repo.parent/'review.json';input_.write_text(json.dumps(request))
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        result=subprocess.run([sys.executable,str(entry),'review','dispatch','--root',str(root),'--run-id','run',
            '--input',str(input_),'--operation-id','public-review'],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        output=json.loads(result.stdout);self.assertEqual(output['status'],'block')
        self.assertEqual(output['reason_code'],'NO_VALIDATED_PERMITTED_MODEL')

    def test_genuine_inprocess_host_bridge_records_specialist_observation(self):
        import json
        from unittest.mock import patch
        from workflow_lib.interactive_routing import dispatch_delegation
        from test_task_routing import task
        root,repo,request,backend=self.native_fixture()
        context={'account_key':'fixture','capabilities':self.capabilities(),'discovery':{**self.discovery(),'host_version':'1.2.3'},
            'controls':{'schema_version':1,'host_version':'1.2.3','source':'enclosing-host','supported':True,
                'account_key':'fixture','configuration_hash':'fixture-config','model_efforts':self.capabilities()['model_efforts'],
                'custom_agent':{},'agent_defaults':{},'parent':{},'overrides':{}}}
        class OwnedBridge:
            def __init__(self):self.spawns=[]
            def capabilities(self):return copy.deepcopy(context)
            def spawn(self,prepared):self.spawns.append(prepared);return 'owned-handle'
            def collect(self,handle):
                prepared=self.spawns[-1];scope=prepared['scope'];selected=prepared['decision']['resolved']
                return {'status':'completed','observed':selected,'observation_source':'host-invocation-metadata',
                    'invocation_ref':'fixture:actual-host-worker','output':json.dumps({'status':'completed','scope':scope,
                        'completed_scope':[scope['package_hash']],'evidence_refs':['fixture:owned-review-output'],'unresolved_facts':[]})}
        bridge=OwnedBridge();request={**request,'stage':'review','execution_path':'interactive-nonfork',
            'task':task(actor_id='independent',stage='review',kind='review',scope=['code.py'])}
        with patch('workflow_lib.interactive_routing.policy',return_value=self.policy()):
            result=dispatch_delegation(root,request,'owned-host-review',bridge)
            again=dispatch_delegation(root,request,'owned-host-review',bridge)
        self.assertEqual(result['status'],'allow',result)
        self.assertEqual(result['scope']['perspective'],'security')
        self.assertEqual(result['observed']['effort'],'high')
        self.assertTrue(again['replayed']);self.assertEqual(len(bridge.spawns),1)

    def test_actual_native_receipt_seals_real_report_content(self):
        root,repo,request,backend=self.native_fixture();result=self.native_call(root,request,backend)
        from workflow_lib.document_units import digest
        self.assertEqual(result.get('review_report_hash'),digest({'verdict':'pass','findings':[]}))

    def test_changed_model_preferences_stale_prior_specialist_eligibility(self):
        subject,package,review=self.receipt_fixture()
        subject['model_receipts']['actual-call']['policy_revision']=0
        subject['model_overrides']=[{'allowed_models':['different-model']}]
        with self.assertRaises(WorkflowError):self.api().validate_review_model(subject,package,review)

    def test_specialist_receives_complete_content_bound_package_artifact(self):
        import json
        root,repo,request,backend=self.native_fixture();receipt=self.native_call(root,request,backend)
        prompt=backend.invoke.call_args.args[1]
        brief=json.loads(prompt.split('\nScoped authoritative brief:\n',1)[1].split('\nTask:\n',1)[0])
        self.assertIn('review_input',brief,'A package hash alone does not give the reviewer the actual diff and obligations.')
        ref=brief['review_input'];artifact=json.loads(Path(ref['artifact_ref']).read_text())
        self.assertEqual(artifact['value']['package']['package_hash'],receipt['scope']['package_hash'])
        self.assertTrue(ref['required']);self.assertIn('repositories',artifact['value']['package'])
        self.assertIn('report_contract',artifact['value']['package'])
        self.assertIn('verification_proofs',artifact['value']['package'])
        self.assertIn('implementation_contracts',artifact['value']['package'])
        self.assertIn('review_input_ref',prompt)

    def test_package_lists_dirty_tracked_and_untracked_inputs_with_repository_identity(self):
        from workflow_lib.store import read_state
        from workflow_lib.reviews import prepare_review
        import subprocess
        root,repo,request,backend=self.native_fixture();subject=read_state(root)['data']['runs']['run']
        (repo/'code.py').write_text('value=60\n');(repo/'new.py').write_text('new=True\n')
        head=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,check=True,capture_output=True,text=True).stdout.strip()
        package=prepare_review(subject,'branch',{'repo':{'location':str(repo),'base':head,'head':head}})
        self.assertEqual(package.get('review_inputs'),[{'repo_id':'repo','path':'code.py'},{'repo_id':'repo','path':'new.py'}])
        self.assertIn('review_requirements',package)

    def test_independent_risk_raise_requires_substantive_model_controls(self):
        from workflow_lib.review_policy import record_risk,review_bindings,PERSPECTIVES
        subject,package,review=self.receipt_fixture();scope={'role':'branch'}
        risk={'schema_version':1,'bindings':review_bindings(subject,scope),'classification':'lightweight','triggers':[],
            'scope_evidence_refs':['fixture:positive-scope'],'perspectives':{p:{'applicability':'not-applicable',
                'reason':'Initial fixture assessment.','evidence_refs':['fixture:scope']} for p in PERSPECTIVES}}
        subject=record_risk(subject,scope,risk)
        subject['review_risk_escalations']=[{'scope':scope,'bindings':review_bindings(subject,scope),
            'review_id':'actual-independent-review','required_perspectives':['security']}]
        actual=self.api().specialist_scope(subject,{'role':'branch-reviewer','perspective':'test'})
        self.assertFalse(actual['lightweight'])
        result=self.select(perspective='test',assessment=actual['assessment'])
        self.assertEqual(result['profile'],'deep-reasoning');self.assertEqual(result['resolved']['effort'],'high')
