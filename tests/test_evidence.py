import json
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/workflow/scripts"))
from workflow_lib.store import read_state, transact

ENTRY = Path(__file__).resolve().parents[1] / "skills/workflow/scripts/run.py"


class EvidenceTests(unittest.TestCase):
    def setUp(self, *, legacy=False):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "control"
        if legacy:
            from control_store_fixtures import legacy_root
            legacy_root(self.root)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "devflow@example.test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Devflow Test"], cwd=self.repo, check=True)
        (self.repo / "test_target.py").write_text("# locked test\n")
        subprocess.run(["git", "add", "test_target.py"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=self.repo, check=True)
        transact(self.root, 0, "fixture", {"kind": "fixture", "payload": {
            "repositories": {"repo-1": {"location": str(self.repo)}},
            "runs": {"run-1": {"id": "run-1", "state_version": 1,
                "plan": {"work_items": [{"id": "W1", "kind": "code", "repo_id": "repo-1"}]},
                "items": {"W1": {"attempts": []}}, "active_attempt": {
                    "token": "attempt-1", "item_id": "W1", "state_version": 1},
                "verification_proofs": {}}},
        }})

    def tearDown(self):
        self.temp.cleanup()

    def command(self, report, exit_code=0):
        encoded = json.dumps(report)
        return [sys.executable, "-c", f"import sys; print({encoded!r}); sys.exit({exit_code})"]

    def capture(self, *args):
        spec = importlib.util.find_spec("workflow_lib.evidence")
        self.assertIsNotNone(spec, "capture_evidence must be implemented")
        from workflow_lib.evidence import capture_evidence
        return capture_evidence(*args)

    def test_enforced_capture_requires_independent_integrity_contract(self):
        from workflow_lib.store import read_state, WorkflowError
        state=read_state(self.root);run=state['data']['runs']['run-1']
        run['enforcement']={'protocol':'devflow.python-enforcement/v1', 'policy_version':1}
        transact(self.root,state['version'],'enforce',{'kind':'fixture','payload':{'runs':{'run-1':run}}})
        with self.assertRaises(WorkflowError):
            self.capture(self.root,'run-1','attempt-1','RED',
                self.command({'tests':[{'id':'test_target','outcome':'failed'}]},1),
                ['test_target.py'],['test_target'],10)

    def test_enforced_reducer_rejects_legacy_proof_injection(self):
        from workflow_lib.store import read_state, WorkflowError
        proof=self.capture(self.root,'run-1','attempt-1','RED',
            self.command({'tests':[{'id':'test_target','outcome':'failed'}]},1),['test_target.py'],['test_target'],10)
        state=read_state(self.root);run=state['data']['runs']['run-1'];run['enforcement']={'protocol':'devflow.python-enforcement/v1', 'policy_version':1}
        transact(self.root,state['version'],'enforce',{'kind':'fixture','payload':{'runs':{'run-1':run}}})
        proof={**proof,'id':'forged-new-proof'}
        with self.assertRaises(WorkflowError):
            transact(self.root,read_state(self.root)['version'],'inject',{'kind':'verification.recorded','payload':{'run_id':'run-1','proof':proof}})

    def test_enforced_real_red_green_uses_reviewed_oracle_and_real_sources(self):
        import hashlib
        from workflow_lib.store import read_state
        script = """import json
from pathlib import Path
outcome='passed';phase=None
try: assert Path('value.txt').read_text() == '30'
except AssertionError: outcome='failed';phase='test-assertion'
print(json.dumps({'schema':'devflow-test-report-v2','tests':[{'id':'test_target','outcome':outcome,'failure_phase':phase}]}))
raise SystemExit(0 if outcome=='passed' else 1)
"""
        (self.repo/'test_target.py').write_text(script)
        (self.repo/'value.txt').write_text('60')
        (self.repo/'.git/info/exclude').write_text('scanner.conf\n')
        (self.repo/'scanner.conf').write_text('strict scanner')
        subprocess.run(['git','add','.'],cwd=self.repo,check=True)
        subprocess.run(['git','commit','-qm','approved fixture oracle'],cwd=self.repo,check=True)
        state=read_state(self.root);run=state['data']['runs']['run-1']
        run['enforcement']={'protocol':'devflow.python-enforcement/v1', 'policy_version':1};run['actors']={'implementer':'fixture-author'};run['status']='active'
        run['repositories']=state['data']['repositories']
        from workflow_lib.protected_changes import snapshot_protected
        inventory={'paths':['test_target.py','scanner.conf'],'governing_digest':'fixture-governing'}
        run['governing_digest']='fixture-governing'
        run['protected_inventories']={'repo-1':{'inventory':inventory,'baseline':snapshot_protected(self.repo,inventory)}}
        run['items']['W1']['attempts']=[dict(run['active_attempt'])]
        run['unresolved_findings']=[{'id':'retention-defect','item_id':'W1','mandatory':True,
            'status':'open','obligations':['retention-rule']}]
        run['plan']['spec_hash']='fixture-approved-spec'
        run['plan']['work_items'][0].update(verification_inputs=['test_target.py'],verification_target_ids=['test_target'],requirement_ids=['R1'])
        transact(self.root,state['version'],'enforce',{'kind':'fixture','payload':{'runs':{'run-1':run}}})
        argv=[sys.executable,'test_target.py']
        from unittest.mock import patch
        real_run=subprocess.run;executions=[]
        def concurrent_metadata(command,*args,**kwargs):
            result=real_run(command,*args,**kwargs)
            if command==argv:
                executions.append(command)
                current=read_state(self.root)
                transact(self.root,current['version'],'unrelated-metadata',{'kind':'fixture','payload':{'unrelated_note':'independent'}})
            return result
        with patch('workflow_lib.evidence.subprocess.run',side_effect=concurrent_metadata):
            red=self.capture(self.root,'run-1','attempt-1','RED',argv,['test_target.py'],['test_target'],10)
        self.assertEqual(len(executions),1,'A metadata race must not rerun the test process.')
        (self.repo/'value.txt').write_text('30')
        subprocess.run(['git','commit','-qam','fix retention\n\nWork-Item: W1'],cwd=self.repo,check=True)
        green=self.capture(self.root,'run-1','attempt-1','GREEN',argv,['test_target.py'],['test_target'],10)
        self.assertNotEqual(red['source_identity'],green['source_identity'])
        self.assertEqual(green['integrity']['baseline_source'],red['source_identity'])
        self.assertTrue((self.root/green['stdout_ref']).is_file())
        self.assertEqual(green['integrity']['semantic_status'],'pending-review')
        self.assertEqual(set(green['protection_receipts']),{'repo-1'})
        self.assertTrue(green.get('execution_id'))
        from workflow_lib.gates import _required_proof
        current_run=read_state(self.root)['data']['runs']['run-1']
        self.assertIsNotNone(_required_proof(current_run,current_run['plan']['work_items'][0]))
        from workflow_lib.runs import record_result
        from workflow_lib.reviews import prepare_review,record_review
        from workflow_lib.store import WorkflowError
        state=read_state(self.root);run=state['data']['runs']['run-1']
        result={'outcome':'passed','verifier_proof_id':green['id']}
        record_result(run,'attempt-1',result)
        transact(self.root,state['version'],'runtime-result',{'kind':'run.result.recorded','payload':{
            'run_id':'run-1','token':'attempt-1','result':result,'verified':True,'verifier_proof_id':green['id']}})
        state=read_state(self.root);run=state['data']['runs']['run-1']
        package=prepare_review(run,'item',{'repo-1':{'location':str(self.repo),'base':red['repository_head'],'head':green['repository_head']}},item_id='W1')
        transact(self.root,state['version'],'oracle-package',{'kind':'review.package.prepared','payload':{'run_id':'run-1','package':package}})
        state=read_state(self.root);run=state['data']['runs']['run-1']
        reviewer={'role':'item','actor_id':'fixture-independent-reviewer','invocation_ref':'fixture-real-review-call','tool_available':True}
        report={'package_hash':package['package_hash'],'verdict':'pass','item_id':'W1','findings':[]}
        with self.assertRaises(WorkflowError):record_review(run,package['package_hash'],reviewer,report)
        contract=green['integrity']['contract']
        report['test_oracles']=[{'item_id':'W1','red_proof_id':red['id'],'green_proof_id':green['id'],
            'input_hashes':contract['input_hashes'],'target_ids':['test_target'],
            'authority_refs':['spec:fixture-approved-spec#R1'],'clarification_binding':contract['clarification_binding'],
            'failure_relevance':'Actual sixty-day value fails the independently specified thirty-day assertion.',
            'rationale':'Fixture reviewer inspects the unchanged assertion and actual retained RED/GREEN reports.'}]
        review=record_review(run,package['package_hash'],reviewer,report)
        transact(self.root,state['version'],'oracle-review',{'kind':'review.recorded','payload':{'run_id':'run-1','review':review}})
        verified=read_state(self.root)['data']['runs']['run-1']['verifier_proofs'][green['id']]
        self.assertEqual(verified['semantic_status'],'reviewed')
        self.assertEqual(verified['semantic_review_id'],review['review_id'])
        from workflow_lib.gates import gate_status
        import copy
        accepted_run=read_state(self.root)['data']['runs']['run-1']
        self.assertEqual(gate_status(accepted_run)['stage'],'branch-review')
        unbound=copy.deepcopy(accepted_run)
        unbound['reviews']['item'][0]['semantic_approvals']={}
        self.assertEqual(gate_status(unbound)['stage'],'item-review')
        # Actual execution and distinct recorded fixture reviewers reach final gates.
        repo_inputs={'repo-1':{'location':str(self.repo),'base':red['repository_head'],'head':green['repository_head']}}
        state=read_state(self.root)
        transact(self.root,state['version'],'candidate-fix',{'kind':'domain.enforcement.propose-fix',
            'payload':{'request':{'run_id':'run-1','record':{'finding_id':'retention-defect',
                'source_identity':green['source_identity'],'proof_ids':[green['id']],
                'rationale':'The actual sixty-day failure now passes with the thirty-day correction.'}}}})

        for role in ('branch','acceptance'):
            state=read_state(self.root);run=state['data']['runs']['run-1']
            package=prepare_review(run,role,repo_inputs)
            transact(self.root,state['version'],role+'-package',{'kind':'review.package.prepared',
                'payload':{'run_id':'run-1','package':package}})
            state=read_state(self.root);run=state['data']['runs']['run-1']
            assessment={'package_hash':package['package_hash'],'verdict':'pass','findings':[]}
            if role=='branch':
                assessment['test_oracles']=report['test_oracles']
                from workflow_lib.finding_closure import finding_hash
                assessment['closure_dispositions']=[{'finding_id':'retention-defect','finding_hash':finding_hash(run['unresolved_findings'][0]),
                    'source_identity':green['source_identity'],'obligations':['retention-rule'],
                    'disposition':'resolved','proof_ids':[green['id']],
                    'proof_applicability':{green['id']:['retention-rule']}}]
            reviewer={'role':role,'actor_id':'fixture-'+role+'-reviewer',
                'invocation_ref':'fixture-'+role+'-invocation','tool_available':True}
            review=record_review(run,package['package_hash'],reviewer,assessment)
            transact(self.root,state['version'],role+'-review',{'kind':'review.recorded',
                'payload':{'run_id':'run-1','review':review}})
            if role=='branch':
                request_path=self.root.parent/'closure-request.json'
                request_path.write_text(json.dumps({'run_id':'run-1','record':{
                    'finding_id':'retention-defect','review_id':review['review_id']}}))
                command=[sys.executable,str(ENTRY),'enforcement','close-finding','--root',str(self.root),
                    '--input',str(request_path),'--operation-id','independent-closure']
                (self.repo/'scanner.conf').write_text('unapproved scanner weakening')
                blocked=subprocess.run(command,capture_output=True,text=True)
                self.assertNotEqual(blocked.returncode,0,blocked.stdout)
                self.assertIn('PROTECTED_CHANGE_BLOCKED',blocked.stdout+blocked.stderr)
                (self.repo/'scanner.conf').write_text('strict scanner')
                allowed=subprocess.run(command,capture_output=True,text=True)
                self.assertEqual(allowed.returncode,0,allowed.stdout+allowed.stderr)
                self.assertEqual(read_state(self.root)['data']['runs']['run-1']['unresolved_findings'][0]['status'],'resolved')
        from workflow_lib.gates import accept_requirements
        state=read_state(self.root);run=state['data']['runs']['run-1']
        (self.repo/'scanner.conf').write_text('unapproved acceptance scanner')
        with self.assertRaises((ValueError,WorkflowError)):
            accept_requirements(run,{'package_hash':package['package_hash'],
                'requirements':[{'id':'R1','verdict':'MET','citations':[{
                    'repo_id':'repo-1','path':'value.txt','line':1}]}]},
                {'repo-1':{'location':str(self.repo),'head':green['repository_head']}})
        (self.repo/'scanner.conf').write_text('strict scanner')
        acceptance=accept_requirements(run,{'package_hash':package['package_hash'],
            'requirements':[{'id':'R1','verdict':'MET','citations':[{
                'repo_id':'repo-1','path':'value.txt','line':1}]}]},
            {'repo-1':{'location':str(self.repo),'head':green['repository_head']}})
        self.assertEqual(acceptance['schema_version'],2)
        self.assertEqual(acceptance['protection_receipts'],green['protection_receipts'])
        transact(self.root,state['version'],'final-acceptance',{'kind':'acceptance.recorded',
            'payload':{'run_id':'run-1','acceptance':acceptance}})
        ready=read_state(self.root)['data']['runs']['run-1']
        self.assertTrue(gate_status(ready)['can_advance'])
        from workflow_lib.delivery import prepare_delivery,verify_delivery,record_delivery
        manifest=prepare_delivery(ready,repo_inputs,'retained-branch')
        checked=verify_delivery(ready,manifest,manifest['manifest_hash'],repo_inputs)

        ready['effects']={'late':{'status':'uncertain','action_scope':{'item_id':'W1'}}}
        self.assertFalse(gate_status(ready)['can_advance'])
        with self.assertRaises((ValueError,WorkflowError)):
            verify_delivery(ready,manifest,manifest['manifest_hash'],repo_inputs)
        with self.assertRaises((ValueError,WorkflowError)):
            record_delivery(ready,checked,{'outcome':'retained-branch','repository_heads':{'repo-1':green['repository_head']},
                'authorization':{'approved':True,'actor_id':'fixture-user','manifest_hash':manifest['manifest_hash'],
                    'action':'delivery.retained-branch'}})
        ready['effects']={}
        from workflow_lib.evidence import repository_fingerprint
        before=repository_fingerprint(self.repo)
        (self.repo/'scanner.conf').write_text('weakened ignored scanner')
        self.assertEqual(repository_fingerprint(self.repo),before)
        self.assertFalse(gate_status(ready)['can_advance'])
        with self.assertRaises((ValueError,WorkflowError)):
            verify_delivery(ready,manifest,manifest['manifest_hash'],repo_inputs)






    def test_actual_target_red_green(self):
        red = self.capture(self.root, "run-1", "attempt-1", "RED",
                           self.command({"tests": [{"id": "test_target", "outcome": "failed"}]}, 1),
                           ["test_target.py"], ["test_target"], 10)
        evidence = self.capture(self.root, "run-1", "attempt-1", "GREEN",
                                self.command({"tests": [{"id": "test_target", "outcome": "passed"}]}),
                                ["test_target.py"], ["test_target"], 10)

        self.assertTrue(red["passed"])
        self.assertEqual(red["target_outcomes"], {"test_target": "failed"})
        self.assertEqual(evidence["exit_code"], 0)
        self.assertEqual(evidence["target_outcomes"], {"test_target": "passed"})
        self.assertEqual(evidence["repo_id"], "repo-1")
        self.assertEqual(len(evidence["test_hashes"]["test_target.py"]), 64)
        self.assertTrue((self.root / evidence["stdout_ref"]).is_file())

    def test_unrelated_failure_and_timeout(self):
        evidence = self.capture(self.root, "run-1", "attempt-1", "RED",
                                    self.command({"tests": [{"id": "other", "outcome": "failed"}]}, 1),
                                    ["test_target.py"], ["test_target"], 10)

        self.assertEqual(evidence["passed"], False)
        self.assertEqual(evidence["target_outcomes"], {})
        self.assertEqual(read_state(self.root)["version"], 1)
        self.assertFalse(read_state(self.root)["data"]["runs"]["run-1"]["verification_proofs"])

    def test_timeout_and_repo_escape_produce_stable_unpassed_results(self):
        timeout = self.capture(self.root, "run-1", "attempt-1", "GREEN",
                                   [sys.executable, "-c", "import time; time.sleep(2)"],
                                   ["test_target.py"], ["test_target"], 1)
        escaped = self.capture(self.root, "run-1", "attempt-1", "GREEN",
                                   self.command({"tests": [{"id": "test_target", "outcome": "passed"}]}),
                                   ["../outside.py"], ["test_target"], 10)

        self.assertEqual(timeout["passed"], False)
        self.assertEqual(timeout["failure"], "TIMEOUT")
        self.assertEqual(escaped["passed"], False)
        self.assertEqual(escaped["failure"], "TEST_PATH_OUTSIDE_REPOSITORY")

    def test_green_rejects_changed_locked_tests_after_red(self):
        failed = self.command({"tests": [{"id": "test_target", "outcome": "failed"}]}, 1)
        passing = self.command({"tests": [{"id": "test_target", "outcome": "passed"}]})
        self.capture(self.root, "run-1", "attempt-1", "RED", failed, ["test_target.py"], ["test_target"], 10)
        (self.repo / "test_target.py").write_text("# changed locked test\n")

        green = self.capture(self.root, "run-1", "attempt-1", "GREEN", passing,
                             ["test_target.py"], ["test_target"], 10)

        self.assertFalse(green["passed"])
        self.assertEqual(green["failure"], "LOCKED_TESTS_CHANGED")

    def test_build_command_records_proof_and_rejects_stale_tokens(self):
        report = json.dumps({"tests": [{"id": "test_target", "outcome": "failed"}]})
        command = [sys.executable, "-c", f"import sys; print({report!r}); sys.exit(1)"]
        result = subprocess.run([sys.executable, str(ENTRY), "build", "verify", "--root", str(self.root),
            "--run-id", "run-1", "--attempt-id", "attempt-1", "--phase", "red",
            "--argv-json", json.dumps(command), "--test-path", "test_target.py", "--target-id", "test_target"],
            capture_output=True, text=True)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])
        proof_map = read_state(self.root)["data"]["runs"]["run-1"]["verification_proofs"]
        self.assertEqual(len(proof_map), 1)

    def test_junit_xml_report_proves_declared_target(self):
        red_xml = "<testsuite failures='1'><testcase classname='tests.test_x' name='target'><failure/></testcase></testsuite>"
        green_xml = "<testsuite><testcase classname='tests.test_x' name='target'/></testsuite>"
        red_command = [sys.executable, "-c", f"import sys; print({red_xml!r}); sys.exit(1)"]
        green_command = [sys.executable, "-c", f"print({green_xml!r})"]
        self.capture(self.root, "run-1", "attempt-1", "RED", red_command,
                     ["test_target.py"], ["tests.test_x.target"], 10)
        result = self.capture(self.root, "run-1", "attempt-1", "GREEN", green_command,
                              ["test_target.py"], ["tests.test_x.target"], 10)

        self.assertTrue(result["passed"])
        self.assertEqual(result["target_outcomes"], {"tests.test_x.target": "passed"})

    def test_unittest_verbose_adapter_parses_failures_from_stderr(self):
        from workflow_lib.evidence import _report
        self.assertEqual(_report("", "test_target (tests.test_x.Target) ... FAIL\n", "unittest"),
                         {"tests.test_x.Target.test_target": "failed"})

    def test_repository_mutation_during_test_command_cannot_produce_green(self):
        self.capture(self.root, "run-1", "attempt-1", "RED",
                     self.command({"tests": [{"id": "test_target", "outcome": "failed"}]}, 1),
                     ["test_target.py"], ["test_target"], 10)
        mutating = [sys.executable, "-c", "import pathlib,json; pathlib.Path('source.py').write_text('changed'); print(json.dumps({'tests':[{'id':'test_target','outcome':'passed'}]}))"]
        result = self.capture(self.root, "run-1", "attempt-1", "GREEN", mutating,
                              ["test_target.py"], ["test_target"], 10)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failure"], "REPOSITORY_CHANGED_DURING_VERIFICATION")


if __name__ == "__main__":
    unittest.main()
