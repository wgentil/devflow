"""Owned public-command integration; native models and human messages are labeled fixtures."""
import contextlib,copy,io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))

class AdversarialIntegrationTests(unittest.TestCase):
    def case(self):
        from test_review_driver import ReviewDriverTests
        case=ReviewDriverTests();self.addCleanup(case.doCleanups);return case
    def cli(self,*args,expected=0):
        import run
        out=io.StringIO()
        with contextlib.redirect_stdout(out):code=run.main(list(map(str,args)))
        self.assertEqual(code,expected,out.getvalue());return json.loads(out.getvalue())
    def data(self,base,name,value):
        path=base/name;path.write_text(json.dumps(value));return path
    def session_event(self,path,action,record,operation):
        from workflow_lib.review_sessions import read_session
        state=read_session(path)
        source=self.data(path.parent,operation+'.json',{'action':action,'record':record})
        return self.cli('enforcement','session-event','--session',path,'--input',source,'--expected-version',state['version'],'--operation-id',operation)
    def test_workflow_review_repair_delivery_boundaries(self):
        from workflow_lib.storage_access import read_current
        case=self.case();base,repo,root,request=case.owned_workflow(2)
        scope=self.data(base,'scope.json',{'role':'item','item_id':'W1'})
        before=self.cli('review','coverage','--root',root,'--run-id','run','--input',scope)
        self.assertEqual(set(before['missing_perspectives']),{'code','test','architecture','security'})
        policy,backend=case.transport(root,base)
        request['reviewers']={'item':{p:{'host':'codex','binding_id':'review-'+p,'actor_id':'review-'+p,'session_id':'session-'+p,'estimated_cost':1} for p in ('code','test','architecture','security')}}
        source=self.data(base,'driver.json',request)
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.native_runtime.CodexBackend',backend):
            result=self.cli('repair','run','--root',root,'--run-id','run','--input',source,'--operation-id','public-repair','--max-actions',30)
        subject=read_current(root,run_id='run')['data']['runs']['run']
        self.assertEqual(subject['items']['W1']['status'],'complete',result)
        self.assertEqual(subject['unresolved_findings'][0]['status'],'resolved')
        self.assertEqual((base/'worker-count').read_text(),'x');self.assertEqual(len(subject['effects']),5)
        self.assertEqual(result['next_action']['scope']['role'],'branch');self.assertFalse(subject.get('delivery'))
        original=subject['reviews']['item'][0];count=len(subject['reviews']['item'])
        forged=self.cli('review','record','--root',root,'--run-id','run','--package-hash',original['package_hash'],
            '--actor-id','controller-forgery','--invocation-ref','fabricated-call','--report-json',json.dumps(original),
            '--model-invocation-id',original['model_invocation_id'],'--tool-available','--operation-id','forged-pass',expected=2)
        self.assertTrue(forged.get('error'));self.assertEqual(len(read_current(root,run_id='run')['data']['runs']['run']['reviews']['item']),count)

        blocked=self.cli('delivery','prepare','--root',root,'--run-id','run','--repositories-json',json.dumps(request['repositories']),'--outcome','retained-branch',expected=2)
        self.assertTrue(blocked.get('error'));self.assertFalse(read_current(root,run_id='run')['data']['runs']['run'].get('delivery'))
    def test_standalone_report_question_answer_and_authorized_repair(self):
        from workflow_lib.review_sessions import read_session
        case=self.case();base,repo,path,request=case.owned_session();subject=read_session(path)['subject']
        self.assertTrue(subject['standalone_scope_history']);self.assertTrue(subject['repair_authorization'])
        self.session_event(path,'question',{'id':'retention-question','scope':None,'text':'Confirm the existing thirty-day rule?',
            'source_identity':subject['source_identity'],'contract_hash':subject['review_contract_hash']},'actual-question')
        next_=self.cli('review','next','--session',path)
        self.assertEqual(next_['kind'],'ask-user');self.assertIn('Confirm the existing thirty-day rule?',str(next_))
        self.assertFalse((base/'worker-count').exists())
        self.session_event(path,'answer',{'id':'retention-question','question_version':1,'answer':'Keep thirty days.','actor_id':'fixture-user',
            'material':False,'contract_hash':subject['review_contract_hash'],'provenance':{'kind':'user-message','ref':'fixture:actual-answer'}},'actual-answer')
        policy,backend=case.transport(path,base);source=self.data(base,'driver.json',request)
        with patch('workflow_lib.native_runtime.policy',return_value=policy),patch('workflow_lib.session_models.CodexBackend',backend):
            result=self.cli('repair','run','--session',path,'--input',source,'--operation-id','public-session-repair','--max-actions',40)
        self.assertEqual(result['status'],'complete',result);self.assertEqual((base/'worker-count').read_text(),'x')
        final=self.cli('review','report','--session',path)
        self.assertFalse(final['workflow_acceptance']);self.assertEqual(read_session(path)['subject']['completion']['outcome'],'verified-repair')
    def test_both_formats_replay_without_live_observation(self):
        from workflow_lib import store
        case=self.case()
        for layout in (1,2):
            base,repo,root,request=case.owned_workflow(layout)
            source=self.data(base,'driver.json',request)
            first=self.cli('repair','run','--root',root,'--run-id','run','--input',source,'--operation-id','one-red','--max-actions',1)
            self.assertTrue(first['steps'][0]['advanced']);before=store.read_state(root)
            with patch('workflow_lib.enforcement_live.source_observation',side_effect=AssertionError('Historical replay must not inspect present-day source')):
                self.assertEqual(store.read_state(root),before)
                again=self.cli('repair','run','--root',root,'--run-id','run','--input',source,'--operation-id','one-red','--max-actions',1)
            self.assertTrue(again['steps'][0]['replayed']);self.assertEqual(len(store.read_state(root)['data']['runs']['run']['verification_proofs']),1)
    def test_policy_or_risk_change_cannot_reuse_a_pass(self):
        from test_review_summary import ReviewSummaryTests
        from workflow_lib.review_summary import review_reuse
        fixture=ReviewSummaryTests()
        fixture.test_changed_scope_or_compliance_cannot_reuse()
        subject,package,reports=fixture.fixture()
        self.assertTrue(review_reuse(subject,package,reports[0])['reusable'])
    def test_material_answer_cannot_reuse_an_older_contract_approval(self):
        from workflow_lib.review_sessions import read_session
        from workflow_lib.clarifications import record_question,record_answer,clarification_blockers
        case=self.case();base,repo,path,request=case.owned_session();subject=read_session(path)['subject']
        subject['contract_approval']={'content_hash':subject['review_contract_hash'],'authorization':{'approved':True,'provenance':{'kind':'user-message','ref':'fixture:previous-approval'}}}
        subject=record_question(subject,{'id':'change','scope':None,'text':'Change retention to ninety days?',
            'source_identity':subject['source_identity'],'contract_hash':subject['review_contract_hash']})
        asked=copy.deepcopy(subject)
        subject=record_answer(subject,{'id':'change','question_version':1,'answer':'Use ninety days.','actor_id':'fixture-user',
            'material':True,'contract_hash':subject['review_contract_hash'],'provenance':{'kind':'user-message','ref':'fixture:actual-material-answer'}})
        self.assertTrue(clarification_blockers(subject,{}),'A material change needs an actual amended/approved contract, not the prior approval.')

        from workflow_lib.document_units import digest
        from workflow_lib.enforcement_events import apply_enforcement
        amended=copy.deepcopy(asked['review_contract']['request']);amended['intent']='Return ninety days, as explicitly confirmed by the user.'
        contract_hash=digest({'scope':asked['review_contract']['scope'],'request':amended})
        answered=record_answer(asked,{'id':'change','question_version':1,'answer':'Use ninety days.','actor_id':'fixture-user',
            'material':True,'contract_hash':contract_hash,'provenance':{'kind':'user-message','ref':'fixture:actual-material-answer'}})
        self.assertTrue(clarification_blockers(answered,{}))
        approved=apply_enforcement(answered,'amend-review-contract',{'previous_contract_hash':asked['review_contract_hash'],
            'review_contract':amended,'authorization':{'approved':True,'actor_id':'fixture-user','reason':'Approve the actual ninety-day amendment.',
                'contract_hash':contract_hash,'provenance':{'kind':'user-message','ref':'fixture:actual-amendment-approval'}}})
        self.assertFalse(clarification_blockers(approved,{}))
        self.assertEqual(approved['review_contract']['request']['intent'],amended['intent'])
