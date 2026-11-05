import sys
import json
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class IntegrityTests(unittest.TestCase):
    def api(self):
        from workflow_lib import test_integrity
        return test_integrity
    def test_generic_failure_does_not_prove_assertion_relevance(self):
        parsed=self.api().parse_test_evidence(json.dumps({'tests':[{'id':'t','outcome':'failed'}]}),'','json')
        self.assertEqual(parsed['classification']['t'],'unknown')
    def test_setup_errors_and_skips_are_not_assertions(self):
        for outcome in ('error','skipped','passed'):
            parsed=self.api().parse_test_evidence(json.dumps({'tests':[{'id':'t','outcome':outcome}]}),'','json')
            self.assertNotEqual(parsed['classification']['t'],'assertion')
    def pair(self):
        contract={'schema_version':2,'targets':['t'],'input_hashes':{'test.py':'a','fixture':'b'},'tool':'python','oracle_review':'review'}
        red={'phase':'RED','contract':contract,'source_identity':'before','passed':True,'exit_code':1,
             'outcomes':{'t':'failed'},'classification':{'t':'assertion'},'stdout_ref':'raw1','stderr_ref':'raw2'}
        green={'phase':'GREEN','contract':contract,'source_identity':'after','baseline_source':'before','passed':True,'exit_code':0,
             'outcomes':{'t':'passed'},'stdout_ref':'raw3','stderr_ref':'raw4'}
        return red,green,contract
    def test_linked_pair_accepts_different_source_snapshots(self):
        red,green,contract=self.pair()
        self.assertTrue(self.api().validate_test_pair(red,green,contract)['passed'])
    def test_missing_setup_changed_inputs_or_unlinked_source_blocks(self):
        for mutation in ('missing','setup','fixture','source','oracle'):
            red,green,contract=self.pair()
            if mutation=='missing':green['outcomes']={}
            if mutation=='setup':red['classification']['t']='setup'
            if mutation=='fixture':green['contract']={**contract,'input_hashes':{'fixture':'changed'}}
            if mutation=='source':green['baseline_source']='wrong'
            if mutation=='oracle':contract.pop('oracle_review')
            with self.assertRaises(WorkflowError):self.api().validate_test_pair(red,green,contract)
    def test_assertion_red_then_corrected_green_links_sources(self):
        import tempfile,subprocess,hashlib
        repo=Path(self.enterContext(tempfile.TemporaryDirectory()))
        source=repo/'behavior.py';source.write_text('def retention(): return 60\n')
        script="""import json
from behavior import retention
outcome='passed';phase=None
try: assert retention() == 30, 'approved fixture rule: thirty days'
except AssertionError: outcome='failed';phase='test-assertion'
print(json.dumps({'schema':'devflow-test-report-v2','tests':[{'id':'retention','outcome':outcome,'failure_phase':phase}]}))
raise SystemExit(0 if outcome=='passed' else 1)
"""
        test=repo/'check.py';test.write_text(script)
        baseline=hashlib.sha256(source.read_bytes()).hexdigest()
        red_run=subprocess.run([sys.executable,str(test)],cwd=repo,capture_output=True,text=True)
        self.assertEqual(red_run.returncode,1)
        red_parsed=self.api().parse_test_evidence(red_run.stdout,red_run.stderr,'json')
        self.assertEqual(red_parsed['classification']['retention'],'assertion')
        source.write_text('def retention(): return 30\n')
        # Avoid Python bytecode cache masking same-size changes in this fixture.
        import shutil
        shutil.rmtree(repo/'__pycache__',ignore_errors=True)
        green_run=subprocess.run([sys.executable,str(test)],cwd=repo,capture_output=True,text=True)
        self.assertEqual(green_run.returncode,0)
        contract={'schema_version':2,'targets':['retention'],'input_hashes':{'check.py':hashlib.sha256(test.read_bytes()).hexdigest()},
                  'tool':sys.executable,'oracle_review':'fixture-independent-contract-review'}
        red={**red_parsed,'phase':'RED','contract':contract,'source_identity':baseline,'passed':True,'exit_code':red_run.returncode,'stdout_ref':'fixture-retained-red','stderr_ref':'fixture-empty-stderr'}
        green={**self.api().parse_test_evidence(green_run.stdout,green_run.stderr,'json'),'phase':'GREEN','contract':contract,
               'source_identity':hashlib.sha256(source.read_bytes()).hexdigest(),'baseline_source':baseline,'passed':True,
               'exit_code':green_run.returncode,'stdout_ref':'fixture-retained-green','stderr_ref':'fixture-empty-stderr'}
        self.assertTrue(self.api().validate_test_pair(red,green,contract)['passed'])
