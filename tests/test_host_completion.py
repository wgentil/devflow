import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from test_hosts import host_state, attachment
from workflow_lib.hosts import apply_host_event
from workflow_lib.host_completion import check_completion, host_brief

class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.state=host_state(); self.binding=apply_host_event(self.state,'attach',attachment())
        apply_host_event(self.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'})
    def test_unmapped_tasks_inactive(self):self.assertEqual(check_completion(self.state,self.binding,'ordinary',False)['status'],'inactive')
    def test_missing_proof_and_active_attempt_block(self):
        self.assertEqual(check_completion(self.state,self.binding,'task',False)['status'],'block')
        self.state['runs']['run']['active_attempt']=None
        self.assertEqual(check_completion(self.state,self.binding,'task',False)['reason_code'],'FINAL_PROOF_REQUIRED')
    def green(self):
        run=self.state['runs']['run'];run['active_attempt']=None;run['items']['W1']['status']='complete'
        run['verifier_proofs']={'p':{'passed':True,'item_id':'W1','token':'t','evidence_id':'p'}}
        run['verification_proofs']={'p':{'kind':'code','phase':'GREEN','fresh':True,'item_id':'W1','token':'t','passed':True}}
    def test_current_final_proof_allows_exact_task(self):
        self.green();self.assertEqual(check_completion(self.state,self.binding,'task',False)['status'],'allow')
        self.state['runs']['run']['items']['W1']['attempts'].append({'token':'new'})
        self.assertEqual(check_completion(self.state,self.binding,'task',False)['status'],'block')
    def test_live_proof_without_repo_evidence_blocks(self):
        self.green();self.assertEqual(check_completion(self.state,self.binding,'task',True)['status'],'block')
    def test_stale_binding_and_strict_model_blocks(self):
        self.green();self.state['runs']['run']['model_overrides']=[{'mode':'strict'}]
        self.assertEqual(check_completion(self.state,self.binding,'task',False)['reason_code'],'STRICT_UNOBSERVABLE')
        self.state['host_bindings']['b1']['revision']=2
        self.assertEqual(check_completion(self.state,self.binding,'task',False)['reason_code'],'STALE_BINDING')
    def test_delivery_requires_actual_terminal_result(self):
        apply_host_event(self.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'delivery','scope':'delivery'})
        self.assertEqual(check_completion(self.state,self.binding,'delivery',False)['status'],'block')
        self.state['runs']['run'].update(status='delivered',delivery={'actual_result':{'status':'merged'},'manifest_hash':'hash'})
        self.assertEqual(check_completion(self.state,self.binding,'delivery',False)['status'],'allow')
    def test_brief_unrelated_events_deduplicate(self):
        first=host_brief(self.state,self.binding)
        self.state['usage']={'unrelated':'changed'}
        self.assertEqual(first['fingerprint'],host_brief(self.state,self.binding)['fingerprint'])
        self.state['runs']['run']['active_attempt']=None
        self.assertNotEqual(first['fingerprint'],host_brief(self.state,self.binding)['fingerprint'])
    def test_reviewer_assessment_can_complete_without_gate_pass(self):
        self.state['runs']['run']['review_packages']={'pkg':{'role':'branch','package_hash':'pkg','plan_hash':'unused'}}
        reviewer=apply_host_event(self.state,'attach',attachment(binding_id='rb',session_id='rs',actor_id='ra',role='branch-reviewer',package_hash='pkg'))
        apply_host_event(self.state,'task-bind',{'binding_id':'rb','revision':1,'task_id':'review','scope':'review','package_hash':'pkg'})
        self.state['runs']['run']['reviews']={'branch':[{'package_hash':'pkg','actor_id':'ra','invocation_ref':'real-invocation','verdict':'request-changes','fresh':True}]}
        self.assertEqual(check_completion(self.state,reviewer,'review',False)['status'],'allow')
        self.state['runs']['run']['reviews']['branch'][0]['actor_id']='other'
        self.assertEqual(check_completion(self.state,reviewer,'review',False)['status'],'block')
