import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import test_evidence as evidence_fixtures
from workflow_lib.store import read_state, transact, WorkflowError
from workflow_lib.evidence import capture_evidence


class RedReuseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=evidence_fixtures.EvidenceTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root=self.fixture.root;self.repo=self.fixture.repo
        self.runner=self.repo/'test_target.py'
        self.runner.write_text("import json,sys\nfrom pathlib import Path\nok=Path('implementation').read_text()=='fixed'\nprint(json.dumps({'tests':[{'id':'target','outcome':'passed' if ok else 'failed'}]}))\nsys.exit(0 if ok else 1)\n",encoding='utf-8')
        (self.repo/'implementation').write_text('broken',encoding='utf-8')
        state=read_state(self.root);run=state['data']['runs']['run-1']
        run['plan']['spec_hash']='a'*64;run['governing_digest']='b'*64
        transact(self.root,state['version'],'contract-seed',{'kind':'fixture','payload':state['data']})
        self.argv=[sys.executable,'test_target.py']
    def capture(self,phase='RED',**kw):
        return capture_evidence(self.root,kw.pop('run_id','run-1'),kw.pop('token','attempt-1'),phase,self.argv,
            ['test_target.py'],kw.pop('targets',['target']),10,**kw)
    def next_attempt(self,new_run=False):
        state=read_state(self.root);data=state['data'];run=copy.deepcopy(data['runs']['run-1'])
        run['active_attempt']['token']='attempt-2'
        if new_run:
            run['id']='run-2';run['verification_proofs']={};run['verifier_proofs']={}
            data['runs']['run-2']=run
        else:data['runs']['run-1']=run
        transact(self.root,state['version'],'next-'+str(new_run),{'kind':'fixture','payload':data})
        (self.repo/'implementation').write_text('fixed',encoding='utf-8')
    def test_recorded_red_supports_fresh_green_under_new_token(self):
        red=self.capture();self.next_attempt()
        green=self.capture('GREEN',token='attempt-2',red_proof_id=red['id'])
        self.assertTrue(green['passed']);self.assertEqual(green['token'],'attempt-2')
        self.assertEqual(green['red_source']['proof_id'],red['id'])
        stored=read_state(self.root)['data']['runs']['run-1']['verification_proofs']
        self.assertEqual(stored[red['id']],red)
    def test_cross_run_requires_explicit_identical_contract(self):
        red=self.capture();self.next_attempt(new_run=True)
        green=self.capture('GREEN',run_id='run-2',token='attempt-2',red_run_id='run-1',red_proof_id=red['id'])
        self.assertTrue(green['passed']);self.assertEqual(green['red_source']['run_id'],'run-1')
    def test_mismatched_contract_rejects_before_execution(self):
        red=self.capture();self.next_attempt()
        for change in ('test','target','argv','format','item','spec','plan','governing','repo'):
            from workflow_lib.red_reuse import verification_contract,select_red_source
            data=read_state(self.root)['data'];run=data['runs']['run-1'];item=run['plan']['work_items'][0]
            contract=verification_contract(run,item,'repo-1',red['test_hashes'],['target'],self.argv,'json')
            changed=copy.deepcopy(contract)
            key={'test':'test_hashes','target':'target_ids','argv':'argv','format':'report_format','item':'item_hash',
                 'spec':'spec_hash','plan':'plan_hash','governing':'governing_digest','repo':'repo_id'}[change]
            changed[key]='changed'
            with self.subTest(change=change),self.assertRaises(WorkflowError):
                select_red_source(data,'run-1','W1',changed,red['id'])
        with patch('workflow_lib.evidence.subprocess.run',side_effect=AssertionError('invalid reuse must not execute')):
            with self.assertRaises(WorkflowError):self.capture('GREEN',token='attempt-2',targets=['missing'],red_proof_id=red['id'])
    def test_legacy_failed_missing_or_incomplete_red_is_not_reusable(self):
        from workflow_lib.red_reuse import verification_contract,select_red_source
        red=self.capture();data=read_state(self.root)['data'];run=data['runs']['run-1'];item=run['plan']['work_items'][0]
        contract=verification_contract(run,item,'repo-1',red['test_hashes'],['target'],self.argv,'json')
        original=copy.deepcopy(data)
        self.assertEqual(select_red_source(data,'run-1','W1',contract,red['id'])['token'],'attempt-1')
        self.assertEqual(data,original)
        for change in ({'passed':False},{'verification_contract':None},{'target_outcomes':{}},{'exit_code':0},{'phase':'GREEN'}):
            data=copy.deepcopy(original);data['runs']['run-1']['verification_proofs'][red['id']].update(change)
            with self.subTest(change=change),self.assertRaises(WorkflowError):
                select_red_source(data,'run-1','W1',contract,red['id'])
        with self.assertRaises(WorkflowError):select_red_source(original,'run-1','W1',contract,'missing')
    def test_replay_validates_red_lineage_without_running_tests(self):
        red=self.capture();self.next_attempt();green=self.capture('GREEN',token='attempt-2',red_proof_id=red['id'])
        (self.root/'state.json').unlink()
        with patch('subprocess.run',side_effect=AssertionError('journal replay is pure')):
            self.assertEqual(read_state(self.root)['data']['runs']['run-1']['verification_proofs'][green['id']]['red_source']['proof_id'],red['id'])
