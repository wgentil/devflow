"""Versioned review requirements; all authorizations here are explicit fixtures."""
import copy,importlib.util,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class ReviewPolicyTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.review_policy'),'Shared review policy must exist.')
        from workflow_lib import review_policy
        return review_policy
    def subject(self):
        return {'id':'r','state_version':1,'status':'active','source_identity':'fixture-source',
            'plan':{'spec_hash':'fixture-approved-spec','work_items':[]},'review_policy':self.api().new_review_policy(),
            'enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1}}
    def scope(self):return {'role':'branch'}
    def risk(self,classification='substantive'):
        return {'schema_version':1,'bindings':self.api().review_bindings(self.subject(),self.scope()),
            'classification':classification,'scope_evidence_refs':['fixture:selected-diff'], 'triggers':[],
            'perspectives':{p:{'applicability':'not-applicable','reason':'Owned fixture has no affected boundary.',
                'evidence_refs':['fixture:unchanged-boundaries']} for p in ('code','test','architecture','security')}}
    def test_new_runs_select_current_policy_without_inventing_approvals(self):
        from test_runs import state
        from workflow_lib.runs import start_run
        data=state();run=start_run(data,'new',data['plan'])
        self.assertEqual(run.get('review_policy',{}).get('protocol'),'devflow.adversarial-review/v1')
        self.assertEqual(run.get('enforcement',{}).get('protocol'),'devflow.python-enforcement/v1')
        self.assertNotIn('protected_inventories',run)
        self.assertFalse(run.get('repair_policy',{}).get('enabled'))
    def test_unknown_risk_requires_every_specialist(self):
        required=self.api().review_requirements(self.subject(),self.scope(),{})
        self.assertEqual(set(required['required_perspectives']),{'code','test','architecture','security'})
        self.assertEqual(required['risk_status'],'unknown')
    def test_substantive_known_low_risk_still_requires_code_and_tests(self):
        result=self.api().review_requirements(self.subject(),self.scope(),self.risk())
        self.assertEqual(result['required_perspectives'],['code','test'])
        self.assertFalse(result['lightweight'])
        self.assertTrue(result['requires_confirmation'])
    def test_lightweight_needs_positive_cited_scope_and_each_exemption(self):
        risk=self.risk('lightweight');result=self.api().review_requirements(self.subject(),self.scope(),risk)
        self.assertEqual(result['required_perspectives'],[]);self.assertTrue(result['lightweight'])
        for key in ('scope_evidence_refs','perspectives'):
            broken=copy.deepcopy(risk);broken.pop(key)
            result=self.api().review_requirements(self.subject(),self.scope(),broken)
            self.assertTrue(result['required_perspectives']);self.assertFalse(result['lightweight'])
    def test_markdown_name_and_triggers_cannot_prove_low_risk(self):
        risk=self.risk('lightweight');risk['changed_paths']=['README.md'];risk['triggers']=['execution-surface']
        result=self.api().review_requirements(self.subject(),self.scope(),risk)
        self.assertIn('security',result['required_perspectives']);self.assertFalse(result['lightweight'])
        risk['triggers']=['interfaces','sensitive-data']
        result=self.api().review_requirements(self.subject(),self.scope(),risk)
        self.assertTrue({'architecture','security'}.issubset(result['required_perspectives']))
    def test_stale_source_scope_spec_policy_or_contract_cannot_reuse_risk(self):
        risk=self.risk()
        for field in ('source_identity','plan','review_policy','implementation_contracts'):
            subject=self.subject()
            if field=='source_identity':subject[field]='changed'
            if field=='plan':subject[field]['spec_hash']='changed'
            if field=='review_policy':subject[field]['revision']=2
            if field=='implementation_contracts':subject[field]={'branch':{'contract_hash':'changed'}}
            result=self.api().review_requirements(subject,self.scope(),risk)
            self.assertEqual(set(result['required_perspectives']),{'code','test','architecture','security'},field)
        result=self.api().review_requirements(self.subject(),{'role':'item','item_id':'W1'},risk)
        self.assertEqual(set(result['required_perspectives']),{'code','test','architecture','security'})
    def test_legacy_opaque_and_future_selected_contracts_are_distinct(self):
        api=self.api()
        self.assertEqual(api.review_requirements({'review_policy':{'version':1}},self.scope(),{})['status'],'not-applicable')
        for policy in ({'protocol':'devflow.adversarial-review/v2','schema_version':2},
                       {'protocol':'devflow.adversarial-review/v1'},
                       {'protocol':'devflow.adversarial-review/v1','schema_version':True}):
            self.assertEqual(api.review_requirements({'review_policy':policy},self.scope(),{})['status'],'block')
    def test_adoption_is_quiescent_exact_authorized_and_does_not_reset_spending(self):
        api=self.api();subject={'id':'r','status':'active','state_version':1,
            'enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1},
            'effects_started_ms':10,'effects':{'spent':{'status':'completed','estimated_cost':2}},
            'reviews':{'branch':[{'fresh':True}]},'acceptances':[{'fresh':True}]}
        authorization={'approved':True,'actor_id':'fixture-user','run_id':'r','state_version':1,
            'provenance':{'kind':'user-message','ref':'fixture-approval'}}
        for fields in ({'active_attempt':{'token':'t'}},{'effects':{'e':{'status':'uncertain'}}},
                       {'active_executions':{'W1':{'status':'launching'}}},{'status':'delivered'}):
            with self.subTest(fields=fields),self.assertRaises(WorkflowError):api.adopt_review_policy({**subject,**fields},authorization)
        with self.assertRaises(WorkflowError):api.adopt_review_policy(subject,{**authorization,'state_version':0})
        adopted=api.adopt_review_policy(subject,authorization)
        self.assertEqual(adopted['effects'],subject['effects']);self.assertEqual(adopted['effects_started_ms'],10)
        self.assertFalse(adopted['reviews']['branch'][0]['fresh']);self.assertFalse(adopted['acceptances'][0]['fresh'])
        with self.assertRaises(WorkflowError):api.adopt_review_policy(adopted,{**authorization,'state_version':adopted['state_version']})
        self.assertNotIn('review_policy',subject)
    def test_live_new_run_event_cannot_omit_policy_but_old_pure_replay_survives(self):
        from workflow_lib import store,sqlite_store
        from control_store_fixtures import legacy_root
        for initialize in (legacy_root,sqlite_store.initialize_store):
            root=Path(self.enterContext(tempfile.TemporaryDirectory()))/'control';initialize(root)
            event={'kind':'run.started','payload':{'run':{'id':'old','status':'active','state_version':0}}}
            replay={'data':{}};store._apply_event(replay,event)
            self.assertEqual(replay['data']['runs']['old']['id'],'old')
            with self.assertRaises(WorkflowError):store.transact(root,0,'new-live-legacy',event)

    def test_unknown_effect_state_cannot_be_declared_quiescent(self):
        subject=self.subject();subject.pop('review_policy');subject['effects']={'e':{'status':'interrupted'}}
        authorization={'approved':True,'actor_id':'fixture-user','run_id':'r','state_version':1,
            'provenance':{'kind':'user-message','ref':'fixture-approval'}}
        with self.assertRaises(WorkflowError):self.api().adopt_review_policy(subject,authorization)

    def test_risk_change_invalidates_reserved_decision_without_resetting_attempt(self):
        from workflow_lib.action_policy import subject_decision
        subject=self.subject();before=subject_decision(subject,'dispatch',{})
        updated=self.api().record_risk(subject,self.scope(),self.risk())
        self.assertNotEqual(before['context_hash'],subject_decision(updated,'dispatch',{})['context_hash'])
        self.assertEqual(subject['state_version'],updated['state_version'])

    def test_future_review_policy_blocks_action_even_with_current_enforcement(self):
        from workflow_lib.action_policy import subject_decision
        subject=self.subject();subject['review_policy']['schema_version']=2
        self.assertEqual(subject_decision(subject,'dispatch',{})['status'],'block')

    def test_public_adoption_and_risk_exact_replay_both_formats(self):
        import json,subprocess
        from workflow_lib import store,sqlite_store
        from control_store_fixtures import legacy_root
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        for initialize in (legacy_root,sqlite_store.initialize_store):
            base=Path(self.enterContext(tempfile.TemporaryDirectory()));root=base/'control';initialize(root)
            subject={'id':'r','status':'active','state_version':1,'source_identity':'fixture-source',
                'plan':{'spec_hash':'fixture-spec','work_items':[]}}
            store.transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':subject}}})
            def call(action,op,request):
                path=base/(op+'.json');path.write_text(json.dumps(request))
                result=subprocess.run([sys.executable,str(entry),'review',action,'--root',str(root),'--run-id','r',
                    '--operation-id',op,'--input',str(path)],capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                return json.loads(result.stdout)
            auth={'approved':True,'actor_id':'fixture-user','run_id':'r','state_version':1,
                'provenance':{'kind':'user-message','ref':'fixture-approval'}}
            adopted=call('adopt','adopt',auth);self.assertTrue(call('adopt','adopt',auth)['replayed'])
            current=store.read_state(root)['data']['runs']['r'];risk=self.risk()
            risk['bindings']=self.api().review_bindings(current,self.scope())
            request={'scope':self.scope(),'risk':risk}
            call('assess-risk','risk',request);self.assertTrue(call('assess-risk','risk',request)['replayed'])
            current=store.read_state(root)['data']['runs']['r']
            self.assertEqual(next(iter(current['risk_assessments'].values()))['assessment']['required_perspectives'],['code','test'])

    def test_frozen_legacy_start_exact_retry_is_history_not_new_policy_adoption(self):
        from unittest.mock import patch
        from workflow_lib import store,sqlite_store
        from control_store_fixtures import legacy_root
        for initialize in (legacy_root,sqlite_store.initialize_store):
            root=Path(self.enterContext(tempfile.TemporaryDirectory()))/'control';initialize(root)
            event={'kind':'run.started','payload':{'run':{'id':'historical','status':'active','state_version':0}}}
            # Model an event written by the previous release; only its historical producer guard is absent.
            with patch.object(store,'_guard_enforcement_transaction'):
                first=store.transact(root,0,'historical-start',event)
            retry=store.transact(root,0,'historical-start',event)
            self.assertTrue(retry['replayed']);self.assertEqual(retry['event'],first['event'])
            self.assertNotIn('review_policy',store.read_state(root)['data']['runs']['historical'])

    def test_context_layer_may_revoke_but_cannot_forge_resolved_authority(self):
        from workflow_lib.action_policy import validate_authority_patch
        data={'enforcement_guard':{'protocol':'devflow.python-enforcement/v1','schema_version':1}}
        validate_authority_patch(data,'context.layer.set',{'context':{'org':{'slices':{}}},'resolved_context':None})
        with self.assertRaises(WorkflowError):
            validate_authority_patch(data,'context.layer.set',{'context':{},'resolved_context':{'values':{'invented':True}}})
