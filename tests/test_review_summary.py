"""Deterministic metadata summaries; model receipts below are labeled fixtures."""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))

class ReviewSummaryTests(unittest.TestCase):
    def fixture(self):
        from test_adversarial_reviews import AdversarialReviewTests
        return AdversarialReviewTests().complete('branch')
    def test_absent_escape_and_cost_reports_are_unknown(self):
        from workflow_lib.review_summary import summarize_review
        result=summarize_review({'id':'fixture'})
        self.assertIsNone(result['confirmed_escaped_defects']);self.assertIsNone(result['observed_cost'])
        self.assertGreater(result['unknown_measurements']['observed_cost'],0)
    def test_overlapping_invocations_have_distinct_wall_and_summed_time(self):
        from workflow_lib.review_summary import summarize_review
        subject={'id':'fixture','model_receipts':{'a':{'scope':{'role':'branch-reviewer'},'started_ms':0,'finished_ms':10},
            'b':{'scope':{'role':'branch-reviewer'},'started_ms':5,'finished_ms':15}},
            'effects':{'a':{'estimated_cost':1,'observed_cost':.5},'b':{'estimated_cost':2}}}
        result=summarize_review(subject)
        self.assertEqual(result['review_wall_ms'],15);self.assertEqual(result['summed_invocation_ms'],20)
        self.assertIsNone(result['observed_cost']);self.assertEqual(result['known_subtotals']['observed_cost'],.5)
        self.assertEqual(result['estimated_reserved_cost'],3)
        self.assertEqual(result['unknown_measurements']['observed_cost'],1)
    def test_same_exact_package_reuses_original_without_dispatch(self):
        from workflow_lib.review_summary import review_reuse
        subject,package,reports=self.fixture()
        with patch('workflow_lib.native_runtime.invoke',side_effect=AssertionError('Reuse must not invoke a model')):
            result=review_reuse(subject,package,reports[0])
        self.assertTrue(result['reusable'],result);self.assertFalse(result['executed'])
        self.assertEqual(result['receipt'],reports[0]);self.assertEqual(result['original_invocation_ref'],reports[0]['invocation_ref'])
    def test_changed_scope_or_compliance_cannot_reuse(self):
        from workflow_lib.review_summary import review_reuse
        for change in ('source','dependency','contract','question','risk','policy','model','stage','head'):
            subject,package,reports=self.fixture();receipt=reports[0]
            if change=='source':subject['source_identity']='changed'
            if change=='dependency':subject['plan']['work_items'][0]['dependencies']=['new-dependency']
            if change=='contract':subject['implementation_contracts']={}
            if change=='question':subject['clarifications']={'q':{'id':'q','version':1,'status':'pending','scope':None,'text':'Which rule?'}}
            if change=='risk':subject['risk_assessments']={__import__('workflow_lib.document_units',fromlist=['digest']).digest({'role':'branch'}):{'risk':{'fixture_changed_evidence':['fixture:new-boundary']}}}
            if change=='policy':subject['review_policy']['revision']=99
            if change=='model':subject['model_overrides']=[{'allowed_models':['other']}]
            if change=='stage':package=copy.deepcopy(package);package['role']='pr'
            if change=='head':package=copy.deepcopy(package);package['snapshot']={'head_sha':'different'}
            with self.subTest(change=change):self.assertFalse(review_reuse(subject,package,receipt)['reusable'])
    def test_metadata_summary_does_not_hydrate_packages(self):
        from workflow_lib.review_summary import summarize_review
        subject,package,reports=self.fixture()
        with patch('workflow_lib.stored_records.require_package',side_effect=AssertionError('No source hydration')):
            result=summarize_review(subject)
        self.assertNotIn('review_packages',result);self.assertNotIn('source',result)
    def test_canonical_findings_keep_separate_dispositions_and_unknown_escapes(self):
        from workflow_lib.review_summary import summarize_review
        subject={'id':'fixture','unresolved_findings':[
            {'id':'a','severity':'important','requested_correction':'Fix','evidence_refs':['report:a'],'status':'open'},
            {'id':'alias','severity':'important','requested_correction':'Fix','evidence_refs':['report:b'],'status':'open'},
            {'id':'waiver','severity':'minor','requested_correction':'Fix','evidence_refs':['report:c'],'status':'waived'},
            {'id':'reject','severity':'info','question':'Which?','evidence_refs':['report:d'],'status':'rejected'}],
            'finding_index':{'aliases':{'a':{'canonical_id':'canonical'},'alias':{'canonical_id':'canonical'}}},
            'review_orchestration':{'cycles':[{'status':'recorded','made_progress':False}], 'blocker':{'reason_code':'NO_PROGRESS'}},
            'clarifications':{'q':{'id':'q','version':1,'status':'pending','scope':None,'text':'Which?'}}}
        result=summarize_review(subject)
        self.assertEqual(result['unique_actionable_findings'],3);self.assertEqual(result['duplicate_aliases'],1)
        self.assertEqual(result['finding_dispositions']['waived'],1);self.assertEqual(result['finding_dispositions']['rejected'],1)
        self.assertEqual(result['repair_cycles'],1);self.assertEqual(result['no_progress_stops'],1);self.assertEqual(result['blocking_questions'],1)
        self.assertIsNone(result['confirmed_escaped_defects'])
    def test_later_explicit_escaped_report_can_be_recorded_after_completion(self):
        from workflow_lib.review_summary import record_escaped_defect,summarize_review
        from workflow_lib.enforcement_events import apply_enforcement
        from workflow_lib.store import WorkflowError
        subject,package,reports=self.fixture();subject['status']='complete'
        record={'id':'escape','review_id':reports[0]['review_id'],'report_ref':'fixture:user-incident-1',
            'confirmed':True,'provenance':{'kind':'user-message','ref':'fixture:actual-report','actor_id':'fixture-user'}}
        updated=apply_enforcement(subject,'report-escaped-defect',record)
        self.assertEqual(summarize_review(updated)['confirmed_escaped_defects'],1)
        self.assertEqual(record_escaped_defect(updated,record),updated)
        with self.assertRaises(WorkflowError):record_escaped_defect(subject,{**record,'review_id':'missing'})
        with self.assertRaises(WorkflowError):record_escaped_defect(subject,{**record,'provenance':{'kind':'assumption'}})

    def test_public_summary_is_read_only_for_workflow_and_standalone(self):
        import json,subprocess
        from test_review_driver import ReviewDriverTests
        from workflow_lib.review_sessions import read_session
        from workflow_lib.storage_access import read_current
        case=ReviewDriverTests();self.addCleanup(case.doCleanups)
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        for kind in ('session','workflow'):
            base,repo,location,request=case.owned_session() if kind=='session' else case.owned_workflow(2)
            scope=['--session',str(location)] if kind=='session' else ['--root',str(location),'--run-id','run']
            def version():return read_session(location)['version'] if kind=='session' else read_current(location,run_id='run')['version']
            before=version();result=subprocess.run([sys.executable,str(entry),'review','summary',*scope],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIsNone(json.loads(result.stdout)['confirmed_escaped_defects']);self.assertEqual(version(),before)
            self.assertFalse((base/'worker-count').exists())
    def test_reuse_record_keeps_original_invocation_without_new_coverage(self):
        from workflow_lib.review_summary import record_reuse,summarize_review
        subject,package,reports=self.fixture();before=copy.deepcopy(subject['reviews'])
        result=record_reuse(subject,{'id':'reuse-1','review_id':reports[0]['review_id']})
        self.assertEqual(result['reviews'],before);self.assertEqual(result['model_receipts'],subject['model_receipts'])
        self.assertEqual(summarize_review(result)['review_reuses'],1)
        self.assertEqual(result['review_reuse_records']['reuse-1']['receipt'],reports[0])

    def test_prelaunch_blocked_receipt_is_not_an_executed_model_invocation(self):
        from workflow_lib.review_summary import summarize_review
        result=summarize_review({'id':'fixture','model_receipts':{'blocked':{'dispatch':False,'status':'block','scope':{'role':'branch-reviewer'}}}})
        self.assertEqual(result['model_invocations'],0)
        self.assertEqual(result['model_attempt_receipts'],1)

    def test_no_progress_stop_counts_survive_explicit_resume(self):
        from test_review_orchestration import OrchestrationTests
        from workflow_lib.review_orchestration import apply_orchestration,input_binding
        from workflow_lib.review_summary import summarize_review
        subject=OrchestrationTests().configure()
        for number in (1,2):
            subject=apply_orchestration(subject,'block',{'input_hash':input_binding(subject),'reason_code':'NO_PROGRESS',
                'required_evidence':['Explicit authorized extension or amended scope.'],'evidence_refs':['fixture:actual-stop-'+str(number)]})
            self.assertEqual(summarize_review(subject)['no_progress_stops'],number)
            subject=apply_orchestration(subject,'clear-blocker',{'input_hash':input_binding(subject)})
            self.assertEqual(summarize_review(subject)['no_progress_stops'],number)

    def test_supported_native_nested_usage_is_measured_with_shared_normalizer(self):
        from workflow_lib.review_summary import summarize_review
        usage={'total':{'inputTokens':10,'cachedInputTokens':5,'outputTokens':2,'totalTokens':12}}
        result=summarize_review({'id':'fixture','model_receipts':{'native':{'usage':usage}}})
        self.assertEqual(result['observed_tokens'],{'input_tokens':10,'cached_tokens':5,'output_tokens':2,'total_tokens':12})
        self.assertEqual(result['unknown_measurements']['model_usage'],0)
        zeros=summarize_review({'id':'fixture','model_receipts':{'native':{'usage':{'input_tokens':0,'cached_input_tokens':0,'output_tokens':0}}}})
        self.assertEqual(zeros['observed_tokens'],{'input_tokens':0,'cached_tokens':0,'output_tokens':0})
