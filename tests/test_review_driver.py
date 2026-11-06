"""Owned regression/driver fixtures; native providers are labeled transport doubles."""
import copy,importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError
from workflow_lib.document_units import digest

class ReviewDriverTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.review_driver'))
        from workflow_lib import review_driver
        return review_driver
    def test_driver_has_explicit_one_step_and_bounded_run(self):
        self.assertTrue(callable(self.api().advance_orchestration));self.assertTrue(callable(self.api().run_orchestration))
    def test_additional_targets_do_not_invent_a_business_question(self):
        from test_review_contracts import ContractTests
        from workflow_lib.implementation_contracts import record_implementation_contract
        case=ContractTests();subject=case.ready();record=case.contract()
        record['behaviors'][0]['target_ids'].append('retention-boundary')
        record['behaviors'][0]['incorrect_behaviors'].append('Return thirty-one at the boundary.')
        result=record_implementation_contract(subject,record)
        self.assertFalse(result.get('clarifications'),result.get('clarifications'))
        self.assertIn('retention-boundary',result['implementation_contracts']['item:W1']['behaviors'][0]['target_ids'])
    def test_additional_input_union_preserves_every_original_locked_test(self):
        from workflow_lib.test_integrity import verification_integrity_contract
        from workflow_lib.clarifications import clarification_binding
        from workflow_lib.test_extensions import record_extension
        subject={'status':'active','source_identity':'source','plan':{'spec_hash':'spec','work_items':[]},
            'items':{'W1':{'attempts':[{'token':'attempt'}]}},'review_policy':__import__('workflow_lib.review_policy',fromlist=['new_review_policy']).new_review_policy()}
        item={'id':'W1','kind':'code','requirement_ids':['R1'],'verification_inputs':['original.py'],'verification_target_ids':['original']}
        subject['plan']['work_items']=[item]
        extension={'item_id':'W1','token':'attempt','item_contract_hash':digest(item),'clarification_binding':clarification_binding(subject,{'item_id':'W1'}),
            'source_identity':'source','input_bindings':{'extra.py':{'sha256':'extra','path':'extra.py'}},'target_ids':['regression'],
            'reason':'Cover the newly observed boundary without weakening original tests.'}
        subject=record_extension(subject,extension)
        bindings={'original.py':{'sha256':'original','path':'original.py'},'extra.py':{'sha256':'extra','path':'extra.py'}}
        contract=verification_integrity_contract(subject,item,{'original.py':'original','extra.py':'extra'},['original','regression'],['fixture-test'],'json',bindings)
        self.assertEqual(set(contract['targets']),{'original','regression'});self.assertIn('test_extension_hash',contract)
        with self.assertRaises(WorkflowError):verification_integrity_contract(subject,item,{'extra.py':'extra'},['regression'],['fixture-test'],'json',{'extra.py':bindings['extra.py']})
        changed=copy.deepcopy(bindings);changed['extra.py']['sha256']='weakened'
        with self.assertRaises(WorkflowError):verification_integrity_contract(subject,item,{'original.py':'original','extra.py':'weakened'},['original','regression'],['fixture-test'],'json',changed)

    def test_active_current_candidate_can_be_reviewed_before_semantic_completion(self):
        from test_review_dispatch import ReviewDispatchTests
        from workflow_lib.storage_access import read_current
        from workflow_lib.reviews import prepare_review,validate_item_review_scope
        case=ReviewDispatchTests();self.addCleanup(case.doCleanups)
        root,repo,request,backend=case.native_fixture()
        run=read_current(root,run_id='run')['data']['runs']['run']
        item=run['items']['W1'];item['status']='pending';attempt=item['attempts'][-1]
        run['active_attempt']={**attempt,'item_id':'W1','status':'active'}
        import subprocess
        head=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,check=True,capture_output=True,text=True).stdout.strip()
        package=prepare_review(run,'item',{'repo':{'location':str(repo),'base':head,'head':head}},item_id='W1')
        validate_item_review_scope(run,package,{'item_id':'W1'})
        self.assertEqual(item['status'],'pending');self.assertNotIn('semantic_approvals',run)

    def test_report_only_copy_requires_exact_editable_scope_authorization(self):
        from test_standalone_review import StandaloneReviewTests
        from workflow_lib.session_repair import prepare_repair,authorize_repair
        from workflow_lib.review_sessions import read_session
        case=StandaloneReviewTests();self.addCleanup(case.doCleanups)
        base,repo,path=case.model_fixture();before=(repo/'value.py').read_bytes()
        proposal=prepare_repair(path,{'implementer_actor':'writer','protection_paths':['AGENTS.md']})
        self.assertFalse(read_session(path)['subject'].get('editable_source'))
        with self.assertRaises(WorkflowError):authorize_repair(path,proposal,'unauthorized')
        proposal['authorization']={'approved':True,'actor_id':'fixture-user','reason':'Explicitly repair the selected working tree.',
            'proposal_hash':proposal['proposal_hash'],'provenance':{'kind':'user-message','ref':'fixture:repair-choice'}}
        authorize_repair(path,proposal,'authorize')
        subject=read_session(path)['subject'];self.assertTrue(subject['editable_source'])
        self.assertEqual(Path(subject['repositories']['repo-1']['location']),repo.resolve())
        self.assertEqual((repo/'value.py').read_bytes(),before);self.assertNotIn('plan',subject)
        self.assertTrue(authorize_repair(path,proposal,'authorize')['replayed'])
    def test_changed_editable_source_requires_fresh_proposal(self):
        from test_standalone_review import StandaloneReviewTests
        from workflow_lib.session_repair import prepare_repair,authorize_repair
        case=StandaloneReviewTests();self.addCleanup(case.doCleanups)
        base,repo,path=case.model_fixture();proposal=prepare_repair(path,{'implementer_actor':'writer','protection_paths':['AGENTS.md']})
        proposal['authorization']={'approved':True,'actor_id':'fixture-user','reason':'Explicit selected scope.',
            'proposal_hash':proposal['proposal_hash'],'provenance':{'kind':'user-message','ref':'fixture:choice'}}
        (repo/'value.py').write_text('unexpected')
        with self.assertRaises(WorkflowError):authorize_repair(path,proposal,'authorize')

    def owned_session(self,always_pass=False,spending_limit=20):
        import json,subprocess,tempfile,time
        from workflow_lib.standalone_reviews import start_standalone
        from workflow_lib.review_sessions import read_session,transact_session
        from workflow_lib.session_evidence import prepare,record_review
        from workflow_lib.session_repair import prepare_repair,authorize_repair
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();path=base/'session.db'
        for args in (['init','-q'],['config','user.name','Owned'],['config','user.email','owned@example.invalid']):subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'app.py').write_text('VALUE = 60\n');(repo/'AGENTS.md').write_text('Preserve the supplied retention rule.\n')
        test="""import json,sys,runpy
sys.dont_write_bytecode=True
ok=runpy.run_path('app.py')['VALUE']==30
print(json.dumps({'schema':'devflow-test-report-v2','tests':[{'id':'retention','outcome':'passed' if ok else 'failed','failure_phase':None if ok else 'test-assertion'}]}))
raise SystemExit(0 if ok else 1)
"""
        if always_pass:test=test.replace("ok=runpy.run_path('app.py')['VALUE']==30",'ok=True')
        (repo/'test.py').write_text(test)
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','Owned defect'],cwd=repo,check=True)
        start_standalone(repo,{'mode':'working-tree','intent':[{'id':'retention','text':'Return exactly thirty days.'}],
            'verification':{'repo_id':'repo-1','input_paths':['test.py'],'target_ids':['retention'],'argv':[sys.executable,'test.py'],
                'report_format':'json','authority_refs':['fixture:user-rule:30']}},path)
        def event(op,action,record):
            state=read_session(path);return transact_session(path,state['version'],op,{'action':action,'record':record})
        event('budget','configure-effects',{'max_attempts':20,'max_estimated_cost':20,'max_elapsed_ms':120000,
            'authorization':{'approved':True,'actor_id':'fixture-user'}})
        package=prepare(path,'initial-package')
        # Declared user-observed defect, explicitly diagnostic/unvalidated; never approval.
        record_review(path,{'package_hash':package['package_hash'],'actor_id':'fixture-observer','invocation_ref':'fixture:inspection',
            'perspective':'code','verdict':'request-changes','diagnostic':True,'findings':[{'id':'retention-bug','severity':'important','path':'app.py','line':1,
                'failure_scenario':'The actual selected module returns sixty.','impact':'Wrong user retention rule.',
                'requested_correction':'Return the supplied thirty-day rule.','evidence_refs':['repo-1:app.py:1']} ]},'initial-finding')
        proposal=prepare_repair(path,{'implementer_actor':'writer','protection_paths':['AGENTS.md','test.py']})
        proposal['authorization']={'approved':True,'actor_id':'fixture-user','reason':'Repair this exact owned working tree and preserve tests.',
            'proposal_hash':proposal['proposal_hash'],'provenance':{'kind':'user-message','ref':'fixture:repair'}}
        authorize_repair(path,proposal,'authorize')
        subject=read_session(path)['subject'];authority='intent:'+subject['review_contract_hash']+'#retention'
        contract={'scope':{'role':'session'},'source_identity':subject['source_identity'],
            'behaviors':[{'id':'retention','text':'Return exactly thirty days.','authority_refs':[authority],'target_ids':['retention'],
                'incorrect_behaviors':['Return sixty days.']}],'invariants':['Keep the independent thirty-day assertion.'],'interfaces':['VALUE'],
            'non_goals':['Changing the rule.'],'neighboring_disposition':{'applicability':'not-applicable','reason':'Owned fixture exposes one constant without callers or storage.',
                'evidence_refs':['repo-1:app.py']}}
        event('contract','implementation-contract',contract)
        subject=read_session(path)['subject'];policy={'protocol':'devflow.review-orchestration/v1','schema_version':1,'enabled':True,
            'max_attempts':3,'max_elapsed_ms':120000,'max_estimated_cost':spending_limit,'no_progress_window':2,'effect_policy_hash':digest(subject['effect_policy'])}
        event('orchestration','orchestration-configure',{'policy':policy,'now_ms':int(time.time()*1000),'authorization':{
            'approved':True,'actor_id':'fixture-user','policy_hash':digest(policy),'provenance':{'kind':'user-message','ref':'fixture:finite-loop'}}})
        request={'session':True,'implementer':{'host':'codex','actor_id':'writer','estimated_cost':1},
            'reviewers':{p:{'host':'codex','actor_id':'review-'+p,'estimated_cost':1} for p in ('code','test','architecture','security')},
            'rationales':{'retention-bug':{'observed_failure':'Actual selected constant is sixty; user rule is thirty.','evidence_refs':['finding:retention-bug'],
                'cause':{'kind':'hypothesis','text':'The constant is the source of the incorrect returned value.'},'correction':'Set the constant to thirty.',
                'why':'The same public constant is checked by the independent thirty-day regression.'}}}
        return base,repo,path,request
    def transport(self,path,base,*,crash=False,wrong=False):
        import json,subprocess
        from test_review_dispatch import ReviewDispatchTests
        from workflow_lib.review_sessions import read_session
        from workflow_lib.storage_access import read_current
        from workflow_lib.adversarial_reviews import review_input_id
        from workflow_lib.implementation_contracts import contract_binding
        from workflow_lib.finding_closure import finding_hash
        fixture=ReviewDispatchTests();policy=fixture.policy();policy['stages']['implementation']='efficient-coding'
        policy['profiles']['efficient-coding']={'effort':'high'}
        policy['hosts']['codex']['efficient-coding']=copy.deepcopy(policy['hosts']['codex']['deep-reasoning'])
        class Controlled:
            def __init__(self,project):self.project=Path(project)
            def identity(self):return {'account_key':'owned-driver-fixture','cacheable':True}
            def configure(self,resolved,brief,access='read-only'):return {'observed':resolved,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configured'}
            def discover(self):return {'capabilities':fixture.capabilities(),'discovery':fixture.discovery()}
            def invoke(self,resolved,prompt,actor,access,timeout):
                if actor=='writer':
                    assert access=='workspace-write'
                    incorrect=wrong is True or (wrong=='once' and not (base/'worker-count').exists())
                    script='from pathlib import Path; p=Path('+repr(str(base/'worker-count'))+'); p.write_text(p.read_text()+"x" if p.exists() else "x"); Path("app.py").write_text('+repr('VALUE = 60\n' if incorrect else 'VALUE = 30\n')+'); print("Actual owned correction")'
                    child=subprocess.run([sys.executable,'-c',script],cwd=self.project,capture_output=True,text=True,check=True)
                    if crash:
                        from workflow_lib.native_models import NativeError
                        raise NativeError('unavailable','Owned child completed without a model completion receipt.')
                    output=child.stdout
                else:
                    assert access=='read-only'
                    subject=read_session(path)['subject'] if Path(path).is_file() else read_current(path,run_id='run')['data']['runs']['run']
                    supplied=(json.loads(prompt.rsplit('\n',1)[-1])['review_input'] if Path(path).is_file() else
                        json.loads(prompt.split('\nScoped authoritative brief:\n',1)[1].split('\nTask:\n',1)[0])['review_input'])
                    package=json.loads(Path(supplied['artifact_ref']).read_text())['value']['package']
                    assert supplied['artifact_id']==review_input_id(package)
                    perspective=actor.removeprefix('review-');green=[p for p in subject['verification_proofs'].values() if p['phase']=='GREEN'][-1]
                    red=subject['verification_proofs'][green['red_proof_id']] if green.get('red_proof_id') else next(p for p in subject['verification_proofs'].values() if p['phase']=='RED' and p['source_identity']==green['integrity']['baseline_source'])
                    scope={'role':'session'} if Path(path).is_file() else {'role':package['role'],'item_id':'W1'}
                    authority=subject['implementation_contracts']['session' if Path(path).is_file() else 'item:W1']['behaviors'][0]['authority_refs']
                    report={'verdict':'pass','findings':[],'reviewed_inputs':package['review_inputs'],'review_input_ref':review_input_id(package),
                        'closure_dispositions':[{'finding_id':f['id'],'finding_hash':finding_hash(f),'source_identity':subject['source_identity'],
                            'obligations':f['obligations'],'disposition':'resolved','proof_ids':[green['id']],
                            'proof_applicability':{green['id']:f['obligations']}} for f in subject['unresolved_findings'] if f.get('status')=='open']}
                    if not Path(path).is_file():report['item_id']='W1'
                    if perspective=='code' and scope['role'] in {'session','branch'}:report['risk_confirmation']={'assessment_hash':package['review_requirements']['assessment_hash'],
                        'disposition':'conservative','reason':'Unknown dependency/trust impact retains all perspectives.','evidence_refs':['package:'+package['package_hash']]}
                    if perspective=='test':
                        report['test_oracles']=[{'red_proof_id':red['id'],'green_proof_id':green['id'],'input_hashes':green['integrity']['contract']['input_hashes'],
                            'authority_refs':['fixture:user-rule:30'],'failure_relevance':'The actual thirty-day assertion fails for sixty and passes for thirty.'}]
                        report['test_quality']={'contract_binding':contract_binding(subject,scope),'limitations':[],
                            'behaviors':[{'id':'retention','authority_refs':authority,'oracle_kind':'actual-user-decision',
                                'oracle_rationale':'The supplied user rule independently fixes the expected value at thirty.',
                                'assertions':[{'target_id':'retention','input_path':'test.py','assertion_ref':'test.py:3'}],
                                'incorrect_behaviors':[{'text':'Return sixty days.','failure_relevance':'The same relevant assertion failed at sixty.',
                                    'red_proof_id':red['id'],'green_proof_id':green['id'],'target_ids':['retention']}]}]}
                    if perspective=='test' and not Path(path).is_file():
                        oracle=report['test_oracles'][0];oracle.update(item_id='W1',target_ids=green['integrity']['contract']['targets'],
                            clarification_binding=green['integrity']['contract']['clarification_binding'],authority_refs=authority,
                            rationale='The approved thirty-day rule supplies the oracle independently of implementation.')
                    output=subprocess.run([sys.executable,'-c','import sys; print(sys.argv[1])',json.dumps(report)],capture_output=True,text=True,check=True).stdout
                return {'status':'completed','observed':resolved,'observation_source':'host-invocation-metadata','invocation_ref':'fixture:actual-'+actor,'output':output}
            def close(self):pass
        return policy,Controlled
    def test_actual_red_fix_green_independent_closure(self):
        from unittest.mock import patch
        from workflow_lib.review_sessions import read_session
        base,repo,path,request=self.owned_session();policy,backend=self.transport(path,base)
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',backend):
            result=self.api().run_orchestration(path,request,'complete-repair',30)
        subject=read_session(path)['subject']
        self.assertEqual(subject['unresolved_findings'][0]['status'],'resolved',result)
        self.assertEqual(subject['completion']['outcome'],'verified-repair',result)
        self.assertEqual((repo/'app.py').read_text(),'VALUE = 30\n');self.assertEqual((base/'worker-count').read_text(),'x')
        self.assertEqual({p['phase'] for p in subject['verification_proofs'].values()},{'RED','GREEN'})
        self.assertEqual({r['perspective'] for r in subject['reviews']['session'] if r.get('fresh') is not False},{'code','test','architecture','security'})
    def test_always_passing_regression_does_not_launch_writer(self):
        from unittest.mock import patch
        base,repo,path,request=self.owned_session(always_pass=True);policy,backend=self.transport(path,base)
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',backend):
            result=self.api().run_orchestration(path,request,'bad-regression',10)
        self.assertFalse((base/'worker-count').exists(),result);self.assertEqual((repo/'app.py').read_text(),'VALUE = 60\n')
    def test_crash_after_launch_never_dispatches_replacement(self):
        from unittest.mock import patch
        base,repo,path,request=self.owned_session();policy,backend=self.transport(path,base,crash=True)
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',backend):
            first=self.api().run_orchestration(path,request,'crash-run',10)
            again=self.api().run_orchestration(path,request,'crash-run',10)
            self.api().run_orchestration(path,request,'new-operation',10)
        self.assertEqual((base/'worker-count').read_text(),'x',again)
        self.assertIsNone(first['steps'][-1]['executed'],'An uncertain launch cannot be reported as zero execution.')

    def test_source_change_before_effect_prevents_launch(self):
        from unittest.mock import patch
        from workflow_lib.review_sessions import read_session
        base,repo,path,request=self.owned_session();policy,backend=self.transport(path,base)
        self.api().advance_orchestration(path,request,'red')
        self.api().advance_orchestration(path,request,'rationale')
        class Drift(backend):
            def discover(self):
                result=super().discover();(repo/'app.py').write_text('VALUE = 99\n');return result
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',Drift):
            result=self.api().advance_orchestration(path,request,'drift')
        self.assertFalse((base/'worker-count').exists(),result)
        self.assertFalse(result['advanced']);self.assertEqual(read_session(path)['subject']['effects']['drift:effect:worker']['status'],'failed')
    def test_shared_action_has_one_real_process_winner(self):
        import subprocess,json
        from workflow_lib.review_sessions import read_session
        base,repo,path,request=self.owned_session()
        # Both real helpers compete for the same durable verifier step while
        # the winner holds the lease; the counter stays outside reviewed inputs.
        marker=base/'shared-counter';launcher=base/'helper.py';request_path=base/'request.json';request_path.write_text(json.dumps(request))
        launcher.write_text('''import json,sys,time
from pathlib import Path
sys.path.insert(0,SCRIPTS)
from workflow_lib import review_driver
original=review_driver._execute
def slow(*args):
 Path(MARKER).write_text(Path(MARKER).read_text()+'x' if Path(MARKER).exists() else 'x')
 time.sleep(0.5)
 return original(*args)
review_driver._execute=slow
print(json.dumps(review_driver.advance_orchestration(Path(SESSION),json.loads(Path(REQUEST).read_text()),'shared')))
'''.replace('SCRIPTS',repr(str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))).replace('MARKER',repr(str(marker))).replace('SESSION',repr(str(path))).replace('REQUEST',repr(str(request_path))))
        children=[subprocess.Popen([sys.executable,str(launcher)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        responses=[]
        for child in children:
            stdout,stderr=child.communicate(timeout=20);self.assertEqual(child.returncode,0,stdout+stderr);responses.append(json.loads(stdout))
        self.assertEqual(marker.read_text(),'x');self.assertEqual(sum(r.get('advanced') is True for r in responses),1)
        self.assertEqual(len(read_session(path)['subject']['verification_proofs']),1)

    def owned_workflow(self,layout,*,gate_only=False,gate_mapping=True):
        import subprocess,time
        from workflow_lib import store,sqlite_store
        from control_store_fixtures import legacy_root
        from test_hosts import host_state,attachment
        from workflow_lib.hosts import apply_host_event
        from workflow_lib.enforcement_live import source_observation
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.review_policy import new_review_policy
        from workflow_lib.implementation_contracts import record_implementation_contract
        from workflow_lib.review_orchestration import apply_orchestration
        base,repo,session,unused=self.owned_session();root=base/'control'
        (legacy_root if layout==1 else sqlite_store.initialize_store)(root)
        data=host_state(str(repo.resolve()))
        from workflow_lib.specs import content_hash
        data['spec']['requirements'][0]['text']='Return exactly thirty days.'
        data['approval']['content_hash']=content_hash(data['spec'])
        data['runs']['run']['plan']['spec_hash']=data['approval']['content_hash']
        run=data['runs']['run'];run.update(state_version=1,review_policy=new_review_policy(),
            enforcement={'protocol':'devflow.python-enforcement/v1','policy_version':1},actors={'implementer':'writer'},
            active_attempt={'item_id':'W1','token':'t','status':'active','result':None,'state_version':1},
            effect_policy={'max_attempts':20,'max_estimated_cost':20,'max_elapsed_ms':120000},effects={},repair_cycles=[],
            governing_digest='fixture-governing',review_ids=[],adjudication_ids=[],reviews={},review_packages={},acceptances=[],
            available_gates=['context','specification','planning','build','review','acceptance'],unavailable_gates=[],artifacts={},
            unresolved_findings=[{'id':'retention-bug','item_id':'W1','severity':'important',
                'status':'open','mandatory':True,'required_perspectives':['code'],'obligations':['retention'],
                'failure_scenario':'Actual constant returns sixty.','impact':'User rule requires thirty.','requested_correction':'Use thirty.',
                'provenance':{'kind':'fixture-user-message','ref':'fixture:rule30'}}])
        run['items']['W1']['attempts']=[copy.deepcopy(run['active_attempt'])]
        item=run['plan']['work_items'][0];item.update(repo_id='repo',dependencies=[],verification_inputs=['test.py'],verification_target_ids=['retention'],
            acceptance_criteria=[{'kind':'code-test','text':'Return thirty.'}])
        run.update(source_observation=source_observation(run));run['source_identity']=run['source_observation']['source_identity']
        inventory={'paths':['AGENTS.md','test.py'],'governing_digest':run['governing_digest']}
        run['protected_inventories']={'repo':{'inventory':inventory,'baseline':snapshot_protected(repo,inventory)}}
        contract={'scope':{'role':'item','item_id':'W1'},'source_identity':run['source_identity'],
            'behaviors':[{'id':'retention','text':'Return thirty days.','authority_refs':['spec:'+run['plan']['spec_hash']+'#R1'],
                'target_ids':['retention'],'incorrect_behaviors':['Return sixty.']}],'invariants':['Preserve independent assertions.'],
            'interfaces':['VALUE'],'non_goals':['Changing the rule.'],'neighboring_disposition':{'applicability':'not-applicable',
                'reason':'Single constant with no callers/storage in the owned fixture.','evidence_refs':['fixture:app.py']}}
        if gate_only:
            run['unresolved_findings']=[]
            gate_script='import sys,runpy; from pathlib import Path; sys.dont_write_bytecode=True; p=Path('+repr(str(base/'gate-counter'))+'); p.write_text(p.read_text()+"x" if p.exists() else "x"); sys.exit(0 if runpy.run_path("app.py")["VALUE"]==30 else 1)'
            gate={'repo_id':'repo','kind':'lint','pre_review':True,'command':[sys.executable,'-B','-c',gate_script],'contract':{'kind':'exit-status'}}
            if gate_mapping:gate['item_ids']=['W1']
            run.update(required_hardening_gates=['lint'],hardening_config={'lint':gate},hardening_config_hash=digest({'lint':gate}),hardening_proofs={})
        run=record_implementation_contract(run,contract)
        policy={'protocol':'devflow.review-orchestration/v1','schema_version':1,'enabled':True,'max_attempts':3,
            'max_elapsed_ms':120000,'max_estimated_cost':20,'no_progress_window':2,'effect_policy_hash':digest(run['effect_policy'])}
        run=apply_orchestration(run,'configure',{'policy':policy,'now_ms':int(time.time()*1000),'authorization':{'approved':True,
            'actor_id':'fixture-user','policy_hash':digest(policy),'provenance':{'kind':'user-message','ref':'fixture:finite-loop'}}})
        data['runs']['run']=run;apply_host_event(data,'attach',attachment(project=str(repo.resolve()),binding_id='writer',actor_id='writer'))
        store.transact(root,0,'owned-current-fixture',{'kind':'fixture','payload':data})
        head=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,capture_output=True,text=True,check=True).stdout.strip()
        request={'run_id':'run','verification':{'argv':[sys.executable,'test.py'],'input_paths':['test.py'],'target_ids':['retention']},
            'repositories':{'repo':{'location':str(repo.resolve()),'base':head,'head':head}},
            'implementer':{'binding_id':'writer','revision':1,'estimated_cost':1},'rationales':unused['rationales']}
        if gate_only:
            rationale=copy.deepcopy(unused['rationales']['retention-bug'])
            rationale.update(observed_failure='The explicitly configured lint criterion rejects the current source.',evidence_refs=['gate:lint'])
            request['rationales']={'gate:lint':rationale}
        return base,repo,root,request
    def workflow_baseline(self,layout):
        from workflow_lib.storage_access import read_current
        base,repo,root,request=self.owned_workflow(layout)
        result=self.api().advance_orchestration(root,request,'baseline')
        self.assertTrue(result['advanced'],result)
        run=read_current(root,run_id='run')['data']['runs']['run'];proof=run['verification_proofs'][result['result_ref']]
        self.assertEqual(proof['phase'],'RED');self.assertEqual(proof['target_outcomes']['retention'],'failed')
        self.assertEqual(len(run['review_orchestration']['cycles']),1)
    def test_workflow_format1_executes_owned_red(self):self.workflow_baseline(1)
    def test_workflow_format2_executes_owned_red(self):self.workflow_baseline(2)

    def workflow_repair(self,layout):
        from unittest.mock import patch
        from workflow_lib.storage_access import read_current
        base,repo,root,request=self.owned_workflow(layout);policy,backend=self.transport(root,base)
        request['reviewers']={'item':{p:{'host':'codex','binding_id':'review-'+p,'actor_id':'review-'+p,
            'session_id':'session-'+p,'estimated_cost':1} for p in ('code','test','architecture','security')}}
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.native_runtime.CodexBackend',backend):
            result=self.api().run_orchestration(root,request,'workflow-repair',30)
        run=read_current(root,run_id='run')['data']['runs']['run']
        self.assertEqual(run['unresolved_findings'][0]['status'],'resolved',result)
        self.assertEqual(run['items']['W1']['status'],'complete',result)
        self.assertEqual((base/'worker-count').read_text(),'x')
        self.assertEqual({r['perspective'] for r in run['reviews']['item'] if r.get('fresh') is not False},{'code','test','architecture','security'})
        self.assertNotEqual(result['status'],'complete');self.assertEqual(result['next_action']['scope']['role'],'branch',result)
        for receipt in run['model_receipts'].values():
            if receipt.get('dispatch') is True:
                self.assertIsInstance(receipt.get('started_ms'),int);self.assertGreaterEqual(receipt.get('finished_ms'),receipt['started_ms'])
    def test_workflow_format1_real_repair_preserves_final_gates(self):self.workflow_repair(1)
    def test_workflow_format2_real_repair_preserves_final_gates(self):self.workflow_repair(2)

    def test_spending_limit_blocks_writer_before_any_model_turn(self):
        from unittest.mock import patch
        base,repo,path,request=self.owned_session(spending_limit=0);policy,backend=self.transport(path,base)
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',backend):
            result=self.api().run_orchestration(path,request,'zero-model-budget',10)
        self.assertFalse((base/'worker-count').exists(),result)
    def test_clarification_during_worker_blocks_green_and_returns_question(self):
        from unittest.mock import patch
        from workflow_lib.review_sessions import read_session,transact_session
        from workflow_lib.document_units import digest
        base,repo,path,request=self.owned_session();policy,backend=self.transport(path,base)
        class Question(backend):
            def invoke(self,*args):
                result=super().invoke(*args)
                if args[2]=='writer':
                    state=read_session(path);subject=state['subject']
                    transact_session(path,state['version'],'actual-question',{'action':'question','record':{'id':'rule','text':'Which retention rule applies?',
                        'scope':None,'source_identity':subject['source_identity'],'contract_hash':subject['review_contract_hash']}})
                return result
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',Question):
            result=self.api().run_orchestration(path,request,'question-run',20)
        self.assertEqual(result['next_action']['kind'],'ask-user',result)
        self.assertIn('Which retention rule applies?',str(result['next_action']))
        self.assertFalse(any(p['phase']=='GREEN' for p in read_session(path)['subject']['verification_proofs'].values()))
    def test_stopped_driver_recovers_actual_proof_without_reexecution(self):
        import json,subprocess
        from workflow_lib.review_sessions import read_session
        base,repo,path,request=self.owned_session();helper=base/'stop-driver.py';input_=base/'input.json';input_.write_text(json.dumps(request));marker=base/'one'
        helper.write_text('''import sys,json,os
from pathlib import Path
sys.path.insert(0,SCRIPTS)
from workflow_lib import review_driver
original=review_driver._execute
def stopped(*args):
 result=original(*args)
 Path(MARKER).write_text('one')
 os._exit(23)
review_driver._execute=stopped
review_driver.advance_orchestration(Path(SESSION),json.loads(Path(INPUT).read_text()),'stopped')
'''.replace('SCRIPTS',repr(str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))).replace('MARKER',repr(str(marker))).replace('SESSION',repr(str(path))).replace('INPUT',repr(str(input_))))
        child=subprocess.run([sys.executable,str(helper)],capture_output=True,text=True,timeout=15)
        self.assertEqual(child.returncode,23,child.stdout+child.stderr)
        retry=self.api().advance_orchestration(path,request,'stopped');self.assertEqual(retry['kind'],'reconcile')
        self.assertIsNone(retry['executed'],'A retained outstanding operation cannot claim definite nonexecution.')
        self.assertEqual(len(read_session(path)['subject']['verification_proofs']),1)
        with self.assertRaises(WorkflowError):self.api().recover_orchestration(path,{**request,'original_operation_id':'stopped','worker_stop_confirmation':{}},'bad-recovery')
        confirmation={'approved':True,'actor_id':'fixture-user','worker_ref':'stopped','reason':'Owned coordinator and all children stopped.',
            'provenance':{'kind':'user-message','ref':'fixture:stop'}}
        result=self.api().recover_orchestration(path,{**request,'original_operation_id':'stopped','worker_stop_confirmation':confirmation},'recover')
        self.assertEqual(result['next_action']['kind'],'rationale',result)
        self.assertEqual(len(read_session(path)['subject']['verification_proofs']),1)

    def test_failed_green_reenters_bounded_repair_without_reviewing_bad_candidate(self):
        from unittest.mock import patch
        from workflow_lib.review_sessions import read_session
        base,repo,path,request=self.owned_session();policy,backend=self.transport(path,base,wrong='once')
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',backend):
            result=self.api().run_orchestration(path,request,'two-corrections',40)
        subject=read_session(path)['subject']
        self.assertEqual(result['status'],'complete',result);self.assertEqual((base/'worker-count').read_text(),'xx')
        self.assertEqual(len(subject['review_orchestration']['cycles']),2)
        self.assertEqual(len([r for r in subject['model_receipts'].values() if r.get('scope',{}).get('role')=='session-reviewer']),4)
    def test_repeated_real_failed_green_stops_without_fake_progress(self):
        from unittest.mock import patch
        from workflow_lib.review_sessions import read_session
        base,repo,path,request=self.owned_session();policy,backend=self.transport(path,base,wrong=True)
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',backend):
            result=self.api().run_orchestration(path,request,'surviving-defect',40)
        self.assertEqual(result['next_action']['reason_code'],'NO_PROGRESS',result)
        from workflow_lib.review_summary import summarize_review
        self.assertEqual(summarize_review(read_session(path)['subject'])['no_progress_stops'],1)
        self.assertEqual((base/'worker-count').read_text(),'xx');self.assertNotIn('completion',read_session(path)['subject'])

    def test_registered_repository_redirect_cannot_change_executed_source(self):
        import subprocess,shutil
        from workflow_lib import store
        from workflow_lib.storage_access import read_current
        base,repo,root,request=self.owned_workflow(2);other=base/'other';shutil.copytree(repo,other)
        (other/'app.py').write_text('VALUE = 30\n')
        state=read_current(root,run_id='run')
        store.transact(root,state['version'],'redirect',{'kind':'repo.registered','payload':{'repositories':{'repo':{'location':str(other.resolve())}}}})
        self.assertEqual(read_current(root,run_id='run')['data']['repositories']['repo']['location'],str(other.resolve()))
        marker=base/'wrong-source-command'
        request['verification']['argv']=[sys.executable,'-c','from pathlib import Path; import runpy; Path('+repr(str(marker))+').write_text("ran"); runpy.run_path("test.py",run_name="__main__")']
        result=self.api().advance_orchestration(root,request,'wrong-repository')
        self.assertFalse(result['advanced'],result)
        self.assertFalse(marker.exists(),'A command ran against a repository different from the bound run source.')
        self.assertFalse(read_current(root,run_id='run')['data']['runs']['run'].get('verification_proofs'))
    def test_capture_retry_cannot_change_expected_source(self):
        from workflow_lib.evidence import capture_evidence
        from workflow_lib.storage_access import read_current
        base,repo,root,request=self.owned_workflow(2);result=self.api().advance_orchestration(root,request,'baseline')
        self.assertTrue(result['advanced'],result)
        with self.assertRaises(WorkflowError):capture_evidence(root,'run','t','RED',[sys.executable,'test.py'],['test.py'],['retention'],300,
            operation_id='baseline:effect',expected_source_identity='different-request-source')

    def test_known_failed_preflight_persists_until_explicit_retry(self):
        from unittest.mock import patch
        from workflow_lib.review_sessions import read_session
        from workflow_lib.review_orchestration import orchestration_next
        base,repo,path,request=self.owned_session(spending_limit=0);policy,backend=self.transport(path,base)
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',backend):
            result=self.api().run_orchestration(path,request,'blocked-writer',10)
            before=read_session(path)['subject']
            blocked=orchestration_next(before,self.api().now())
            self.assertEqual(blocked['kind'],'blocked',result)
            self.assertIn('explicit retry',str(blocked))
            repeated=self.api().advance_orchestration(path,request,'another-operation')
            self.assertFalse(repeated['advanced']);self.assertEqual(len(read_session(path)['subject']['review_orchestration']['driver_operations']),len(before['review_orchestration']['driver_operations']))
            retried=self.api().advance_orchestration(path,{**request,'resume':True},'explicit-retry')
            self.assertFalse(retried['advanced']);self.assertFalse((base/'worker-count').exists())

    def competing_writers(self,layout):
        import json,subprocess
        from workflow_lib.review_sessions import read_session
        from workflow_lib.storage_access import read_current
        base,repo,location,request=self.owned_session() if layout=='session' else self.owned_workflow(layout)
        self.api().advance_orchestration(location,request,'baseline')
        self.api().advance_orchestration(location,request,'rationale')
        request_path=base/'competing-request.json';request_path.write_text(json.dumps(request));gate=base/'start-writers'
        script='''import json,sys,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,sys.argv[1]);from test_review_driver import ReviewDriverTests
from workflow_lib.review_driver import advance_orchestration
location=Path(sys.argv[2]);base=Path(sys.argv[3]);request=json.loads(Path(sys.argv[4]).read_text())
case=ReviewDriverTests();policy,backend=case.transport(location,base)
class Slow(backend):
 def invoke(self,*args):
  time.sleep(.5)
  return super().invoke(*args)
while not Path(sys.argv[5]).exists():time.sleep(.01)
with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.native_runtime.CodexBackend',Slow),patch('workflow_lib.session_models.CodexBackend',Slow):
 print(json.dumps(advance_orchestration(location,request,'one-writer')))
'''
        children=[subprocess.Popen([sys.executable,'-c',script,str(Path(__file__).parent.resolve()),str(location),str(base),str(request_path),str(gate)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
        try:
            gate.touch()
            for child in children:
                out,err=child.communicate(timeout=30);self.assertEqual(child.returncode,0,out+err)
            subject=read_session(location)['subject'] if layout=='session' else read_current(location,run_id='run')['data']['runs']['run']
            self.assertEqual((base/'worker-count').read_text(),'x')
            self.assertEqual(len(subject['effects']),1)
            self.assertEqual(sum(e['estimated_cost'] for e in subject['effects'].values()),1)
            self.assertEqual(len(subject['review_orchestration']['cycles']),1)
        finally:
            for child in children:
                if child.poll() is None:child.kill();child.communicate(timeout=5)
    def test_shared_writer_has_one_real_process_winner_standalone(self):self.competing_writers('session')
    def test_shared_writer_has_one_real_process_winner_workflow_format1(self):self.competing_writers(1)
    def test_shared_writer_has_one_real_process_winner_workflow_format2(self):self.competing_writers(2)

    def test_standalone_additional_inputs_are_live_captured_and_locked(self):
        from workflow_lib.review_sessions import read_session
        from workflow_lib.session_evidence import capture
        from workflow_lib import test_extensions
        base,repo,path,request=self.owned_session()
        (repo/'extra.txt').write_text('additional regression fixture')
        self.api().Subject(path,request).observe('observe-extra-input')
        self.assertTrue(callable(getattr(test_extensions,'admit_extension',None)))
        test_extensions.admit_extension(path,{'session':True,'input_paths':['extra.txt'],'target_ids':[],
            'reason':'Retain the extra regression fixture.'},'extra-input')
        red=capture(path,'RED','extra-red')
        self.assertEqual(set(red['integrity']['contract']['input_hashes']),{'test.py','extra.txt'})
        (repo/'extra.txt').write_text('weakened')
        self.api().Subject(path,request).observe('observe-weakened-input')
        with self.assertRaises(WorkflowError):capture(path,'RED','changed-extra-red')
        self.assertEqual(len(read_session(path)['subject']['verification_proofs']),1)

    def test_model_policy_change_during_preflight_prevents_real_writer(self):
        from unittest.mock import patch
        from workflow_lib.store import transact
        from workflow_lib.storage_access import read_current
        base,repo,root,request=self.owned_workflow(2);policy,backend=self.transport(root,base)
        self.api().advance_orchestration(root,request,'baseline');self.api().advance_orchestration(root,request,'rationale')
        class Drift(backend):
            def discover(self):
                result=super().discover();state=read_current(root,run_id='run')
                transact(root,state['version'],'actual-model-restriction',{'kind':'domain.host.model-override','payload':{'request':{
                    'binding_id':'writer','revision':1,'mode':'strict','allowed_models':['unavailable-model']}}})
                return result
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.native_runtime.CodexBackend',Drift):
            result=self.api().advance_orchestration(root,request,'policy-drift')
        self.assertFalse((base/'worker-count').exists(),result);self.assertFalse(result['advanced'])

    def test_extension_cannot_change_test_contract_during_active_effect(self):
        from workflow_lib.test_extensions import record_extension
        from workflow_lib.clarifications import clarification_binding
        base,repo,path,request=self.owned_session()
        from workflow_lib.review_sessions import read_session
        from workflow_lib.test_extensions import session_item
        subject=read_session(path)['subject'];item=session_item(subject)
        record={'item_id':'session','token':subject['review_contract_hash'],'item_contract_hash':digest(item),
            'clarification_binding':clarification_binding(subject,{}),'source_identity':subject['source_identity'],
            'input_bindings':{'extra.py':{'sha256':'fixture-sha'}},'target_ids':['extra'],'reason':'Additional regression.'}
        subject['effects']={'worker':{'status':'running'}}
        with self.assertRaises(WorkflowError):record_extension(subject,record)
