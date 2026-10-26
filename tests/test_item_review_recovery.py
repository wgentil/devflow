import copy
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
import test_reviews as review_fixtures
from workflow_lib.reviews import prepare_review,record_review
from workflow_lib.runs import issue_attempt,record_result
from workflow_lib.store import transact,read_state,WorkflowError
ENTRY=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'


class ItemReviewRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=review_fixtures.ReviewTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.run=copy.deepcopy(self.f.run);self.run.update(status='active',state_version=0,active_attempt=None,unavailable_gates=[],review_ids=[])
        self.run['plan']['work_items'][0].update(repo_id='repo-1',dependencies=[])
        self.run['items']['W1'].update(status='complete',attempts=[{'token':'t1','status':'verified'}])
        self.run['items']['W2']={'status':'complete','attempts':[{'token':'t2','status':'verified'}]}
        self.run['plan']['work_items'].append({'id':'W2','kind':'code','repo_id':'repo-1','requirement_ids':['R2'],'dependencies':[],'acceptance_criteria':[]})
        self.run['reviews']={'branch':[{'verdict':'pass'}],'acceptance':[{'verdict':'pass'}]}
        self.run['acceptances']=[{'complete':True}]
        self.repos={'repo-1':{'location':str(self.f.repo),'base':self.f.base,'head':self.f.head}}
        self.reviewer={'role':'item','actor_id':'item-reviewer','invocation_ref':'independent://1','tool_available':True}
        self.root=Path(self.f.temp.name)/'control'
    def package(self,legacy=False):
        pkg=prepare_review(self.run,'item',self.repos,**({} if legacy else {'item_id':'W1'}))
        self.run.setdefault('review_packages',{})[pkg['package_hash']]=pkg
        return pkg
    def report(self,pkg):
        return {'package_hash':pkg['package_hash'],'verdict':'request-changes','item_id':'W1',
            'findings':[{'id':'F1','severity':'important','path':'src/app.py','line':1}]}
    def seed(self):transact(self.root,0,'seed',{'kind':'fixture','payload':{'runs':{'run-1':self.run}}})
    def test_request_changes_reopens_only_reviewed_item_and_retains_history(self):
        pkg=self.package();record=record_review(self.run,pkg['package_hash'],self.reviewer,self.report(pkg))
        self.seed();before=copy.deepcopy(self.run['items']['W2'])
        transact(self.root,1,'request-changes',{'kind':'review.recorded','payload':{'run_id':'run-1','review':record}})
        saved=read_state(self.root)['data']['runs']['run-1']
        self.assertEqual(saved['items']['W1']['status'],'pending');self.assertEqual(saved['items']['W2'],before)
        self.assertEqual(saved['reviews']['item'][0]['findings'][0]['id'],'F1')
        self.assertFalse(saved['reviews']['branch'][0].get('fresh',True));self.assertFalse(saved['acceptances'][0].get('fresh',True))
        retried=issue_attempt(saved,'W1');self.assertNotEqual(retried['active_attempt']['token'],'t1')
        with self.assertRaises(WorkflowError):record_result(retried,'t1',{'outcome':'passed'})
    def test_invalid_item_actor_finding_or_limit_leaves_run_unchanged(self):
        pkg=self.package();original=copy.deepcopy(self.run)
        for change in ('item','actor','finding','limit'):
            run=copy.deepcopy(original);reviewer=copy.deepcopy(self.reviewer);report=self.report(pkg)
            if change=='item':report['item_id']='W2'
            elif change=='actor':reviewer['actor_id']='impl'
            elif change=='finding':report['findings']=[]
            else:run['reviews']['item']=[{'verdict':'request-changes','item_id':'W1'} for _ in range(4)]
            before=copy.deepcopy(run)
            with self.subTest(change=change),self.assertRaises(ValueError):record_review(run,pkg['package_hash'],reviewer,report)
            self.assertEqual(run,before)
    def test_failed_journal_independence_cannot_reopen_item(self):
        pkg=self.package();record=record_review(self.run,pkg['package_hash'],self.reviewer,self.report(pkg))
        self.run['actors']['item_reviewer']='established';self.seed();before=read_state(self.root)
        with self.assertRaises(WorkflowError):
            transact(self.root,1,'bad-actor',{'kind':'review.recorded','payload':{'run_id':'run-1','review':record}})
        self.assertEqual(read_state(self.root),before)
    def test_old_record_replays_without_new_reopening_semantics(self):
        from control_store_fixtures import legacy_root
        legacy_root(self.root)
        pkg=self.package(legacy=True);record=record_review(self.run,pkg['package_hash'],self.reviewer,self.report(pkg))
        self.seed();transact(self.root,1,'legacy',{'kind':'review.recorded','payload':{'run_id':'run-1','review':record}})
        (self.root/'state.json').unlink()
        saved=read_state(self.root)['data']['runs']['run-1'];self.assertEqual(saved['items']['W1']['status'],'complete')
    def test_record_command_names_retry_and_replay_does_not_reopen_again(self):
        pkg=self.package();self.seed()
        argv=[sys.executable,str(ENTRY),'review','record','--root',str(self.root),'--run-id','run-1',
            '--package-hash',pkg['package_hash'],'--actor-id','item-reviewer','--invocation-ref','independent://1',
            '--tool-available','--report-json',json.dumps(self.report(pkg)),'--operation-id','record']
        first=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(first.returncode,0,first.stdout+first.stderr)
        value=json.loads(first.stdout);self.assertEqual(value['item_status'],'pending');self.assertEqual(value['next_action']['command'],'run retry')
        version=read_state(self.root)['version']
        again=subprocess.run(argv,capture_output=True,text=True);self.assertEqual(again.returncode,0,again.stdout)
        self.assertEqual(read_state(self.root)['version'],version)
