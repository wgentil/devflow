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
        return {'id':'r','state_version':1,'source_identity':'sha','enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},
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
    def test_uncertain_worker_blocks_completion_without_being_reported_fixed(self):
        from workflow_lib.action_policy import subject_decision
        subject=self.api().claim_effect(self.subject(),self.request())
        self.assertEqual(subject_decision(subject,'completion',{})['status'],'block')
        self.assertEqual(subject_decision(subject,'delivery',{})['status'],'block')
        self.assertEqual(subject_decision(subject,'review-report',{})['status'],'allow')
    def test_policy_change_or_elapsed_limit_invalidates_launch_reservation(self):
        api=self.api();subject=api.claim_effect(self.subject(),self.request())
        original=subject['effects']['one']
        subject['effect_policy']['max_attempts']=3
        with self.assertRaises(WorkflowError):
            api.validate_launch_receipt(subject,original,{'source_identity':'sha','now_ms':11})
        subject=api.claim_effect(self.subject(),self.request())
        with self.assertRaises(WorkflowError):
            api.transition_effect(subject,{'effect_id':'one','status':'launching','now_ms':1010})

    def test_explicit_extension_preserves_spending_history_and_clock(self):
        from workflow_lib.enforcement_events import apply_enforcement
        from workflow_lib.document_units import digest
        api=self.api();subject=api.claim_effect(self.subject(),self.request())
        request={'previous_policy_hash':digest(subject['effect_policy']),
            'policy':{'max_attempts':3,'max_estimated_cost':5,'max_elapsed_ms':2000},
            'authorization':{'approved':True,'actor_id':'fixture-user','reason':'additional reviewed work',
                'provenance':{'kind':'user-message','ref':'fixture-message'}}}
        with self.assertRaises(WorkflowError):apply_enforcement(subject,'extend-effects',request)
        subject=api.transition_effect(subject,{'effect_id':'one','status':'failed','now_ms':11})
        updated=apply_enforcement(subject,'extend-effects',request)
        self.assertEqual(updated['effects'],subject['effects'])
        self.assertEqual(updated['effects_started_ms'],10)
        self.assertEqual(updated['effect_policy'],request['policy'])
        self.assertEqual(len(updated['effect_policy_extensions']),1)
        with self.assertRaises(WorkflowError):apply_enforcement(updated,'extend-effects',request)

    def test_initial_policy_rejects_invalid_limits_before_reservation(self):
        from workflow_lib.enforcement_events import apply_enforcement
        for value in (None,True,float('nan'),-1):
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                apply_enforcement(self.subject(),'configure-effects',{
                    'max_attempts':1,'max_estimated_cost':value,'max_elapsed_ms':100,
                    'authorization':{'approved':True,'actor_id':'fixture-user'}})

    def test_public_transition_cannot_fabricate_bound_native_completion(self):
        from workflow_lib.enforcement_events import apply_enforcement
        api=self.api();request={**self.request(),'owner_binding':{'binding_id':'native','role':'implementer'}}
        subject=api.claim_effect(self.subject(),request)
        subject=api.transition_effect(subject,{'effect_id':'one','status':'launching','now_ms':11})
        subject=api.transition_effect(subject,{'effect_id':'one','status':'running','now_ms':12,'worker_ref':'actual-worker'})
        with self.assertRaises(WorkflowError):
            apply_enforcement(subject,'effect-transition',{'effect_id':'one','status':'completed',
                'now_ms':13,'worker_ref':'actual-worker'})

    def test_transition_time_and_observed_spend_cannot_move_backwards(self):
        api=self.api();subject=api.claim_effect(self.subject(),self.request())
        subject=api.transition_effect(subject,{'effect_id':'one','status':'launching','now_ms':20})
        with self.assertRaises(WorkflowError):
            api.transition_effect(subject,{'effect_id':'one','status':'running','now_ms':11,'worker_ref':'worker'})
        subject=api.transition_effect(subject,{'effect_id':'one','status':'running','now_ms':21,
            'worker_ref':'worker','observed_cost':2})
        with self.assertRaises(WorkflowError):
            api.transition_effect(subject,{'effect_id':'one','status':'completed','now_ms':22,'observed_cost':1})

    def test_caller_supplied_os_stop_claim_is_not_a_termination_observation(self):
        api=self.api();subject=api.claim_effect(self.subject(),self.request())
        subject=api.transition_effect(subject,{'effect_id':'one','status':'launching','now_ms':11})
        subject=api.transition_effect(subject,{'effect_id':'one','status':'uncertain','now_ms':12,'worker_ref':'worker'})
        with self.assertRaises(WorkflowError):
            api.transition_effect(subject,{'effect_id':'one','status':'reconciled','now_ms':13,
                'termination_receipt':{'effect_id':'one','worker_ref':'worker','basis':'os-owner-stopped'}})

    def test_probe_and_work_have_separate_attempt_counts_but_shared_spend_and_clock(self):
        api=self.api();subject=self.subject()
        subject['effect_policy'].update(max_attempts=1,max_probe_attempts=1,max_estimated_cost=4)
        probe={**self.request('probe','probe'),'effect_kind':'probe'}
        subject=api.claim_effect(subject,probe)
        subject=api.transition_effect(subject,{'effect_id':'probe','status':'failed','now_ms':11})
        subject=api.claim_effect(subject,self.request('work','work'))
        self.assertEqual(subject['effects_started_ms'],10)
        with self.assertRaises(WorkflowError):api.claim_effect(subject,{**probe,'effect_id':'another-probe'})
        with self.assertRaises(WorkflowError):api.claim_effect(subject,self.request('another-work','other'))
        self.assertEqual(sum(e['estimated_cost'] for e in subject['effects'].values()),4)

    def test_observed_overrun_is_charged_before_new_reservations(self):
        api=self.api();subject=api.claim_effect(self.subject(),{**self.request(),'estimated_cost':1})
        subject=api.transition_effect(subject,{'effect_id':'one','status':'failed','now_ms':11,'observed_cost':2})
        with self.assertRaises(WorkflowError):api.claim_effect(subject,self.request('two','b'))
