import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib.model_policy import resolve_profile, check_model_receipt, interruption
from workflow_lib.model_discovery import discovery_key, cached_discovery, store_discovery

class ModelPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy={'schema_version':1,'version':'fixture-1','stages':{'planning':'deep-reasoning','implementation':'efficient-coding','tests':'deterministic'},
          'profiles':{'deep-reasoning':{'effort':'high'},'efficient-coding':{'effort':'medium'}},
          'hosts':{'codex':{'deep-reasoning':[{'provider':'openai','model':'deep','efforts':['high'],'status':'validated','validation_ref':'fixture-eval-1','policy_version':'fixture-1'},
             {'provider':'openai','model':'fallback','efforts':['high'],'status':'validated','validation_ref':'fixture-eval-2','policy_version':'fixture-1'}]}}}
        self.cap={'configure':True,'observe':False,'models':['deep','fallback'],'efforts':['high']}
        self.discovery={'models':{'deep':'available','fallback':'available'}}
        self.req={'host':'codex','stage':'planning','mode':'advisory'}
    def resolve(self,**changes):return resolve_profile(self.policy,{**self.req,**changes},self.cap,self.discovery,None)
    def test_profiles_and_deterministic_helpers(self):
        policy=json.loads((ROOT/'definitions/model-policy.json').read_text())
        self.assertEqual(policy['stages']['planning'],'deep-reasoning')
        self.assertEqual(policy['stages']['implementation'],'efficient-coding')
        self.assertEqual(self.resolve(stage='tests')['dispatch'],False)
        result=self.resolve();self.assertEqual(result['resolved']['model'],'deep');self.assertEqual(result['mode'],'advisory')
    def test_unknown_effective_identity_blocks_strict(self):
        self.assertEqual(self.resolve(mode='strict')['status'],'block')
        self.cap['observe']=True
        result=self.resolve(mode='strict');self.assertEqual(result['status'],'allow')
        receipt={**result,'observed':{'model':'other','effort':'high'},'observation_source':'caller'}
        self.assertEqual(check_model_receipt(receipt,'strict')['status'],'block')
    def test_candidates_not_defaults_and_unvalidated_override_advisory(self):
        entry=self.policy['hosts']['codex']['deep-reasoning'][0];entry['status']='candidate'
        self.assertEqual(self.resolve()['resolved']['model'],'fallback')
        self.assertEqual(self.resolve(pin='deep')['status'],'block')
        self.assertEqual(self.resolve(pin='deep',allow_unvalidated=True)['mode'],'advisory')
    def test_retirement_validated_fallback_and_pin_pause(self):
        self.discovery['models']['deep']='retired'
        self.assertEqual(self.resolve()['resolved']['model'],'fallback')
        self.assertEqual(self.resolve(pin='deep')['reason_code'],'PIN_UNAVAILABLE')
        self.discovery['models']['fallback']='unavailable'
        self.assertEqual(self.resolve()['status'],'block')
    def test_account_effort_and_budget(self):
        self.assertEqual(self.resolve(max_cost=1)['reason_code'],'COST_UNKNOWN')
        self.cap['efforts']=[];self.assertEqual(self.resolve(mode='strict')['status'],'block')
        self.cap['models']=[];self.assertEqual(self.resolve()['status'],'block')
    def test_trusted_receipt_and_substitution(self):
        receipt={**self.resolve(),'observed':{'model':'deep','effort':'high'},'observation_source':'host-effective-configuration'}
        self.assertEqual(check_model_receipt(receipt,'strict')['status'],'allow')
        receipt['observed']['model']='substituted'
        self.assertEqual(check_model_receipt(receipt,'strict')['reason_code'],'MODEL_SUBSTITUTED')
    def test_interruption_distinguishes_errors_preserves_attempt(self):
        for error in ('auth','network','quota','rate-limit','context','retired'):
            result=interruption({'invocation_id':'i','token':'t'},error,2)
            self.assertEqual(result['token'],'t');self.assertEqual(result['error_kind'],error)
            self.assertFalse(result['retry_allowed'])
    def test_discovery_cache_invalidation(self):
        key=discovery_key('codex','account','p1');cache={}
        store_discovery(cache,key,{'models':{'deep':'available'}},100,60)
        self.assertIsNotNone(cached_discovery(cache,key,120))
        self.assertIsNone(cached_discovery(cache,key,161))
        self.assertIsNone(cached_discovery(cache,key,120,refresh=True))
        self.assertIsNone(cached_discovery(cache,discovery_key('codex','account','p2'),120))
        self.assertIsNone(cached_discovery(cache,key,120,availability_failure=True))
