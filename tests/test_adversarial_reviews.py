"""Synthetic durable review facts; actual model transports are tested separately."""
import copy,importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError
from workflow_lib.document_units import digest

class AdversarialReviewTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.adversarial_reviews'))
        from workflow_lib import adversarial_reviews
        return adversarial_reviews
    def fixture(self,role='item'):
        from test_test_challenges import ChallengeTests
        from workflow_lib.review_dispatch import specialist_scope
        from workflow_lib.implementation_contracts import contract_binding
        from workflow_lib.review_enforcement import review_bindings
        subject,_,original=ChallengeTests().quality_fixture()
        subject.update(id='r',state_version=1,review_ids=[],actors={'implementer':'author'},unresolved_findings=[])
        subject['verifier_proofs']={'g':{'passed':True,'fresh':True,'semantic_status':'reviewed','evidence_id':'g','item_id':'W1','token':'attempt','source_identity':'after'}}
        scope={'role':role,**({'item_id':'W1'} if role=='item' else {})}
        package={**scope,'source_identity':'after','input_paths':['test.py'],'review_inputs':[{'repo_id':'repo','path':'test.py'}],'spec_hash':'spec',
            'enforcement_bindings':review_bindings(subject,role,scope.get('item_id'),live=False),
            'adversarial_bindings':self.api().adversarial_bindings(subject,scope)}
        if role=='pr':
            package['changed_files']=['test.py']
            package['snapshot']={'checks':[{'status':'completed','conclusion':'success'}],'mergeable':True}
        package['package_hash']=digest(package)
        subject['review_packages']={package['package_hash']:package};subject['model_receipts']={}
        reports=[]
        for ordinal,perspective in enumerate(('code','test','architecture','security'),1):
            binding={'role':role+'-reviewer','perspective':perspective,**({'item_id':'W1'} if role=='item' else {})}
            model_scope={**binding,'actor_id':role+'-'+perspective,'package_hash':package['package_hash'],
                'review_scope':specialist_scope(subject,binding)}
            invocation=role+'-'+perspective;selected={'provider':'openai','model':'fixture-eligible','effort':'high'}
            subject['model_receipts'][invocation]={'invocation_id':invocation,'invocation_ref':'fixture:'+invocation,
                'policy_revision':0,'review_sequence':ordinal,'status':'allow','dispatch':True,'diagnostic':False,'scope':model_scope,'profile':'deep-reasoning','capability_validated':True,
                'validation_ref':'fixture:validation','resolved':selected,'observed':dict(selected),'observation_source':'host-invocation-metadata'}
            report={**scope,'review_id':invocation,'actor_id':model_scope['actor_id'],'invocation_ref':'fixture:'+invocation,
                'model_invocation_id':invocation,'package_hash':package['package_hash'],'perspective':perspective,
                'verdict':'pass','findings':[],'fresh':True,'reviewed_inputs':copy.deepcopy(package['review_inputs']),
                'review_input_ref':self.api().review_input_id(package),'adversarial_bindings':copy.deepcopy(package['adversarial_bindings'])}
            if role=='pr':report['reviewed_files']=['test.py']
            if perspective=='test':
                report['test_quality']=copy.deepcopy(original['test_quality'])
                report['test_quality']['contract_binding']=contract_binding(subject,scope)
                if role!='item':report['test_quality']['behaviors'][0]['item_id']='W1'
                report['test_oracles']=copy.deepcopy(original['test_oracles'])
            if perspective=='code' and role in {'branch','pr','session'}:
                report['risk_confirmation']={'assessment_hash':model_scope['review_scope']['assessment_hash'],
                    'disposition':'conservative','evidence_refs':['package:'+package['package_hash']],
                    'reason':'Unknown fixture risk retains all four perspectives.'}
            if perspective=='test':
                from workflow_lib.oracle_acceptance import validate_oracle_acceptance
                report['semantic_approvals']=validate_oracle_acceptance(subject,package,report)
            fact=self.api().expected_review_input_validation(package)
            subject['model_receipts'][invocation]['review_input_validation']={'before':fact,'after':fact}
            subject['model_receipts'][invocation]['review_report_hash']=self.api().semantic_report_hash(report)
            reports.append(report)
        return subject,package,reports
    def complete(self,role='item'):
        subject,package,reports=self.fixture(role);subject['reviews']={role:reports}
        return subject,package,reports
    def test_missing_package_cannot_be_a_specialist_pass(self):
        with self.assertRaises(WorkflowError):self.api().validate_adversarial_review({'id':'fixture'},{},{'verdict':'pass','perspective':'security'})
    def test_all_independent_required_perspectives_complete_current_scope(self):
        subject,package,reports=self.complete()
        for report in reports:self.assertEqual(self.api().validate_adversarial_review(subject,package,report)['status'],'allow')
        self.assertTrue(self.api().review_coverage(subject,'item','W1')['complete'])
    def test_one_invocation_cannot_cover_four_perspectives(self):
        subject,package,reports=self.complete()
        for report in reports[1:]:report['invocation_ref']=reports[0]['invocation_ref']
        self.assertFalse(self.api().review_coverage(subject,'item','W1')['complete'])
    def test_omitting_code_or_test_is_incomplete(self):
        for omitted in ('code','test'):
            subject,package,reports=self.complete();subject['reviews']['item']=[r for r in reports if r['perspective']!=omitted]
            coverage=self.api().review_coverage(subject,'item','W1')
            self.assertFalse(coverage['complete']);self.assertIn(omitted,coverage['missing_perspectives'])
    def test_item_pass_is_not_branch_pass(self):
        subject,package,reports=self.complete()
        self.assertFalse(self.api().review_coverage(subject,'branch')['complete'])
    def test_later_block_stops_delivery(self):
        subject,package,reports=self.complete();later=copy.deepcopy(reports[-1])
        later.update(review_id='later',invocation_ref='fixture:later',model_invocation_id='later',verdict='block')
        subject['model_receipts']['later']={**copy.deepcopy(subject['model_receipts']['item-security']),
            'invocation_id':'later','invocation_ref':'fixture:later','review_sequence':5}
        subject['model_receipts']['later']['review_report_hash']=self.api().semantic_report_hash(later)
        subject['reviews']['item'].append(later)
        self.assertFalse(self.api().review_coverage(subject,'item','W1')['complete'])
    def test_wrong_item_source_policy_or_contract_cannot_count(self):
        for case in ('item','source','policy','contract'):
            subject,package,reports=self.complete()
            if case=='item':reports[-1]['item_id']='W2'
            if case=='source':subject['source_identity']='changed'
            if case=='policy':subject['review_policy']['revision']+=1
            if case=='contract':subject['implementation_contracts']['item:W1']['non_goals'].append('new scope')
            with self.subTest(case=case):self.assertFalse(self.api().review_coverage(subject,'item','W1')['complete'])
    def test_branch_needs_independent_risk_confirmation_in_existing_code_round(self):
        subject,package,reports=self.complete('branch')
        self.assertTrue(self.api().review_coverage(subject,'branch')['complete'])
        reports[0].pop('risk_confirmation')
        self.assertFalse(self.api().review_coverage(subject,'branch')['complete'])
    def test_critical_important_and_undisposed_minor_block_pass(self):
        for severity in ('critical','important','minor'):
            subject,package,reports=self.fixture();report=reports[-1]
            report['findings']=[{'id':'f','severity':severity,'path':'test.py','line':1,
                'evidence_refs':['package:'+package['package_hash']],'failure_scenario':'Return wrong value.',
                'impact':'Incorrect retention.','requested_correction':'Use the approved rule.'}]
            with self.subTest(severity=severity),self.assertRaises(WorkflowError):self.api().validate_adversarial_review(subject,package,report)
    def test_failed_cheap_check_cannot_be_hidden_by_passing_report(self):
        subject,package,reports=self.fixture();subject['hardening_config']={'lint':{'pre_review':True,'kind':'lint'}}
        with self.assertRaises(WorkflowError):self.api().validate_adversarial_review(subject,package,reports[-1])
    def test_diagnostic_assessment_finishes_without_counting_as_pass(self):
        subject,package,reports=self.fixture();report=reports[-1];report.update(verdict='block',diagnostic=True)
        subject['implementation_contracts']={}
        # A fresh diagnostic package is still bound to its actual missing inputs.
        scope={'role':'item','item_id':'W1'};package['adversarial_bindings']=self.api().adversarial_bindings(subject,scope)
        report['adversarial_bindings']=copy.deepcopy(package['adversarial_bindings'])
        subject['model_receipts'][report['model_invocation_id']]['review_report_hash']=self.api().semantic_report_hash(report)
        result=self.api().validate_adversarial_review(subject,package,report)
        self.assertFalse(result['passing']);self.assertTrue(result['diagnostic'])

    def test_actual_model_receipt_cannot_authorize_an_invented_report(self):
        subject,package,reports=self.fixture();report=reports[-1]
        subject['model_receipts'][report['model_invocation_id']]['review_report_hash']='actual-different-output'
        with self.assertRaises(WorkflowError):self.api().validate_adversarial_review(subject,package,report)

    def test_direct_event_cannot_bypass_required_coverage(self):
        from workflow_lib.store import _apply_event,_empty
        from workflow_lib.oracle_acceptance import validate_oracle_acceptance
        subject,package,reports=self.fixture();report=reports[1]
        report['semantic_approvals']=validate_oracle_acceptance(subject,package,report)
        subject['verifier_proofs']={'g':{'passed':True,'fresh':True,'semantic_status':'pending'}}
        report.pop('adversarial_bindings')
        state=_empty();state['data']['runs']={'r':subject}
        with self.assertRaises(WorkflowError) as caught:
            _apply_event(state,{'kind':'review.recorded','payload':{'run_id':'r','review':report}})
        self.assertEqual(caught.exception.code,'ADVERSARIAL_REVIEW_BLOCKED')
    def test_single_test_review_cannot_make_the_item_gate_current(self):
        from workflow_lib.gates import _review_current
        from workflow_lib.oracle_acceptance import validate_oracle_acceptance
        subject,package,reports=self.fixture();report=reports[1]
        report['semantic_approvals']=validate_oracle_acceptance(subject,package,report)
        subject['verifier_proofs']={'g':{'passed':True,'fresh':True,'semantic_status':'reviewed'}}
        subject['reviews']={'item':[report]}
        self.assertFalse(_review_current(subject,report,False))

    def test_diagnostic_invocation_cannot_be_relabelled_as_an_accepted_pass(self):
        subject,package,reports=self.fixture();report=reports[-1]
        subject['model_receipts'][report['model_invocation_id']]['diagnostic']=True
        with self.assertRaises(WorkflowError):self.api().validate_adversarial_review(subject,package,report)

    def test_public_producer_records_actual_diagnostic_without_advancing_scope(self):
        import json
        from test_review_dispatch import ReviewDispatchTests
        from workflow_lib.reviews import record_review
        from workflow_lib.store import read_state,transact
        fixture=ReviewDispatchTests()
        self.addCleanup(fixture.doCleanups)
        root,repo,request,backend=fixture.native_fixture()
        state=read_state(root);package=next(iter(state['data']['runs']['run']['review_packages'].values()))
        report={'package_hash':package['package_hash'],'perspective':'security','diagnostic':True,'verdict':'block','findings':[]}
        backend.invoke.return_value['output']=json.dumps(report)
        receipt=fixture.native_call(root,request,backend)
        state=read_state(root);subject=state['data']['runs']['run'];subject.setdefault('review_ids',[])
        review=record_review(subject,package['package_hash'],{'role':'branch','actor_id':'independent',
            'invocation_ref':receipt['invocation_ref'],'model_invocation_id':receipt['invocation_id'],'tool_available':True},report)
        # Owned historical seed lacks only the normally initialized review_ids.
        # Use pure replay to isolate durable review validation from fixture setup.
        from workflow_lib.store import _apply_event
        _apply_event(state,{'kind':'review.recorded','payload':{'run_id':'run','review':review}})
        self.assertEqual(state['data']['runs']['run']['reviews']['branch'][0]['verdict'],'block')
        self.assertFalse(self.api().review_coverage(state['data']['runs']['run'],'branch')['complete'])

    def test_reported_blocker_survives_a_later_passing_report(self):
        from workflow_lib.store import _apply_event,_empty
        subject,package,reports=self.fixture();report=reports[-1]
        report.update(verdict='request-changes',semantic_approvals={})
        report['findings']=[{'id':'retention-defect','severity':'important','path':'test.py','line':1,
            'evidence_refs':['package:'+package['package_hash']],'failure_scenario':'Sixty is returned instead of thirty.',
            'impact':'Incorrect retention.','requested_correction':'Apply the approved thirty-day rule.'}]
        subject['model_receipts'][report['model_invocation_id']]['review_report_hash']=self.api().semantic_report_hash(report)
        state=_empty();state['data']['runs']={'r':subject}
        _apply_event(state,{'kind':'review.recorded','payload':{'run_id':'r','review':report}})
        stored=state['data']['runs']['r']
        self.assertEqual([f['id'] for f in stored['unresolved_findings']],['retention-defect'])
        later=copy.deepcopy(report);later.update(review_id='later',invocation_ref='fixture:later',model_invocation_id='later',verdict='pass',findings=[])
        stored['model_receipts']['later']={**copy.deepcopy(stored['model_receipts']['item-security']),
            'invocation_id':'later','invocation_ref':'fixture:later','review_sequence':5,'review_report_hash':self.api().semantic_report_hash(later)}
        stored['reviews']['item'].append(later)
        self.assertIn('retention-defect',self.api().review_coverage(stored,'item','W1')['blocking_findings'])
    def test_deferred_minor_requires_visible_reason_and_remains_in_report(self):
        subject,package,reports=self.fixture();report=reports[-1]
        report['findings']=[{'id':'minor','severity':'minor','path':'test.py','line':1,'evidence_refs':['fixture:location'],
            'failure_scenario':'Error text is unclear.','impact':'Less useful diagnostics.','requested_correction':'Improve wording.',
            'disposition':{'status':'deferred','reason':'No behavior impact; follow up separately.'}}]
        subject['model_receipts'][report['model_invocation_id']]['review_report_hash']=self.api().semantic_report_hash(report)
        result=self.api().validate_adversarial_review(subject,package,report)
        self.assertTrue(result['passing']);self.assertEqual(result['findings'][0]['disposition']['status'],'deferred')

    def test_report_output_findings_do_not_invalidate_unchanged_input_obligations(self):
        from workflow_lib.review_enforcement import review_bindings_current
        subject,package,reports=self.fixture()
        subject['unresolved_findings']=[{'id':'new-output','status':'open','severity':'important','item_id':'W1'}]
        self.assertTrue(review_bindings_current(subject,package,live=False))
        subject['unresolved_findings']=[]
        # Inputs present when packaged cannot disappear or change silently.
        package['enforcement_bindings']['logical']['findings']={'old':{'finding_hash':'bound'}}
        self.assertFalse(review_bindings_current(subject,package,live=False))

    def test_acceptance_cannot_approve_while_configured_prerequisite_is_missing(self):
        from workflow_lib.store import _apply_event,_empty
        subject,_,_=self.fixture();subject['hardening_config']={'lint':{'kind':'lint','pre_review':True}}
        scope={'role':'acceptance'}
        package={**scope,'source_identity':'after','adversarial_bindings':self.api().adversarial_bindings(subject,scope)}
        package['package_hash']=digest(package);subject['review_packages']={package['package_hash']:package}
        report={**scope,'package_hash':package['package_hash'],'review_id':'acceptance','actor_id':'requirements-reviewer',
            'invocation_ref':'fixture:acceptance','verdict':'pass','findings':[],
            'adversarial_bindings':copy.deepcopy(package['adversarial_bindings'])}
        state=_empty();state['data']['runs']={'r':subject}
        with self.assertRaises(WorkflowError) as caught:_apply_event(state,{'kind':'review.recorded','payload':{'run_id':'r','review':report}})
        self.assertEqual(caught.exception.code,'ADVERSARIAL_REVIEW_BLOCKED')

    def test_lightweight_item_exemptions_advance_only_to_branch_confirmation(self):
        from unittest.mock import patch
        from workflow_lib.gates import gate_status
        from workflow_lib.review_policy import record_risk,review_bindings,PERSPECTIVES
        subject,package,reports=self.fixture();scope={'role':'item','item_id':'W1'}
        risk={'schema_version':1,'bindings':review_bindings(subject,scope),'classification':'lightweight',
            'scope_evidence_refs':['fixture:explicit-scope'],'triggers':[],'perspectives':{
                p:{'applicability':'not-applicable','reason':'Fixture no behavior impact.','evidence_refs':['fixture:scope']} for p in PERSPECTIVES}}
        subject=record_risk(subject,scope,risk);subject['items']['W1']['status']='complete'
        subject['reviews']={}
        self.assertTrue(self.api().review_coverage(subject,'item','W1')['complete'])
        # Isolate the review-stage predicate from separately tested live proof I/O.
        with patch('workflow_lib.gates._required_proof',return_value=True):status=gate_status(subject,live=False)
        self.assertEqual(status['stage'],'branch-review');self.assertFalse(status['can_advance'])

    def test_missing_or_incomplete_reviewed_input_claim_cannot_pass(self):
        for case in ('missing','omitted','foreign'):
            subject,package,reports=self.fixture();report=reports[-1]
            if case=='missing':report.pop('reviewed_inputs',None)
            if case=='omitted':report['reviewed_inputs']=[]
            if case=='foreign':report['reviewed_inputs']=[{'repo_id':'foreign','path':'test.py'}]
            subject['model_receipts'][report['model_invocation_id']]['review_report_hash']=self.api().semantic_report_hash(report)
            with self.subTest(case=case),self.assertRaises(WorkflowError):self.api().validate_adversarial_review(subject,package,report)
    def test_current_reviewer_can_refresh_its_own_perspective_for_correction(self):
        from test_review_dispatch import ReviewDispatchTests
        from workflow_lib.hosts import apply_host_event
        from workflow_lib.store import read_state
        fixture=ReviewDispatchTests();self.addCleanup(fixture.doCleanups)
        root,repo,request,backend=fixture.native_fixture();data=read_state(root)['data'];binding=data['host_bindings']['review']
        data['runs']['run']['actors']['branch_security_reviewer']='independent'
        data['runs']['run']['reviews']={'branch':[{'actor_id':'independent','perspective':'security','role':'branch'}]}
        result=apply_host_event(data,'attach',{**binding,'refresh':True})
        self.assertEqual(result['revision'],2);self.assertEqual(result['perspective'],'security')

    def test_newer_real_review_output_cannot_leave_an_old_pass_effective(self):
        subject,package,reports=self.complete();old=subject['model_receipts']['item-security']
        subject['model_receipts']['new-review']={**copy.deepcopy(old),'invocation_id':'new-review',
            'invocation_ref':'fixture:new-review','review_sequence':99,'review_report_hash':None}
        coverage=self.api().review_coverage(subject,'item','W1')
        self.assertFalse(coverage['complete']);self.assertIn('security',coverage['missing_perspectives'])

    def test_coverage_needs_registered_semantic_approval_not_only_raw_green(self):
        subject,package,reports=self.complete()
        reports[1].pop('semantic_approvals',None);subject['verifier_proofs']={}
        self.assertFalse(self.api().review_coverage(subject,'item','W1')['complete'])

    def test_hosted_pr_uses_same_durable_four_perspective_and_oracle_rules(self):
        from workflow_lib.pr_reviews import record_pr_review
        from workflow_lib.store import _apply_event,_empty
        subject,package,reports=self.fixture('pr');state=_empty();state['data']['runs']={'r':subject}
        for index,report in enumerate(reports):
            current=state['data']['runs']['r']
            actual=record_pr_review(current,package['package_hash'],{'role':'pr','actor_id':report['actor_id'],
                'invocation_ref':report['invocation_ref'],'model_invocation_id':report['model_invocation_id'],'tool_available':True},report)
            _apply_event(state,{'kind':'review.recorded','payload':{'run_id':'r','review':actual}})
            self.assertEqual(self.api().review_coverage(state['data']['runs']['r'],'pr')['complete'],index==3)

    def test_pr_report_contract_retains_the_exact_pr_verdict_vocabulary(self):
        contract=self.api().report_contract('pr')
        self.assertEqual(set(contract['verdicts']),{'pass','changes-requested','human-decision-required','blocked'})
        self.assertIn('reason',contract['findings_required'])
