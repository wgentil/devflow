"""Explicit synthetic findings/reviewer receipts; no live provider is used."""
import copy,importlib.util,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError
from workflow_lib.finding_closure import finding_hash

class FindingIndexTests(unittest.TestCase):
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.finding_index'))
        from workflow_lib import finding_index
        return finding_index
    def subject(self):
        findings=[{'id':'f1','status':'open','severity':'important','item_id':'W1','path':'retention.py','line':1,
            'failure_scenario':'Return sixty for the first caller.','impact':'Wrong retention.','requested_correction':'Use the approved rule.',
            'obligations':['R1'],'required_perspectives':['code'],'evidence_refs':['fixture:caller-one']},
            {'id':'f2','status':'open','severity':'critical','item_id':'W2','path':'retention.py','line':2,
            'failure_scenario':'Return sixty for the second caller.','impact':'Wrong retention.','requested_correction':'Use the approved rule.',
            'obligations':['R2'],'required_perspectives':['test'],'evidence_refs':['fixture:caller-two']}]
        subject={'id':'r','status':'active','source_identity':'source','state_version':1,
            'enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1},
            'plan':{'spec_hash':'spec','work_items':[{'id':i,'kind':'code','dependencies':[],'requirement_ids':['R1' if i=='W1' else 'R2']} for i in ('W1','W2')]},
            'actors':{'implementer':'author'},'items':{i:{'attempts':[{'token':'t'+i}]} for i in ('W1','W2')},
            'unresolved_findings':findings,'effects':{'spent':{'status':'completed','estimated_cost':1}},
            'effect_policy':{'max_attempts':3,'max_estimated_cost':3,'max_elapsed_ms':1000},
            'repair_cycles':[{'cycle_id':'spent','status':'completed'}]}
        from workflow_lib.review_enforcement import review_bindings
        package={'package_hash':'pkg','role':'branch','source_identity':'source','enforcement_bindings':review_bindings(subject,'branch')}
        equivalence={'id':'same-default','member_ids':['f1','f2'],'source_identity':'source',
            'finding_hashes':{f['id']:finding_hash(f) for f in findings},
            'same_failure':{'trigger':'Both callers use retention().','observed':'Sixty days.','expected':'Thirty days.'},
            'same_correction':'Correct the shared default.','reason':'The same owned function controls both observations.',
            'evidence_refs':['fixture:shared-function','fixture:caller-one','fixture:caller-two']}
        review={'review_id':'review','role':'branch','perspective':'code','actor_id':'independent','invocation_ref':'fixture:actual-review',
            'package_hash':'pkg','fresh':True,'verdict':'request-changes','findings':[], 'finding_equivalences':[equivalence]}
        subject.update(review_packages={'pkg':package},reviews={'branch':[review]})
        return subject
    def indexed(self):return self.api().index_findings(self.subject(),[])
    def request(self):return {'review_id':'review','equivalence_id':'same-default','member_ids':['f1','f2']}
    def test_similar_text_is_not_equivalence(self):
        subject=self.indexed()
        self.assertEqual(len(subject['finding_index']['canonical']),2)
        subject['reviews']['branch'][0]['finding_equivalences']=[]
        with self.assertRaises(WorkflowError):self.api().consolidate_findings(subject,self.request())
    def test_consolidation_retains_every_member_obligation(self):
        subject=self.api().consolidate_findings(self.indexed(),self.request());index=subject['finding_index']
        aliases=index['aliases'];self.assertEqual(aliases['f1']['canonical_id'],aliases['f2']['canonical_id'])
        canonical=index['canonical'][aliases['f1']['canonical_id']]
        self.assertEqual(set(canonical['member_ids']),{'f1','f2'});self.assertEqual(canonical['severity'],'critical')
        self.assertEqual(set(canonical['item_ids']),{'W1','W2'})
        self.assertEqual(set(canonical['required_perspectives']),{'code','test'})
        self.assertEqual(len(canonical['obligation_hashes']),2)
        for finding in subject['unresolved_findings']:
            self.assertEqual(aliases[finding['id']]['original_finding_hash'],finding_hash(finding))
            self.assertEqual(finding['status'],'open')
    def test_unresolved_disagreement_business_question_and_stale_source_block_merge(self):
        for case in ('disagreement','question','source','hash'):
            subject=self.indexed()
            if case=='disagreement':subject['unresolved_findings'][0]['unresolved_disagreements']=['business-rule']
            if case=='question':subject['unresolved_findings'][0]['question']='Which retention rule applies?'
            if case=='source':subject['source_identity']='different'
            if case=='hash':subject['reviews']['branch'][0]['finding_equivalences'][0]['finding_hashes']['f1']='different'
            with self.subTest(case=case),self.assertRaises(WorkflowError):self.api().consolidate_findings(subject,self.request())
    def test_renaming_does_not_reset_progress_or_budget(self):
        before=self.indexed();renamed=copy.deepcopy(self.subject());renamed['unresolved_findings'][0]['id']='new-id'
        after=self.api().index_findings(renamed,[])
        self.assertEqual(self.api().finding_progress(before)['verified_progress_hash'],self.api().finding_progress(after)['verified_progress_hash'])
        self.assertEqual(after['effects'],before['effects']);self.assertEqual(after['repair_cycles'],before['repair_cycles'])
        merged=self.api().consolidate_findings(before,self.request())
        self.assertEqual(self.api().finding_progress(before)['verified_progress_hash'],self.api().finding_progress(merged)['verified_progress_hash'])
    def test_waived_rejected_deferred_and_resolved_are_not_interchangeable(self):
        signatures={}
        for status in ('open','waived','rejected','deferred','resolved'):
            subject=self.subject();subject['unresolved_findings'][0]['status']=status
            if status=='resolved':subject['unresolved_findings'][0]['resolution']={'proof_ids':['actual-proof'],'review_ids':['review'],'source_identity':'source'}
            indexed=self.api().index_findings(subject,[]);progress=self.api().finding_progress(indexed)
            self.assertIn(status,progress['outcomes']);signatures[status]=progress['verified_progress_hash']
        self.assertEqual(signatures['open'],signatures['waived']);self.assertEqual(signatures['open'],signatures['rejected'])
        self.assertNotEqual(signatures['open'],signatures['resolved'])
    def test_members_cannot_disappear_and_merge_cannot_clear_spending(self):
        subject=self.indexed();subject['unresolved_findings'].pop()
        with self.assertRaises(WorkflowError):self.api().index_findings(subject,[])
        subject=self.indexed();request={**self.request(),'effects':{}}
        with self.assertRaises(WorkflowError):self.api().consolidate_findings(subject,request)

    def compound(self):
        from test_finding_closure import ClosureTests
        from workflow_lib.review_enforcement import review_bindings
        subject=ClosureTests().fixture();subject.update(status='active')
        first=subject['unresolved_findings'][0];second={**copy.deepcopy(first),'id':'second','item_id':'W2','obligations':['o3']}
        subject['unresolved_findings'].append(second);subject['plan']['work_items'].append({'id':'W2','kind':'code','dependencies':[]})
        subject['items']['W2']={'attempts':[{'token':'t2'}]}
        subject['corrections']['second']={'source_identity':'sha','proof_ids':['p'],'finding_hash':finding_hash(second),'rationale':'Fixture common correction.'}
        review=subject['reviews']['branch'][0];review['role']='branch'
        review['closure_dispositions'].append({'finding_id':'second','source_identity':'sha','finding_hash':finding_hash(second),
            'obligations':['o3'],'disposition':'resolved','proof_ids':['p'],'proof_applicability':{'p':['o3']}})
        review['finding_equivalences']=[{'id':'equivalence','member_ids':['f','second'],'source_identity':'sha',
            'finding_hashes':{f['id']:finding_hash(f) for f in subject['unresolved_findings']},
            'same_failure':{'trigger':'shared fixture','observed':'wrong value','expected':'approved value'},
            'same_correction':'shared implementation','reason':'Actual fixture review.', 'evidence_refs':['fixture:both-callers']}]
        subject['review_packages']['pkg']['enforcement_bindings']=review_bindings(subject,'branch')
        subject=self.api().consolidate_findings(self.api().index_findings(subject,[]),{
            'review_id':'rev','equivalence_id':'equivalence','member_ids':['f','second']})
        canonical=subject['finding_index']['aliases']['f']['canonical_id']
        record={'canonical_id':canonical,'member_closures':[{'finding_id':'f','review_id':'rev'},{'finding_id':'second','review_id':'rev'}]}
        return subject,record
    def test_cross_item_member_needs_its_own_current_proof(self):
        subject,record=self.compound()
        with self.assertRaises(WorkflowError):self.api().validate_canonical_closure(subject,record)
        subject['verification_proofs']['raw2']={**copy.deepcopy(subject['verification_proofs']['raw']),
            'id':'raw2','item_id':'W2','token':'t2'}
        subject['verifier_proofs']['p2']={**copy.deepcopy(subject['verifier_proofs']['p']),
            'item_id':'W2','token':'t2','evidence_id':'raw2'}
        subject['corrections']['second']['proof_ids']=['p2']
        disposition=subject['reviews']['branch'][0]['closure_dispositions'][1]
        disposition.update(proof_ids=['p2'],proof_applicability={'p2':['o3']})
        from workflow_lib.review_enforcement import review_bindings
        subject['review_packages']['pkg']['enforcement_bindings']=review_bindings(subject,'branch')
        closure=self.api().validate_canonical_closure(subject,record)
        self.assertEqual(set(closure['members']),{'f','second'});self.assertEqual(closure['status'],'resolved')
        with self.assertRaises(WorkflowError):self.api().validate_canonical_closure(subject,{**record,'member_closures':record['member_closures'][:1]})
    def test_phantom_diagnostic_report_cannot_resolve_new_policy_finding(self):
        from test_finding_closure import ClosureTests
        from workflow_lib.review_policy import new_review_policy
        from workflow_lib.finding_closure import validate_closure
        subject=ClosureTests().fixture();subject['review_policy']=new_review_policy()
        review=subject['reviews']['branch'][0]
        review.update(role='branch',perspective='code',verdict='block',diagnostic=True,findings=[])
        with self.assertRaises(WorkflowError):validate_closure(subject,{'finding_id':'f','review_id':'rev'})

    def test_split_preserves_every_member_and_verified_progress(self):
        subject=self.api().consolidate_findings(self.indexed(),self.request());before=self.api().finding_progress(subject)
        canonical=subject['finding_index']['aliases']['f1']['canonical_id']
        report=copy.deepcopy(subject['reviews']['branch'][0]);report.update(review_id='partition-review',actor_id='partition-actor',invocation_ref='fixture:partition')
        report['finding_partitions']=[{'id':'separate','canonical_id':canonical,'groups':[['f1'],['f2']],
            'finding_hashes':{f['id']:finding_hash(f) for f in subject['unresolved_findings']},'source_identity':'source',
            'reason':'Owned evidence now shows distinct caller failures.','evidence_refs':['fixture:distinct-callers']}]
        subject['reviews']['branch'].append(report)
        split=self.api().split_findings(subject,{'review_id':'partition-review','partition_id':'separate','canonical_id':canonical})
        self.assertNotEqual(split['finding_index']['aliases']['f1']['canonical_id'],split['finding_index']['aliases']['f2']['canonical_id'])
        self.assertEqual(split['effects'],subject['effects']);self.assertEqual(split['repair_cycles'],subject['repair_cycles'])
        self.assertEqual(self.api().finding_progress(split)['verified_progress_hash'],before['verified_progress_hash'])
        report['finding_partitions'][0]['groups']=[['f1']]
        with self.assertRaises(WorkflowError):self.api().split_findings(subject,{'review_id':'partition-review','partition_id':'separate','canonical_id':canonical})
    def test_rejection_and_minor_deferral_need_exact_independent_disposition(self):
        subject=self.indexed();report=subject['reviews']['branch'][0]
        report['finding_dispositions']=[{'id':'false-positive','finding_id':'f1','finding_hash':finding_hash(subject['unresolved_findings'][0]),
            'source_identity':'source','disposition':'rejected','reason':'Independent fixture rule disproves the report.',
            'authority_refs':['spec:spec#R1'],'evidence_refs':['fixture:approved-rule']}]
        rejected=self.api().record_disposition(subject,{'review_id':'review','disposition_id':'false-positive','finding_id':'f1'})
        self.assertEqual(rejected['unresolved_findings'][0]['status'],'rejected')
        self.assertEqual(self.api().finding_progress(rejected)['verified_obligation_count'],0)
        report['finding_dispositions'][0]['disposition']='deferred'
        with self.assertRaises(WorkflowError):self.api().record_disposition(subject,{'review_id':'review','disposition_id':'false-positive','finding_id':'f1'})
        report['finding_dispositions'][0]['disposition']='waived'
        with self.assertRaises(WorkflowError):self.api().record_disposition(subject,{'review_id':'review','disposition_id':'false-positive','finding_id':'f1'})

    def test_canonical_reducer_is_atomic_and_records_all_member_resolutions(self):
        from workflow_lib.enforcement_events import apply_enforcement
        subject,record=self.compound()
        before=copy.deepcopy(subject)
        with self.assertRaises(WorkflowError):apply_enforcement(subject,'close-canonical',record)
        self.assertEqual(subject,before)
        subject['verification_proofs']['raw2']={**copy.deepcopy(subject['verification_proofs']['raw']),'id':'raw2','item_id':'W2','token':'t2'}
        subject['verifier_proofs']['p2']={**copy.deepcopy(subject['verifier_proofs']['p']),'item_id':'W2','token':'t2','evidence_id':'raw2'}
        subject['corrections']['second']['proof_ids']=['p2']
        subject['reviews']['branch'][0]['closure_dispositions'][1].update(proof_ids=['p2'],proof_applicability={'p2':['o3']})
        from workflow_lib.review_enforcement import review_bindings
        subject['review_packages']['pkg']['enforcement_bindings']=review_bindings(subject,'branch')
        result=apply_enforcement(subject,'close-canonical',record)
        self.assertTrue(all(f['status']=='resolved' for f in result['unresolved_findings']))
        self.assertTrue(all(f.get('status','open')=='open' for f in subject['unresolved_findings']))
        self.assertEqual(result.get('effects'),subject.get('effects'))

    def test_index_cannot_weaken_original_severity_or_perspectives(self):
        for field,value in [('severity','minor'),('required_perspectives',[]),('mandatory',False)]:
            subject=self.subject();subject['unresolved_findings'][0]['mandatory']=True
            subject=self.api().index_findings(subject,[])
            subject['unresolved_findings'][0][field]=value
            with self.subTest(field=field),self.assertRaises(WorkflowError):self.api().index_findings(subject,[])

    def test_durable_grouping_retries_and_replays_both_formats(self):
        import tempfile
        from unittest.mock import patch
        from control_store_fixtures import legacy_root
        from workflow_lib import store,sqlite_store
        for initialize in (legacy_root,sqlite_store.initialize_store):
            with self.subTest(format=initialize.__name__),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'control';initialize(root)
                subject=self.indexed()
                store.transact(root,0,'fixture',{'kind':'fixture','payload':{'runs':{'r':subject}}})
                event={'kind':'domain.enforcement.consolidate-findings','payload':{'request':{'run_id':'r','record':self.request()}}}
                first=store.transact(root,1,'group',event)
                retry=store.transact(root,1,'group',event)
                self.assertTrue(retry['replayed'])
                with patch('workflow_lib.enforcement_live.source_observation',side_effect=AssertionError('replay must be pure')):
                    state=store.read_state(root)
                indexed=state['data']['runs']['r']['finding_index']
                self.assertEqual(indexed['aliases']['f1']['canonical_id'],indexed['aliases']['f2']['canonical_id'])
                self.assertEqual(len(indexed['history']),1)
                self.assertEqual(state['data']['runs']['r']['effects'],subject['effects'])
                changed=copy.deepcopy(event);changed['payload']['request']['record']['canonical_id']='unknown'
                from argparse import Namespace
                from commands.journal import commit
                parsed=Namespace(root=str(root),operation_id='group',operation_id_explicit=True,expected_version=1)
                with self.assertRaises(WorkflowError):commit(parsed,changed['kind'],changed['payload']['request'])

    def test_current_model_closure_requires_sealed_original_disposition(self):
        from test_adversarial_reviews import AdversarialReviewTests
        from workflow_lib.finding_closure import validate_closure
        from workflow_lib.review_enforcement import review_bindings
        from workflow_lib.document_units import digest
        from workflow_lib.adversarial_reviews import semantic_report_hash
        subject,package,reports=AdversarialReviewTests().fixture('branch')
        finding={'id':'doc','item_id':'W1','severity':'important','obligations':['wording'],'required_perspectives':['code']}
        subject['unresolved_findings']=[finding]
        package['enforcement_bindings']=review_bindings(subject,'branch',live=False)
        package['package_hash']=digest({k:v for k,v in package.items() if k!='package_hash'})
        subject['review_packages']={package['package_hash']:package}
        report=reports[0];report['package_hash']=package['package_hash']
        model=subject['model_receipts'][report['model_invocation_id']];model['scope']['package_hash']=package['package_hash']
        disposition={'finding_id':'doc','finding_hash':finding_hash(finding),'source_identity':'after','obligations':['wording'],
            'disposition':'resolved','proof_ids':[],'execution_inapplicable':{'reason':'Prose wording only.','evidence_refs':['package:'+package['package_hash']]}}
        report['closure_dispositions']=[disposition]
        from workflow_lib.adversarial_reviews import expected_review_input_validation
        fact=expected_review_input_validation(package);model['review_input_validation']={'before':fact,'after':fact}
        model['review_report_hash']=semantic_report_hash(report)
        subject['reviews']={'branch':[report]}
        subject['corrections']={'doc':{'source_identity':'after','finding_hash':finding_hash(finding),'proof_ids':[],'rationale':'Correct the prose.'}}
        request={'finding_id':'doc','review_id':report['review_id']}
        self.assertEqual(validate_closure(subject,request)['status'],'resolved')
        report['closure_dispositions'][0]['execution_inapplicable']['reason']='Invented controller explanation.'
        with self.assertRaises(WorkflowError):validate_closure(subject,request)
