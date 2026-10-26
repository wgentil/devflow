import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import test_red_reuse as red_fixtures
from workflow_lib.store import read_state,transact,WorkflowError
from workflow_lib.runs import record_result
from workflow_lib.gates import _required_proof
ENTRY=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'


class ReverificationTests(unittest.TestCase):
    def setUp(self):
        self.f=red_fixtures.RedReuseTests();self.f.setUp(legacy=self._testMethodName == "test_exact_replay_and_rebuild_do_not_issue_second_token");self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.repo=self.f.repo
        state=read_state(self.root);run=state['data']['runs']['run-1']
        from test_hosts import host_state
        governing=host_state()
        state['data']['spec']=governing['spec'];state['data']['approval']=governing['approval']
        run['plan']['spec_hash']=governing['approval']['content_hash']
        run.update(status='active',repositories=copy.deepcopy(state['data']['repositories']),unavailable_gates=[])
        run['items']['W1'].update(status='pending',attempts=[copy.deepcopy(run['active_attempt'])])
        run['plan']['work_items'][0].update(dependencies=[],requirement_ids=['R1'],acceptance_criteria=[{'kind':'code-test','text':'target'}])
        transact(self.root,state['version'],'full-run',{'kind':'fixture','payload':state['data']})
        self.red=self.f.capture()
        (self.repo/'implementation').write_text('fixed',encoding='utf-8')
        self.green=self.f.capture('GREEN')
        state=read_state(self.root);updated=record_result(state['data']['runs']['run-1'],'attempt-1',{'outcome':'passed','verifier_proof_id':self.green['id']})
        state['data']['runs']['run-1']=updated
        transact(self.root,state['version'],'completed-fixture',{'kind':'fixture','payload':state['data']})
    def cli(self,*args):
        out=subprocess.run([sys.executable,str(ENTRY),'run','reverify','--root',str(self.root),'--run-id','run-1','--item','W1',*args],capture_output=True,text=True)
        return out,json.loads(out.stdout) if out.stdout.strip() else {}
    def test_new_commit_then_reverify_keeps_red_and_requires_fresh_green(self):
        subprocess.run(['git','add','.'],cwd=self.repo,check=True)
        subprocess.run(['git','commit','-qm','W2 unrelated commit'],cwd=self.repo,check=True)
        run=read_state(self.root)['data']['runs']['run-1'];item=run['plan']['work_items'][0]
        self.assertIsNone(_required_proof(run,item))
        from workflow_lib.gates import gate_status
        self.assertEqual(gate_status(run)['reverification_actions'][0]['command'],'run reverify')
        out,result=self.cli('--operation-id','reverify-1');self.assertEqual(out.returncode,0,out.stdout+out.stderr)
        token=result['attempt_id'];self.assertNotEqual(token,'attempt-1')
        run=read_state(self.root)['data']['runs']['run-1'];self.assertEqual(run['items']['W1']['status'],'pending')
        self.assertEqual(len(run['items']['W1']['attempts']),2)
        with self.assertRaises(WorkflowError):record_result(run,token,{'outcome':'passed','verifier_proof_id':self.green['id']})
        fresh=self.f.capture('GREEN',token=token,red_proof_id=self.red['id'])
        run=read_state(self.root)['data']['runs']['run-1']
        updated=record_result(run,token,{'outcome':'passed','verifier_proof_id':fresh['id']})
        self.assertEqual(updated['items']['W1']['status'],'complete');self.assertIsNotNone(_required_proof(updated,item))
    def test_exact_replay_and_rebuild_do_not_issue_second_token(self):
        out,first=self.cli('--operation-id','same');self.assertEqual(out.returncode,0,out.stdout)
        (self.root/'state.json').unlink()
        out,again=self.cli('--operation-id','same');self.assertEqual(out.returncode,0,out.stdout)
        self.assertEqual(again['active_attempt']['token'],first['attempt_id'])
        self.assertEqual(len(read_state(self.root)['data']['runs']['run-1']['items']['W1']['attempts']),2)
    def test_ineligible_reverification_is_pure_and_actionable(self):
        from workflow_lib.reverification import begin_reverification
        original=read_state(self.root)['data']['runs']['run-1']
        for change in ('active','worker','repair','delivered','noncode','dependencies'):
            run=copy.deepcopy(original)
            if change=='active':run['active_attempt']={'token':'other'}
            elif change=='worker':run['native_invocations']={'worker':{'status':'running'}}
            elif change=='repair':run['repair_cycles']=[{'status':'claimed'}]
            elif change=='delivered':run['status']='delivered'
            elif change=='noncode':run['plan']['work_items'][0]['kind']='iac'
            else:run['plan']['work_items'][0]['dependencies']=['missing']
            before=copy.deepcopy(run)
            with self.subTest(change=change),self.assertRaises(WorkflowError):begin_reverification(run,'W1')
            self.assertEqual(run,before)
    def test_replay_cannot_change_requested_item(self):
        out,_=self.cli('--operation-id','scope');self.assertEqual(out.returncode,0,out.stdout)
        out=subprocess.run([sys.executable,str(ENTRY),'run','reverify','--root',str(self.root),'--run-id','run-1','--item','W2','--operation-id','scope'],capture_output=True,text=True)
        self.assertNotEqual(out.returncode,0);self.assertIn('OPERATION_CONFLICT',out.stdout)

    def test_reverification_renews_affected_review_and_acceptance_evidence(self):
        state=read_state(self.root);run=state['data']['runs']['run-1']
        run['reviews']={'item':[{'item_id':'W1','verdict':'pass'}], 'branch':[{'verdict':'pass'}], 'acceptance':[{'verdict':'pass'}]}
        run['acceptances']=[{'complete':True}]
        transact(self.root,state['version'],'reviewed-fixture',{'kind':'fixture','payload':state['data']})
        out,_=self.cli('--operation-id','renew-reviewed');self.assertEqual(out.returncode,0,out.stdout)
        run=read_state(self.root)['data']['runs']['run-1']
        self.assertFalse(run['reviews']['item'][0].get('fresh',True))
        self.assertFalse(run['reviews']['branch'][0].get('fresh',True))
        self.assertFalse(run['acceptances'][0].get('fresh',True))
