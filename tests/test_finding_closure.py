import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class ClosureTests(unittest.TestCase):
    def fixture(self):
        return {'id':'r','enforcement':{'policy_version':1},'source_identity':'sha',
            'actors':{'implementer':'author'},'unresolved_findings':[{'id':'f','obligations':['o1','o2']}],
            'corrections':{'f':{'source_identity':'sha','proof_ids':['p']}},
            'verifier_proofs':{'p':{'passed':True,'fresh':True,'source_identity':'sha'}},
            'reviews':{'branch':[{'review_id':'rev','actor_id':'independent','invocation_ref':'call',
                'fresh':True,'verdict':'pass','package_hash':'pkg','closure_dispositions':[
                    {'finding_id':'f','source_identity':'sha','obligations':['o1','o2'],'disposition':'resolved','proof_ids':['p']}]}]},
            'review_packages':{'pkg':{'package_hash':'pkg','source_identity':'sha'}}}
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
