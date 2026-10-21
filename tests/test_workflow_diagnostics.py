import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_red_reuse as red_fixtures
import test_item_review_recovery as review_fixtures
from workflow_lib.store import read_state,transact
from workflow_lib.reviews import record_review
ENTRY=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'


class WorkflowDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.f=red_fixtures.RedReuseTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root
        state=read_state(self.root);run=state['data']['runs']['run-1']
        run.update(status='active',unavailable_gates=[])
        run['items']['W1'].update(status='pending',attempts=[copy.deepcopy(run['active_attempt'])])
        transact(self.root,state['version'],'full',{'kind':'fixture','payload':state['data']})
    def test_passing_result_without_proof_preserves_token_and_names_required_fields(self):
        for outcome in ('success','passed','completed','succeeded'):
            before=read_state(self.root)
            result=subprocess.run([sys.executable,str(ENTRY),'run','result','--root',str(self.root),'--run-id','run-1',
                '--attempt-id','attempt-1','--result',json.dumps({'outcome':outcome})],capture_output=True,text=True)
            with self.subTest(outcome=outcome):
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertIn('verifier_proof_id',result.stdout);self.assertIn('passed',result.stdout)
                self.assertEqual(read_state(self.root),before)
    def test_failed_and_blocked_results_are_recordable_without_proof(self):
        from workflow_lib.runs import record_result
        run=read_state(self.root)['data']['runs']['run-1']
        for outcome in ('failed','blocked'):
            updated=record_result(run,'attempt-1',{'outcome':outcome})
            self.assertIsNone(updated['active_attempt']);self.assertEqual(updated['items']['W1']['status'],'pending')
    def test_build_response_alias_matches_stored_id_without_changing_stored_shape(self):
        result=subprocess.run([sys.executable,str(ENTRY),'build','verify','--root',str(self.root),'--run-id','run-1',
            '--attempt-id','attempt-1','--phase','red','--argv-json',json.dumps(self.f.argv),
            '--test-path','test_target.py','--target-id','target'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        value=json.loads(result.stdout);self.assertTrue(value['passed']);self.assertEqual(value['proof_id'],value['id'])
        self.assertNotIn('proof_id',read_state(self.root)['data']['runs']['run-1']['verification_proofs'][value['id']])
    def test_review_severity_error_lists_allowed_values(self):
        f=review_fixtures.ItemReviewRecoveryTests();f.setUp();self.addCleanup(f.doCleanups)
        pkg=f.package();report=f.report(pkg);report['findings'][0]['severity']='low'
        with self.assertRaises(ValueError) as error:record_review(f.run,pkg['package_hash'],f.reviewer,report)
        for severity in ('critical','important','minor','info'):self.assertIn(severity,str(error.exception))
    def test_reviewer_role_identity_conflict_is_distinct_from_self_review(self):
        f=review_fixtures.ItemReviewRecoveryTests();f.setUp();self.addCleanup(f.doCleanups)
        pkg=f.package();f.run['actors']['item_reviewer']='established';f.seed()
        report={**f.report(pkg),'verdict':'pass','findings':[]}
        for actor,expected in (('different','REVIEWER_ROLE_IDENTITY_CONFLICT'),('impl','distinct from implementer')):
            before=read_state(f.root)
            result=subprocess.run([sys.executable,str(ENTRY),'review','record','--root',str(f.root),'--run-id','run-1',
                '--package-hash',pkg['package_hash'],'--actor-id',actor,'--invocation-ref','independent://new',
                '--tool-available','--report-json',json.dumps(report)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn(expected,result.stdout)
            self.assertEqual(read_state(f.root),before)
