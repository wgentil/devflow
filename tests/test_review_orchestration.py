"""Pure next-action transitions with labeled structural evidence, no effects."""
import copy,importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError
from workflow_lib.document_units import digest

class OrchestrationTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.review_orchestration'))
        from workflow_lib import review_orchestration
        return review_orchestration
    def subject(self):
        from test_review_contracts import ContractTests
        subject=ContractTests().ready();subject.update(status='active',actors={'implementer':'writer'},
            unresolved_findings=[{'id':'f','item_id':'W1','severity':'important','failure_scenario':'Sixty instead of thirty.',
                'impact':'Wrong retention.','requested_correction':'Use thirty.','obligations':['retention']}],
            effect_policy={'max_attempts':20,'max_estimated_cost':20,'max_elapsed_ms':10000},effects={},repair_cycles=[])
        return subject
    def configure(self,subject=None):
        subject=subject or self.subject()
        policy={'protocol':'devflow.review-orchestration/v1','schema_version':1,'enabled':True,
            'max_attempts':3,'max_elapsed_ms':5000,'max_estimated_cost':10,'no_progress_window':2,
            'effect_policy_hash':digest(subject['effect_policy'])}
        return self.api().apply_orchestration(subject,'configure',{'policy':policy,'now_ms':1000,
            'authorization':{'approved':True,'actor_id':'fixture-user','policy_hash':digest(policy),
                'provenance':{'kind':'user-message','ref':'fixture:authorize'}}})
    def test_pending_business_question_returns_actual_question(self):
        subject=self.configure();subject['clarifications']={'q':{'id':'q','version':1,'status':'pending','scope':None,'text':'Which retention rule applies?'}}
        before=copy.deepcopy(subject);action=self.api().orchestration_next(subject,1100)
        self.assertEqual(action['kind'],'ask-user');self.assertIn('Which retention rule applies?',str(action));self.assertEqual(subject,before)
    def test_review_finding_without_failed_gate_is_repairable(self):
        subject=self.configure();action=self.api().orchestration_next(subject,1100)
        self.assertEqual(action['kind'],'verify');self.assertEqual(action['phase'],'RED');self.assertIn('f',action['scope']['finding_ids'])
    def test_worker_exit_leaves_verification_next(self):
        subject=self.configure();subject['review_orchestration']['cycles']=[{'cycle_id':'cycle','status':'active','scope':{'role':'item','item_id':'W1','finding_ids':['f']},'actions':[
            {'kind':'implement','status':'recorded','result_ref':'worker','baseline_proof_ids':['red']}]}]
        subject['native_invocations']={'worker':{'status':'completed','stage':'implementation'}}
        subject['model_receipts']={'worker':{'status':'allow','invocation_ref':'fixture:completed'}}
        action=self.api().orchestration_next(subject,1100)
        self.assertEqual(action['kind'],'verify');self.assertEqual(action['phase'],'GREEN')
    def test_renamed_finding_is_not_progress(self):
        before=self.configure();after=copy.deepcopy(before);after['unresolved_findings'][0]['id']='fresh-id'
        after['source_identity']='unrelated-source';after['timestamp']='later'
        self.assertEqual(self.api().progress_signature(before),self.api().progress_signature(after))
    def test_waiting_does_not_reset_elapsed_clock(self):
        subject=self.configure();subject['clarifications']={'q':{'id':'q','version':1,'status':'pending','scope':None,'text':'Which retention rule applies?'}}
        self.api().orchestration_next(subject,1200)
        self.assertEqual(subject['review_orchestration']['started_ms'],1000)
        action=self.api().orchestration_next(subject,6000);self.assertEqual(action['reason_code'],'TIME_LIMIT')
    def test_read_only_status_never_enables_or_mutates_loop(self):
        subject=self.subject();before=copy.deepcopy(subject)
        self.assertEqual(self.api().orchestration_next(subject,1100)['reason_code'],'REPAIR_DISABLED');self.assertEqual(subject,before)
    def test_configuration_cannot_reset_existing_clock_spending_or_history(self):
        subject=self.subject();subject['repair_started_ms']=500;subject['effects_started_ms']=600
        subject['repair_cycles']=[{'cycle_id':'legacy','status':'recorded','estimated_cost':1}]
        configured=self.configure(subject)
        self.assertEqual(configured['review_orchestration']['started_ms'],500)
        self.assertEqual(configured['repair_cycles'],subject['repair_cycles']);self.assertEqual(configured['effects'],subject['effects'])
        with self.assertRaises(WorkflowError):self.configure(configured)
    def test_exhausted_attempts_and_no_progress_stop_before_new_action(self):
        for reason,count in [('ATTEMPT_LIMIT',3),('NO_PROGRESS',2)]:
            subject=self.configure();signature=self.api().progress_signature(subject)
            subject['review_orchestration']['cycles']=[{'cycle_id':str(n),'status':'recorded','before_progress':signature,'after_progress':signature} for n in range(count)]
            self.assertEqual(self.api().orchestration_next(subject,1100)['reason_code'],reason)
    def test_changed_shared_budget_needs_explicit_extension(self):
        subject=self.configure();subject['effect_policy']['max_attempts']+=1
        self.assertEqual(self.api().orchestration_next(subject,1100)['reason_code'],'SHARED_BUDGET_CHANGED')
    def test_claim_requires_exact_predecessor_and_retries_are_idempotent(self):
        subject=self.configure();action=self.api().orchestration_next(subject,1100)
        record={'cycle_id':'cycle','now_ms':1100,'input_hash':action['input_hash']}
        claimed=self.api().apply_orchestration(subject,'begin-cycle',record)
        self.assertEqual(len(claimed['review_orchestration']['cycles']),1)
        self.assertEqual(self.api().apply_orchestration(claimed,'begin-cycle',record),claimed)
        with self.assertRaises(WorkflowError):self.api().apply_orchestration(subject,'begin-cycle',{**record,'input_hash':'stale'})

    def test_action_records_cannot_invent_a_completed_worker(self):
        subject=self.configure();start=self.api().orchestration_next(subject,1100)
        subject=self.api().apply_orchestration(subject,'begin-cycle',{'cycle_id':'cycle','now_ms':1100,'input_hash':start['input_hash']})
        next_=self.api().orchestration_next(subject,1101)
        claim={'cycle_id':'cycle','action_id':'baseline','now_ms':1101,'input_hash':next_['input_hash']}
        claimed=self.api().apply_orchestration(subject,'claim-action',claim)
        self.assertEqual(len(claimed['review_orchestration']['cycles'][0]['actions']),1)
        with self.assertRaises(WorkflowError):self.api().apply_orchestration(claimed,'record-action',{
            'cycle_id':'cycle','action_id':'baseline','input_hash':next_['input_hash'],'result_ref':'invented','now_ms':1102})
    def test_regressing_check_cannot_be_reported_as_progress(self):
        subject=self.configure();subject['required_hardening_gates']=['lint'];subject['hardening_config']={'lint':{'argv':['fixture-lint']}}
        subject['hardening_proofs']={'lint':{'passed':True,'source_identity':subject['source_identity'],'config_hash':subject.get('hardening_config_hash')}}
        before=self.api().progress_facts(subject)
        subject['hardening_proofs']['lint']['passed']=False
        after=self.api().progress_facts(subject)
        self.assertFalse(self.api().progress_improved(before,after))
    def test_active_cycle_keeps_its_item_after_individual_closure(self):
        subject=self.configure();start=self.api().orchestration_next(subject,1100)
        subject=self.api().apply_orchestration(subject,'begin-cycle',{'cycle_id':'cycle','now_ms':1100,'input_hash':start['input_hash']})
        subject['unresolved_findings'][0]['status']='resolved'
        subject['unresolved_findings'].append({'id':'other','item_id':'W2','severity':'important'})
        self.assertEqual(self.api().orchestration_next(subject,1101)['scope']['item_id'],'W1')

    def test_explicit_extension_while_waiting_preserves_active_cycle_and_clock(self):
        subject=self.configure();start=self.api().orchestration_next(subject,1100)
        subject=self.api().apply_orchestration(subject,'begin-cycle',{'cycle_id':'cycle','now_ms':1100,'input_hash':start['input_hash']})
        policy={**subject['review_orchestration']['policy'],'max_elapsed_ms':10000}
        record={'policy':policy,'previous_policy_hash':digest(subject['review_orchestration']['policy']),'now_ms':6000,
            'authorization':{'approved':True,'actor_id':'fixture-user','policy_hash':digest(policy),'provenance':{'kind':'user-message','ref':'fixture:extension'}}}
        updated=self.api().apply_orchestration(subject,'extend',record)
        self.assertEqual(updated['review_orchestration']['started_ms'],1000)
        self.assertEqual(updated['review_orchestration']['cycles'],subject['review_orchestration']['cycles'])
    def test_durable_policy_and_cycle_retry_both_workflow_formats(self):
        import tempfile
        from control_store_fixtures import legacy_root
        from workflow_lib import store,sqlite_store
        for initialize in (legacy_root,sqlite_store.initialize_store):
            with self.subTest(format=initialize.__name__),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'control';initialize(root);subject=self.subject()
                store.transact(root,0,'fixture',{'kind':'fixture','payload':{'runs':{'r':subject}}})
                policy=self.configure(subject)['review_orchestration']['policy']
                record={'policy':policy,'now_ms':1000,'authorization':{'approved':True,'actor_id':'fixture-user','policy_hash':digest(policy),
                    'provenance':{'kind':'user-message','ref':'fixture:authorization'}}}
                event={'kind':'domain.repair.orchestration-configure','payload':{'request':{'run_id':'r','record':record}}}
                store.transact(root,1,'configure',event)
                state=store.read_state(root);current=state['data']['runs']['r'];next_=self.api().orchestration_next(current,1100)
                begin={'kind':'domain.repair.orchestration-begin-cycle','payload':{'request':{'run_id':'r','record':{
                    'cycle_id':'cycle','now_ms':1100,'input_hash':next_['input_hash']}}}}
                store.transact(root,2,'begin',begin);self.assertTrue(store.transact(root,2,'begin',begin)['replayed'])
                self.assertEqual(len(store.read_state(root)['data']['runs']['r']['review_orchestration']['cycles']),1)
                self.assertEqual(store.read_state(root)['data']['runs']['r']['effects'],{})

    def test_missing_tool_model_or_price_stays_blocked_until_explicit_retry(self):
        for reason in ('MODEL_UNAVAILABLE','PRICE_UNKNOWN','VERIFICATION_UNAVAILABLE'):
            subject=self.configure();next_=self.api().orchestration_next(subject,1100)
            blocked=self.api().apply_orchestration(subject,'block',{'input_hash':next_['input_hash'],'reason_code':reason,
                'required_evidence':['Actual missing prerequisite.'],'evidence_refs':['fixture:preflight']})
            self.assertEqual(self.api().orchestration_next(blocked,1101)['reason_code'],reason)
            self.assertEqual(blocked['effects'],subject['effects'])
            cleared=self.api().apply_orchestration(blocked,'clear-blocker',{'input_hash':self.api().input_binding(blocked)})
            self.assertEqual(cleared['review_orchestration']['started_ms'],1000)
            self.assertEqual(self.api().orchestration_next(cleared,1102)['kind'],'verify')
    def test_same_policy_applies_to_genuine_session_without_invented_plan(self):
        from test_standalone_review import StandaloneReviewTests
        from workflow_lib.review_sessions import read_session,transact_session
        case=StandaloneReviewTests();self.addCleanup(case.doCleanups)
        base,repo,path=case.model_fixture();state=read_session(path);subject=state['subject']
        policy=self.configure(subject)['review_orchestration']['policy']
        transact_session(path,state['version'],'orchestration-policy',{'action':'orchestration-configure','record':{
            'policy':policy,'now_ms':1000,'authorization':{'approved':True,'actor_id':'fixture-user','policy_hash':digest(policy),
                'provenance':{'kind':'user-message','ref':'fixture:session-policy'}}}})
        actual=read_session(path)['subject'];action=self.api().orchestration_next(actual,1100)
        self.assertEqual(action['kind'],'contract');self.assertEqual(action['scope']['role'],'session')
        self.assertNotIn('plan',actual);self.assertNotIn('spec',actual);self.assertNotIn('runs',actual)

    def test_old_or_foreign_implementer_receipt_cannot_finish_action(self):
        subject=self.configure();action={'kind':'implement','scope':{'role':'item','item_id':'W1'},'source_identity':subject['source_identity'],'claimed_ms':1100}
        subject['native_invocations']={'worker':{'status':'completed','stage':'implementation'}}
        subject['model_receipts']={'worker':{'status':'allow','invocation_ref':'fixture:worker','scope':{'actor_id':'writer','item_id':'W2','token':'unrelated'}}}
        subject['effects']={'worker':{'source_identity':subject['source_identity'],'claimed_at_ms':1000}}
        with self.assertRaises(WorkflowError):self.api()._require_result(subject,action,'worker')
