"""Real owned experiments; structural quality fixtures are explicitly synthetic."""
import copy,hashlib,importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class ChallengeTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.test_challenges'))
        from workflow_lib import test_challenges
        return test_challenges
    def owned(self,mode='assertion'):
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir()
        (repo/'behavior.py').write_text('def retention(): return 30\n')
        (repo/'oracle.json').write_text('{"retention":30}')
        assertion={'assertion':'assert retention() == expected','always':'assert True',
            'setup':"raise ImportError('owned setup failure')",'skip':'pass'}[mode]
        script="""import json
from behavior import retention
expected=json.load(open('oracle.json'))['retention']
outcome='passed';phase=None
try:
    ASSERTION
except AssertionError: outcome='failed';phase='test-assertion'
except Exception: outcome='error';phase='setup'
print(json.dumps({'schema':'devflow-test-report-v2','tests':[{'id':'retention','outcome':outcome,'failure_phase':phase}]}))
raise SystemExit(0 if outcome=='passed' else 1)
""".replace('ASSERTION',assertion)
        (repo/'check.py').write_text(script)
        for args in (['init','-q'],['config','user.name','Owned'],['config','user.email','owned@example.invalid'],['add','.'],['commit','-qm','Owned fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        paths=['behavior.py','check.py','oracle.json']
        req={'schema_version':1,'source_paths':['behavior.py'],'input_paths':['check.py','oracle.json'],
            'input_hashes':{p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in paths},
            'replacements':[{'path':'behavior.py','before':'return 30','after':'return 60'}],
            'argv':[sys.executable,'-B','check.py'],'target_ids':['retention'],'report_format':'json',
            'timeout_seconds':5,'incorrect_behavior':'Return sixty days contrary to the independently authored fixture.',
            'authority_refs':['fixture:approved-thirty-day-rule']}
        return repo,req,base/'artifacts'
    def test_missing_discrimination_cannot_be_test_quality(self):
        with self.assertRaises(WorkflowError):self.api().validate_test_quality({'id':'fixture'},{},{'behaviors':[]})
    def test_relevant_wrong_behavior_is_detected(self):
        repo,req,out=self.owned();receipt=self.api().execute_challenge(repo,req,out)
        self.assertTrue(receipt['detected']);self.assertEqual(receipt['baseline']['exit_code'],0)
        self.assertEqual(receipt['changed']['classification']['retention'],'assertion')
        self.assertEqual(receipt['changed']['outcomes']['retention'],'failed')
        for run in ('baseline','changed'):
            self.assertTrue((out/receipt[run]['stdout_ref']).is_file())
    def test_surviving_incorrect_behavior_blocks_pass(self):
        repo,req,out=self.owned('always');receipt=self.api().execute_challenge(repo,req,out)
        self.assertFalse(receipt['detected']);self.assertEqual(receipt['disposition'],'survived')
    def test_setup_failure_is_not_detection(self):
        repo,req,out=self.owned('setup');receipt=self.api().execute_challenge(repo,req,out)
        self.assertFalse(receipt['detected']);self.assertEqual(receipt['disposition'],'baseline-unavailable')
    def test_challenge_never_changes_user_source(self):
        repo,req,out=self.owned();before={p:p.read_bytes() for p in repo.rglob('*') if p.is_file()}
        self.api().execute_challenge(repo,req,out)
        self.assertEqual(before,{p:p.read_bytes() for p in repo.rglob('*') if p.is_file()})
    def test_rejects_oracle_mutation_escape_noop_ambiguous_and_missing_inputs(self):
        for case in ('oracle','escape','noop','ambiguous','missing','stale','output-inside'):
            repo,req,out=self.owned()
            if case=='oracle':req['replacements'][0]['path']='oracle.json'
            if case=='escape':req['source_paths']=['../escape']
            if case=='noop':req['replacements'][0]['after']='return 30'
            if case=='ambiguous':req['replacements'][0]['before']='r'
            if case=='missing':req['input_paths']=[]
            if case=='stale':(repo/'oracle.json').write_text('{"retention":60}')
            if case=='output-inside':out=repo/'artifacts'
            with self.subTest(case=case),self.assertRaises(WorkflowError):self.api().execute_challenge(repo,req,out)
    def test_symlink_cannot_import_external_oracle(self):
        repo,req,out=self.owned();external=repo.parent/'secret';external.write_text('secret')
        (repo/'oracle.json').unlink();(repo/'oracle.json').symlink_to(external)
        with self.assertRaises(WorkflowError):self.api().execute_challenge(repo,req,out)

    def quality_fixture(self):
        from test_oracle_acceptance import OracleAcceptanceTests
        from workflow_lib.review_policy import new_review_policy
        from workflow_lib.implementation_contracts import record_implementation_contract,contract_binding
        subject,package,review=OracleAcceptanceTests().fixture()
        subject.update(status='active',review_policy=new_review_policy())
        subject=record_implementation_contract(subject,{'scope':{'role':'item','item_id':'W1'},'source_identity':'after',
            'behaviors':[{'id':'retention','text':'Use the independent retention rule.','target_ids':['t'],
                'authority_refs':['spec:spec#R1']}],'invariants':[],'interfaces':[],'non_goals':[],
            'neighboring_disposition':{'applicability':'not-applicable','reason':'Isolated fixture.','evidence_refs':['fixture:scope']}})
        review['test_quality']={'contract_binding':contract_binding(subject,{'role':'item','item_id':'W1'}),
            'limitations':['Synthetic structural proof; live runtime is tested separately.'],'behaviors':[{
                'id':'retention','authority_refs':['spec:spec#R1'],'oracle_kind':'approved-rule',
                'oracle_rationale':'Rule stated independently of the implementation.',
                'assertions':[{'target_id':'t','input_path':'test.py','assertion_ref':'test.py:12'}],
                'incorrect_behaviors':[{'text':'Return sixty instead of thirty.','failure_relevance':'Exact expected return assertion.',
                    'red_proof_id':'r','green_proof_id':'g','target_ids':['t']}]}]}
        return subject,package,review
    def test_independently_justified_actual_regression_supplies_discrimination(self):
        self.assertTrue(self.api().validate_test_quality(*self.quality_fixture())['passed'])
    def test_output_derived_oracle_missing_behavior_unrelated_red_and_skips_block(self):
        for case in ('copied','missing','target','setup','skip','source','assertion','limitations'):
            subject,package,report=self.quality_fixture();row=report['test_quality']['behaviors'][0]
            if case=='copied':row['oracle_kind']='implementation-output'
            if case=='missing':report['test_quality']['behaviors']=[]
            if case=='target':row['incorrect_behaviors'][0]['target_ids']=['unrelated']
            if case=='setup':subject['verification_proofs']['r']['integrity']['classification']['t']='setup'
            if case=='skip':subject['verification_proofs']['g']['integrity']['outcomes']['t']='skipped'
            if case=='source':subject['source_identity']='changed'
            if case=='assertion':row['assertions'][0]['input_path']='not-executed.py'
            if case=='limitations':report['test_quality'].pop('limitations')
            with self.subTest(case=case),self.assertRaises(WorkflowError):self.api().validate_test_quality(subject,package,report)
    def test_actual_surviving_challenge_prevents_quality_acceptance(self):
        repo,req,out=self.owned('always');receipt=self.api().execute_challenge(repo,req,out)
        subject,package,report=self.quality_fixture();subject['test_challenges']={'challenge':receipt}
        report['test_quality']['behaviors'][0]['incorrect_behaviors'][0]['challenge_ids']=['challenge']
        with self.assertRaises(WorkflowError):self.api().validate_test_quality(subject,package,report)
    def test_current_test_perspective_cannot_omit_quality_checks(self):
        from workflow_lib.oracle_acceptance import validate_oracle_acceptance
        subject,package,report=self.quality_fixture();report['perspective']='test';report.pop('test_quality')
        with self.assertRaises(WorkflowError):validate_oracle_acceptance(subject,package,report)

    def test_raw_challenge_stderr_preserves_invalid_utf8_and_crlf(self):
        repo,req,out=self.owned();path=repo/'check.py'
        path.write_bytes(b"import os;os.write(2,b'\\xff\\r\\n')\n"+path.read_bytes())
        req['input_hashes']['check.py']=hashlib.sha256(path.read_bytes()).hexdigest()
        receipt=self.api().execute_challenge(repo,req,out)
        self.assertEqual((out/receipt['changed']['stderr_ref']).read_bytes(),b'\xff\r\n')
    def test_import_failure_in_wrong_variant_cannot_count_as_detected(self):
        repo,req,out=self.owned();req['replacements'][0]['after']="raise ImportError('wrong variant')"
        receipt=self.api().execute_challenge(repo,req,out)
        self.assertEqual(receipt['baseline']['exit_code'],0)
        self.assertFalse(receipt['detected']);self.assertNotEqual(receipt['changed']['exit_code'],0)

    def test_same_behavior_id_in_different_items_cannot_drop_obligations(self):
        from workflow_lib.implementation_contracts import record_implementation_contract,contract_binding
        subject,package,report=self.quality_fixture();subject['plan']['work_items'].append({
            'id':'W2','kind':'code','requirement_ids':['R1'],'dependencies':[]})
        # Refresh W1 after the approved plan binding changes.
        first=subject['implementation_contracts']['item:W1'];request={k:copy.deepcopy(first[k]) for k in
            ('scope','source_identity','behaviors','invariants','interfaces','non_goals','neighboring_disposition')}
        subject=record_implementation_contract(subject,request)
        request['scope']={'role':'item','item_id':'W2'};subject=record_implementation_contract(subject,request)
        report.update(role='branch');report.pop('item_id')
        report['test_quality']['contract_binding']=contract_binding(subject,{'role':'branch'})
        report['test_quality']['behaviors'][0]['item_id']='W1'
        with self.assertRaises(WorkflowError):self.api().validate_test_quality(subject,package,report)

    def test_quality_cannot_borrow_another_items_or_attempts_proof(self):
        for field,value in (('item_id','W2'),('token','old-attempt')):
            subject,package,report=self.quality_fixture()
            subject['verification_proofs']['g'][field]=value
            with self.subTest(field=field),self.assertRaises(WorkflowError):self.api().validate_test_quality(subject,package,report)
