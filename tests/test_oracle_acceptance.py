"""Fixture receipts exercise structural semantic-approval boundaries, not live host identity."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError
EMPTY='44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'

class OracleAcceptanceTests(unittest.TestCase):
    def fixture(self):
        contract={'schema_version':2,'targets':['t'],'input_hashes':{'test.py':'a'*64},'tool':['python','test.py'],
            'oracle_authority':[{'spec_hash':'spec','requirement_id':'R1'}],'spec_hash':'spec','item_id':'W1','clarification_binding':EMPTY}
        red={'id':'r','item_id':'W1','token':'attempt','phase':'RED','passed':True,'fresh':True,
             'integrity':{'phase':'RED','contract':contract,'source_identity':'before','passed':True,'exit_code':1,
                          'outcomes':{'t':'failed'},'classification':{'t':'assertion'},'stdout_ref':'raw-red','stderr_ref':'raw-red-err'}}
        green={'id':'g','item_id':'W1','token':'attempt','phase':'GREEN','passed':True,'fresh':True,'source_identity':'after',
               'integrity':{'phase':'GREEN','contract':contract,'source_identity':'after','baseline_source':'before','passed':True,
                            'exit_code':0,'outcomes':{'t':'passed'},'stdout_ref':'raw-green','stderr_ref':'raw-green-err'}}
        subject={'enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'actors':{'implementer':'author'},'source_identity':'after',
                 'plan':{'spec_hash':'spec','work_items':[{'id':'W1','kind':'code','requirement_ids':['R1'],'dependencies':[]}]},
                 'items':{'W1':{'attempts':[{'token':'attempt'}]}},'verification_proofs':{'r':red,'g':green}}
        from workflow_lib.document_units import digest
        contract['item_contract_hash']=digest(subject['plan']['work_items'][0])
        package={'source_identity':'after','package_hash':'pkg'}
        oracle={'item_id':'W1','red_proof_id':'r','green_proof_id':'g','input_hashes':{'test.py':'a'*64},'target_ids':['t'],
                'authority_refs':['spec:spec#R1'],'failure_relevance':'The captured assertion detects the approved wrong behavior.',
                'rationale':'Inspect real reports and test/source contract.','clarification_binding':EMPTY}
        review={'review_id':'review','role':'item','item_id':'W1','actor_id':'reviewer','invocation_ref':'fixture-invocation',
                'verdict':'pass','package_hash':'pkg','test_oracles':[oracle]}
        return subject,package,review
    def validate(self,*args):
        from workflow_lib.oracle_acceptance import validate_oracle_acceptance
        return validate_oracle_acceptance(*args)
    def test_raw_execution_requires_actual_independent_oracle_review(self):
        subject,package,review=self.fixture()
        accepted=self.validate(subject,package,review)
        self.assertEqual(set(accepted),{'g'})
        self.assertEqual(accepted['g']['review_id'],'review')
        review['test_oracles']=[]
        with self.assertRaises(WorkflowError):self.validate(subject,package,review)
    def test_self_review_stale_source_missing_targets_or_setup_failure_cannot_approve(self):
        for kind in ('self','source','target','setup','authority','token'):
            subject,package,review=self.fixture()
            if kind=='self':review['actor_id']='author'
            if kind=='source':package['source_identity']='old'
            if kind=='target':review['test_oracles'][0]['target_ids']=[]
            if kind=='setup':subject['verification_proofs']['r']['integrity']['classification']['t']='setup'
            if kind=='authority':review['test_oracles'][0]['authority_refs']=[]
            if kind=='token':subject['items']['W1']['attempts'][-1]['token']='new'
            with self.assertRaises(WorkflowError):self.validate(subject,package,review)
    def test_diagnostic_assessment_can_be_recorded_without_approving_tests(self):
        subject,package,review=self.fixture();review.update(verdict='request-changes',test_oracles=[])
        self.assertEqual(self.validate(subject,package,review),{})

    def test_changed_approved_item_or_specification_cannot_accept_old_oracle(self):
        for change in ('item','spec'):
            subject,package,review=self.fixture()
            if change=='item':subject['plan']['work_items'][0]['acceptance_criteria']=[{'text':'different rule'}]
            else:subject['plan']['spec_hash']='changed-spec'
            with self.subTest(change=change), self.assertRaises(WorkflowError):
                self.validate(subject,package,review)

    def test_cross_run_review_uses_sealed_original_red_with_exact_reuse_lineage(self):
        subject,package,review=self.fixture()
        red=subject['verification_proofs'].pop('r')
        green=subject['verification_proofs']['g']
        red['token']='original-attempt'
        green['red_source']={'run_id':'prior-run','proof_id':'r','token':'original-attempt','contract_hash':'original-contract'}
        green['red_baseline']=red
        self.assertEqual(set(self.validate(subject,package,review)),{'g'})
        green['red_source']['proof_id']='unrelated'
        with self.assertRaises(WorkflowError):self.validate(subject,package,review)
