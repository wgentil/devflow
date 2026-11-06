"""Contract/rationale/check prerequisites, with explicitly synthetic stored facts."""
import copy,importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError
from workflow_lib.review_policy import new_review_policy
from workflow_lib.document_units import digest

class ContractTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.implementation_contracts'))
        from workflow_lib import implementation_contracts
        return implementation_contracts
    def scope(self):return {'role':'item','item_id':'W1'}
    def subject(self):
        return {'id':'r','status':'active','state_version':1,'source_identity':'fixture-source',
            'enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1},'review_policy':new_review_policy(),
            'plan':{'spec_hash':'spec','work_items':[{'id':'W1','kind':'code','requirement_ids':['R1'],
                'dependencies':[],'verification_target_ids':['retention']}]},
            'items':{'W1':{'attempts':[{'token':'t'}]}},'unresolved_findings':[{'id':'f','item_id':'W1','status':'open','obligations':['R1']}]}
    def contract(self):
        return {'scope':self.scope(),'source_identity':'fixture-source',
            'behaviors':[{'id':'retention','text':'Return thirty days.','authority_refs':['spec:spec#R1'],
                'target_ids':['retention'],'incorrect_behaviors':['Return sixty days.']}],
            'invariants':['Never change existing records.'],'non_goals':['Changing pricing.'],'interfaces':['retention()'],
            'neighboring':[{'behavior':'Unrelated records remain unchanged.','reason':'Caller compatibility.',
                'evidence_refs':['spec:spec#R1'],'target_ids':['unchanged-records']}]}
    def ready(self):
        subject=self.api().record_implementation_contract(self.subject(),self.contract())
        subject['verification_proofs']={'green':{'id':'green','kind':'code','phase':'GREEN','item_id':'W1',
            'token':'t','source_identity':'fixture-source','passed':True,'fresh':True}}
        return subject
    def test_missing_implementation_contract_blocks_accepted_review(self):
        self.assertEqual(self.api().review_prerequisites(self.subject(),self.scope())['status'],'block')
    def test_recorded_derived_contract_and_current_raw_green_allow_prerequisites(self):
        subject=self.ready();result=self.api().review_prerequisites(subject,self.scope())
        self.assertEqual(result['status'],'allow',result)
        self.assertIn('contract_hash',subject['implementation_contracts']['item:W1'])
        self.assertEqual(result['not_configured'],['syntax','type','lint'])
        self.assertNotIn('implementation_contracts',self.subject())
    def test_missing_business_authority_returns_actual_pending_question(self):
        request=self.contract();request['behaviors'][0]['authority_refs']=[]
        request['question']='Which retention rule applies?'
        subject=self.api().record_implementation_contract(self.subject(),request)
        question=next(iter(subject['clarifications'].values()))
        self.assertEqual(question['text'],'Which retention rule applies?');self.assertEqual(question['status'],'pending')
        self.assertNotIn('implementation_contracts',subject)
        self.assertEqual(self.api().review_prerequisites(subject,self.scope())['questions'][0]['text'],question['text'])
    def test_changing_intended_behavior_requires_user_clarification_not_invention(self):
        subject=self.ready();request=self.contract();request['behaviors'][0]['text']='Return sixty days.'
        request['question']='Should retention change from thirty to sixty days?'
        updated=self.api().record_implementation_contract(subject,request)
        self.assertTrue(updated['clarifications'])
        self.assertEqual(updated['implementation_contracts'],subject['implementation_contracts'])
        self.assertEqual(self.api().review_prerequisites(updated,self.scope())['status'],'block')
    def test_material_answer_requires_actual_approved_amendment(self):
        from workflow_lib.clarifications import record_answer
        request=self.contract();request['behaviors'][0]['authority_refs']=[]
        subject=self.api().record_implementation_contract(self.subject(),request)
        question=next(iter(subject['clarifications'].values()))
        answered=record_answer(subject,{'id':question['id'],'question_version':question['version'],
            'answer':'Use the amended retention rule.','actor_id':'actual-user',
            'provenance':{'kind':'user-message','ref':'fixture:user-message'},'material':True,'spec_hash':'amended'})
        self.assertEqual(self.api().implementation_prerequisites(answered,self.scope())['status'],'block')
        self.assertTrue(self.api().implementation_prerequisites(answered,self.scope())['questions'])

    def test_neighboring_selection_requires_rationale_and_evidence(self):
        request=self.contract();request['neighboring']=[]
        subject=self.api().record_implementation_contract(self.subject(),request)
        self.assertIn('NEIGHBORING_BEHAVIOR_UNASSESSED',self.api().review_prerequisites(subject,self.scope())['reason_codes'])
        request['neighboring_disposition']={'applicability':'not-applicable','reason':'Fixture has no adjacent behavior.',
            'evidence_refs':['fixture:scope-inspection']}
        subject=self.api().record_implementation_contract(self.subject(),request)
        self.assertNotIn('NEIGHBORING_BEHAVIOR_UNASSESSED',self.api().review_prerequisites(subject,self.scope())['reason_codes'])
    def test_required_cheap_checks_block_pass_while_diagnostic_remains_possible(self):
        subject=self.ready();subject['hardening_config']={'lint':{'pre_review':True,'kind':'lint','repo_id':'repo','command':['configured-linter']}}
        subject['hardening_config_hash']=digest(subject['hardening_config'])
        result=self.api().review_prerequisites(subject,self.scope())
        self.assertEqual(result['status'],'block');self.assertIn('lint',result['missing_checks'])
        self.assertEqual(self.api().review_prerequisites(subject,{**self.scope(),'diagnostic':True})['status'],'allow')
        subject['hardening_proofs']={'lint':{'passed':False,'config_hash':subject['hardening_config_hash'],'source_identity':'fixture-source'}}
        self.assertEqual(self.api().review_prerequisites(subject,self.scope())['status'],'block')
        subject['hardening_proofs']['lint']['passed']=True
        self.assertEqual(self.api().review_prerequisites(subject,self.scope())['status'],'allow')
    def test_rationale_keeps_hypothesis_and_stales_on_contract_or_source_change(self):
        api=self.api();subject=self.ready();contract=subject['implementation_contracts']['item:W1']
        request={'finding_id':'f','scope':self.scope(),'contract_hash':contract['contract_hash'],
            'source_identity':'fixture-source','observed_failure':'Sixty differs from thirty.',
            'evidence_refs':['finding:f'],'cause':{'kind':'hypothesis','text':'Wrong default.'},
            'correction':'Use the documented default.','why':'It changes the incorrect return value.'}
        updated=api.record_fix_rationale(subject,request)
        self.assertEqual(updated['fix_rationales']['f']['cause']['kind'],'hypothesis')
        self.assertTrue(api.rationale_current(updated,'f'))
        updated['source_identity']='different-source';self.assertFalse(api.rationale_current(updated,'f'))
        with self.assertRaises(WorkflowError):api.record_fix_rationale(updated,request)
    def test_declared_checks_cannot_smuggle_new_commands_or_fake_authority(self):
        request=self.contract();request['checks']=[{'command':['invented-program']}]
        with self.assertRaises(WorkflowError):self.api().record_implementation_contract(self.subject(),request)
        request=self.contract();request['behaviors'][0]['authority_refs']=['spec:wrong#R1'];request['question']='What rule authorizes this?'
        updated=self.api().record_implementation_contract(self.subject(),request)
        self.assertTrue(updated['clarifications'])
    def test_unrelated_item_contract_does_not_invalidate_selected_contract(self):
        api=self.api();subject=self.ready();before=api.contract_binding(subject,self.scope())
        subject['implementation_contracts']['item:W2']={'contract_hash':'independent'}
        self.assertEqual(api.contract_binding(subject,self.scope()),before)
        self.assertNotEqual(api.contract_binding(subject,{'role':'branch'}),before)

    def test_public_contract_and_rationale_are_durable_and_exact_retry_is_effect_free(self):
        import json,subprocess,tempfile
        from workflow_lib import store
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));root=base/'control'
        store.transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':self.subject()}}})
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        request=base/'contract.json';request.write_text(json.dumps(self.contract()))
        argv=[sys.executable,str(entry),'review','contract','--root',str(root),'--run-id','r','--input',str(request),'--operation-id','contract']
        first=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        self.assertEqual(first.returncode,0,first.stdout+first.stderr)
        again=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        self.assertEqual(again.returncode,0,again.stdout+again.stderr);self.assertTrue(json.loads(again.stdout)['replayed'])
        self.assertIn('item:W1',store.read_state(root)['data']['runs']['r']['implementation_contracts'])

    def test_new_policy_worker_dispatch_requires_current_contract(self):
        from workflow_lib.action_policy import subject_decision
        self.assertEqual(subject_decision(self.subject(),'dispatch',{'item_id':'W1'})['status'],'block')
        subject=self.ready()
        self.assertEqual(subject_decision(subject,'dispatch',{'item_id':'W1'})['status'],'allow')
        subject['source_identity']='changed'
        self.assertEqual(subject_decision(subject,'dispatch',{'item_id':'W1'})['status'],'block')
        self.assertEqual(subject_decision(subject,'review-report',{'item_id':'W1'})['status'],'allow')

    def test_actual_configured_gate_checks_question_immediately_before_process(self):
        import argparse,json,subprocess,tempfile
        from unittest.mock import patch
        from workflow_lib import store
        from workflow_lib.enforcement_live import source_observation
        from workflow_lib.protected_changes import snapshot_protected
        from commands import harden
        for block in (False,True):
            with self.subTest(question_after_claim=block):
                base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();root=base/'control';marker=base/'executed'
                for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):
                    subprocess.run(['git',*args],cwd=repo,check=True)
                (repo/'code').write_text('owned source');subprocess.run(['git','add','.'],cwd=repo,check=True)
                subprocess.run(['git','commit','-qm','fixture'],cwd=repo,check=True)
                subject=self.subject();subject['plan']['work_items'][0]['repo_id']='repo';subject['repositories']={'repo':{'location':str(repo)}}
                subject['source_identity']=source_observation(subject)['source_identity'];subject['governing_digest']='fixture-governing'
                inv={'paths':[],'governing_digest':'fixture-governing'}
                subject['protected_inventories']={'repo':{'inventory':inv,'baseline':snapshot_protected(repo,inv)}}
                request=self.contract();request['source_identity']=subject['source_identity'];subject=self.api().record_implementation_contract(subject,request)
                subject['hardening_config']={'lint':{'pre_review':True,'kind':'lint','repo_id':'repo',
                    'command':[sys.executable,'-c',f'from pathlib import Path;Path({str(marker)!r}).write_text("executed")'],
                    'contract':{'kind':'exit-status'}}}
                subject['hardening_config_hash']=digest(subject['hardening_config'])
                store.transact(root,0,'seed',{'kind':'fixture','payload':{'repositories':subject['repositories'],'runs':{'r':subject}}})
                input_=base/'request.json';input_.write_text(json.dumps({'run_id':'r','gate_id':'lint'}))
                parsed=argparse.Namespace(root=str(root),operation='gate',input=str(input_),operation_id='gate',operation_id_explicit=True,expected_version=1)
                original=harden.commit
                def commit(*args,**kwargs):
                    result=original(*args,**kwargs)
                    if block and args[1]=='domain.harden.started':
                        current=store.read_state(root)
                        store.transact(root,current['version'],'late-question',{'kind':'domain.enforcement.question','payload':{'request':{
                            'run_id':'r','record':{'id':'q','text':'Which retention rule applies?','scope':['W1'],
                                'source_identity':subject['source_identity'],'spec_hash':'spec'}}}})
                    return result
                with patch.object(harden,'commit',side_effect=commit):
                    try:result=harden._dispatch(parsed)
                    except WorkflowError as exc:
                        if not block:raise
                        result={'passed':False,'failure':exc.code}
                self.assertEqual(marker.exists(),not block,'A post-claim question must prevent any process effect.')
                if not block:
                    proof=store.read_state(root)['data']['runs']['r']['hardening_proofs']['lint']
                    self.assertEqual(proof.get('source_identity'),subject['source_identity'])
                    self.assertEqual(proof.get('contract_binding'),self.api().contract_binding(subject,{'role':'branch'}))

    def test_crashed_tool_claim_cannot_authorize_duplicate_process_on_exact_retry(self):
        import json,subprocess,tempfile
        from workflow_lib import store
        from workflow_lib.enforcement_live import source_observation
        from workflow_lib.protected_changes import snapshot_protected
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();root=base/'control';counter=base/'counter'
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):
            subprocess.run(['git',*args],cwd=repo,check=True)
        subprocess.run(['git','commit','--allow-empty','-qm','fixture'],cwd=repo,check=True)
        subject=self.subject();subject['repositories']={'repo':{'location':str(repo)}};subject['source_identity']=source_observation(subject)['source_identity']
        subject['active_attempt']={'token':'t','item_id':'W1','state_version':1};subject['governing_digest']='g'
        inv={'paths':[],'governing_digest':'g'};subject['protected_inventories']={'repo':{'inventory':inv,'baseline':snapshot_protected(repo,inv)}}
        store.transact(root,0,'seed',{'kind':'fixture','payload':{'repositories':subject['repositories'],'runs':{'r':subject}}})
        script="""import os,sys,subprocess
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from workflow_lib.tool_execution import execution,started,ended,before_command
with execution(Path(sys.argv[2]),'r','t','owned-operation'):
 before_command();started()
 subprocess.run([sys.executable,'-c',"from pathlib import Path;p=Path("+repr(sys.argv[3])+");p.write_text(str((int(p.read_text()) if p.exists() else 0)+1))"],check=True)
 ended()
 if sys.argv[4]=='crash':os._exit(23)
"""
        args=[sys.executable,'-c',script,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'),str(root),str(counter)]
        first=subprocess.run([*args,'crash'],capture_output=True,text=True,timeout=30)
        self.assertEqual(first.returncode,23,first.stdout+first.stderr);self.assertEqual(counter.read_text(),'1')
        second=subprocess.run([*args,'retry'],capture_output=True,text=True,timeout=30)
        self.assertNotEqual(second.returncode,0,'An uncertain prior execution must block replacement.')
        self.assertEqual(counter.read_text(),'1','Replaying a claim is history, never permission for another process effect.')
