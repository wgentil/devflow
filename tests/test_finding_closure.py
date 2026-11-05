"""Structural fixture receipts; actual execution is covered by evidence integration tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class ClosureTests(unittest.TestCase):
    def fixture(self):
        subject = {'id':'r','enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'source_identity':'sha',
            'actors':{'implementer':'author'},'plan':{'work_items':[{'id':'W1','kind':'code','dependencies':[]}]},
            'items':{'W1':{'attempts':[{'token':'t'}]}},
            'unresolved_findings':[{'id':'f','item_id':'W1','obligations':['o1','o2']}],
            'corrections':{'f':{'source_identity':'sha','proof_ids':['p']}},
            'verifier_proofs':{'p':{'passed':True,'fresh':True,'source_identity':'sha','evidence_id':'raw',
                'item_id':'W1','token':'t','semantic_status':'reviewed'}},
            'verification_proofs':{'raw':{'id':'raw','item_id':'W1','token':'t','kind':'code','phase':'GREEN','source_identity':'sha','fresh':True,'passed':True}},
            'reviews':{'branch':[{'review_id':'rev','actor_id':'independent','invocation_ref':'call',
                'fresh':True,'verdict':'pass','package_hash':'pkg','closure_dispositions':[
                    {'finding_id':'f','source_identity':'sha','obligations':['o1','o2'],'disposition':'resolved','proof_ids':['p'],'proof_applicability':{'p':['o1','o2']}}]}]},
            'review_packages':{'pkg':{'package_hash':'pkg','role':'branch','source_identity':'sha'}}}
        from workflow_lib.review_enforcement import review_bindings
        subject['review_packages']['pkg']['enforcement_bindings']=review_bindings(subject,'branch')
        return subject
    def validate(self,s):
        from workflow_lib.finding_closure import validate_closure
        return validate_closure(s,{'finding_id':'f','review_id':'rev'})
    def test_current_independent_closure_succeeds(self):
        self.assertEqual(self.validate(self.fixture())['status'],'resolved')
    def test_implementer_cannot_close_own_fix(self):
        s=self.fixture();s['reviews']['branch'][0]['actor_id']='author'
        with self.assertRaises(WorkflowError):self.validate(s)
    def test_stale_or_unrelated_proof_rejected(self):
        for field,value in [('passed',False),('fresh',False),('source_identity','old')]:
            s=self.fixture();s['verifier_proofs']['p'][field]=value
            with self.assertRaises(WorkflowError):self.validate(s)
    def test_all_consolidated_obligations_required(self):
        s=self.fixture();s['reviews']['branch'][0]['closure_dispositions'][0]['obligations']=['o1']
        with self.assertRaises(WorkflowError):self.validate(s)
    def test_prose_requires_independent_applicability(self):
        s=self.fixture();s['corrections']['f']['proof_ids']=[]
        d=s['reviews']['branch'][0]['closure_dispositions'][0];d['proof_ids']=[]
        with self.assertRaises(WorkflowError):self.validate(s)
        d['execution_inapplicable']={'reason':'Prose defect','evidence_refs':['docs/file:1']}
        self.assertEqual(self.validate(s)['status'],'resolved')
    def test_waiver_is_not_verified_repair(self):
        s=self.fixture();s['reviews']['branch'][0]['closure_dispositions'][0]['disposition']='waived'
        with self.assertRaises(WorkflowError):self.validate(s)

    def test_proof_must_match_item_attempt_semantic_review_and_obligations(self):
        for change in ('item','token','semantic','obligations','phase'):
            subject=self.fixture();proof=subject['verifier_proofs']['p']
            if change=='item':proof['item_id']='unrelated-item'
            if change=='token':proof['token']='old-attempt'
            if change=='semantic':proof['semantic_status']='pending-review'
            if change=='obligations':subject['reviews']['branch'][0]['closure_dispositions'][0]['proof_applicability']={'p':['o1']}
            if change=='phase':subject['verification_proofs']['raw']['phase']='RED'
            with self.subTest(change=change), self.assertRaises(WorkflowError):self.validate(subject)

    def test_unresolved_disagreement_or_wrong_required_perspective_blocks_closure(self):
        for change in ('disagreement','perspective'):
            subject=self.fixture();finding=subject['unresolved_findings'][0]
            if change=='disagreement':finding['unresolved_disagreements']=['conflicting-business-rule']
            else:finding['required_perspective']='security'
            with self.subTest(change=change), self.assertRaises(WorkflowError):self.validate(subject)

    def test_individual_resolution_can_be_recorded_in_request_changes_assessment(self):
        subject=self.fixture();subject['reviews']['branch'][0]['verdict']='request-changes'
        self.assertEqual(self.validate(subject)['status'],'resolved')
