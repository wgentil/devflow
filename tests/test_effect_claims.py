import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class ClaimTests(unittest.TestCase):
    def api(self):
        from workflow_lib import effect_claims
        return effect_claims
    def subject(self):
        return {'id':'r','state_version':1,'source_identity':'sha','enforcement':{'policy_version':1},
            'effect_policy':{'max_attempts':2,'max_estimated_cost':3,'max_elapsed_ms':1000},'effects':{}}
    def request(self,identifier='one',scope='a'):
        return {'effect_id':identifier,'scope':scope,'estimated_cost':2,'now_ms':10,'source_identity':'sha'}
    def test_budget_and_exclusive_claim_cannot_be_spent_twice(self):
        api=self.api();s=api.claim_effect(self.subject(),self.request())
        with self.assertRaises(WorkflowError):api.claim_effect(s,self.request('two'))
        with self.assertRaises(WorkflowError):api.claim_effect(s,self.request('two','b'))
        self.assertEqual(api.claim_effect(s,self.request()),s)
    def test_unknown_nonfinite_or_negative_estimates_block(self):
        for cost in (None,float('nan'),float('inf'),-1,True):
            r=self.request();r['estimated_cost']=cost
            with self.assertRaises(WorkflowError):self.api().claim_effect(self.subject(),r)
    def test_launch_changes_and_uncertain_worker_block_replacement(self):
        api=self.api();s=api.claim_effect(self.subject(),self.request())
        receipt=s['effects']['one'];s['source_identity']='different'
        with self.assertRaises(WorkflowError):api.validate_launch_receipt(s,receipt,{'source_identity':'different'})
        s['source_identity']='sha'
        s=api.transition_effect(s,{'effect_id':'one','status':'launching','now_ms':11})
        with self.assertRaises(WorkflowError):api.transition_effect(s,{'effect_id':'one','status':'reconciled','now_ms':12})
        with self.assertRaises(WorkflowError):api.claim_effect(s,self.request('two'))
    def test_failed_launch_does_not_refund_spend(self):
        api=self.api();s=api.claim_effect(self.subject(),self.request())
        s=api.transition_effect(s,{'effect_id':'one','status':'failed','now_ms':11})
        with self.assertRaises(WorkflowError):api.claim_effect(s,self.request('two','b'))
