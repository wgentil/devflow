import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from large_context_fixtures import make_context_project
from workflow_lib import context_preparation as preparation
from workflow_lib.ground_interview import TOPICS
from workflow_lib.lifecycle_hooks import prepared_context
from workflow_lib.repo_input_gate import preflight_inputs
from workflow_lib.runs import issue_attempt
from workflow_lib.store import read_state,transact,WorkflowError

class ContextInputContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.f=make_context_project(self.base/'project');self.root=self.f['root'];self.repo=self.f['repo']
    def proposal(self):
        state=read_state(self.root);run=issue_attempt(state['data']['runs']['current'],'W1')
        p=preparation.prepare_context(self.root,run,{'run_id':'current'},['W1'],stage='implementation',state=state)
        return p,run
    def assert_capture_rejected(self,mutation):
        original=preparation.preflight_inputs
        def changed(*args,**kwargs):
            result=original(*args,**kwargs);mutation();return result
        with patch.object(preparation,'preflight_inputs',side_effect=changed):
            with self.assertRaises(WorkflowError) as caught:self.proposal()
        self.assertEqual(caught.exception.code,'CONTEXT_SOURCE_CHANGED')
        self.assertIsNone(read_state(self.root)['data']['runs']['current']['active_attempt'])
    def governed(self,org=False):
        document={'category':'coding-standards','path':'rules.md','rule_ids':['G1']}
        manifest={'schema_version':1,'documents':[document],'ground_interview':{'path':'docs/devflow-ground-interview.json'}}
        owner=self.repo
        if org:
            owner=self.base/'org';(owner/'docs').mkdir(parents=True)
            subprocess.run(['git','init','-q',str(owner)],check=True,capture_output=True)
            (owner/'docs/devflow-org.json').write_text(json.dumps({'schema_version':1,'id':'org','documents':[document]},indent=2), newline='\n', encoding='utf-8')
            manifest['documents']=[];manifest['org']={'id':'org','url':str(owner)}
            state=read_state(self.root);repositories=copy.deepcopy(state['data']['repositories']);repositories['org']={'location':str(owner)}
            transact(self.root,state['version'],'register-org',{'kind':'fixture','payload':{'repositories':repositories}})
        (owner/'rules.md').write_text('## G1: Safety\nPreserve required checks.\n', newline='\n', encoding='utf-8')
        (self.repo/'docs/devflow-context.json').write_text(json.dumps(manifest,indent=2), newline='\n', encoding='utf-8')
        self.interview={'schema_version':1,'topics':{name:{'status':'answered','material':True,'decision':'Offline decision.'} for name in TOPICS}}
        (self.repo/'docs/devflow-ground-interview.json').write_text(json.dumps(self.interview,indent=2), newline='\n', encoding='utf-8')
        for repo in {owner,self.repo}:
            subprocess.run(['git','-C',str(repo),'add','.'],check=True,capture_output=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=offline@example.test','commit','-qm','Governing fixture'],check=True,capture_output=True)
        state=preflight_inputs(self.root,read_state(self.root),'plan-validation')['state'];data=state['data'];digest=data['governing_input_receipt']['effective_digest']
        runs=copy.deepcopy(data['runs']);runs['current']['governing_digest']=digest
        validation={**data['plan_validation'],'governing_digest':digest}
        transact(self.root,state['version'],'reassessed-fixture',{'kind':'fixture','payload':{'runs':runs,'plan_validation':validation,'governing_reassessment_required':False}})
        return owner
    def test_absent_project_manifest_created_after_preflight_is_rejected(self):
        self.assert_capture_rejected(lambda:(self.repo/'docs/devflow-context.json').write_text('{"schema_version":1,"documents":[]}', newline='\n', encoding='utf-8'))
    def test_project_manifest_change_after_preflight_is_rejected(self):
        self.governed();path=self.repo/'docs/devflow-context.json'
        self.assert_capture_rejected(lambda:path.write_text('{"schema_version":1,"documents":[]}', newline='\n', encoding='utf-8'))
    def test_ground_interview_change_after_preflight_is_rejected(self):
        self.governed();self.interview['topics']['architecture']={'status':'deferred','material':True,'reason':'Unresolved change.'}
        self.assert_capture_rejected(lambda:(self.repo/'docs/devflow-ground-interview.json').write_text(json.dumps(self.interview,indent=2), newline='\n', encoding='utf-8'))
    def test_org_manifest_change_after_worker_blocks_token_without_consuming_key(self):
        owner=self.governed(org=True);p,run=self.proposal()
        prepared_context(self.root,run,{'run_id':'current'},['W1'],stage='implementation',prepared=p)
        (owner/'docs/devflow-org.json').write_text('invalid unapproved manifest', newline='\n', encoding='utf-8')
        with self.assertRaises(WorkflowError):
            preparation.commit_prepared_attempt(self.root,p,'org-guard',{'kind':'run.attempt.issued','payload':{'run_id':'current','attempt':run['active_attempt']}})
        state=read_state(self.root);self.assertNotIn('org-guard',state['operations']);self.assertIsNone(state['data']['runs']['current']['active_attempt'])
    def test_org_manifest_change_after_preflight_is_rejected(self):
        owner=self.governed(org=True)
        self.assert_capture_rejected(lambda:(owner/'docs/devflow-org.json').write_text('invalid unapproved manifest', newline='\n', encoding='utf-8'))

    def test_org_manifest_removed_after_preflight_is_rejected(self):
        owner=self.governed(org=True)
        self.assert_capture_rejected(lambda:(owner/'docs/devflow-org.json').unlink())
    def test_windows_checkout_conversion_matches_validated_receipt(self):
        from workflow_lib.governing_docs import canonical_document_bytes
        owner=self.governed(org=True)
        paths=[self.repo/'docs/devflow-context.json',self.repo/'docs/devflow-ground-interview.json',owner/'docs/devflow-org.json',owner/'rules.md']
        for path in paths:path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
        def windows(raw,**kw):return canonical_document_bytes(raw,windows=True,**kw)
        with patch('workflow_lib.governing_docs.canonical_document_bytes',side_effect=windows),patch('workflow_lib.document_approvals.canonical_document_bytes',side_effect=windows):
            p,run=self.proposal()
        self.assertIn(str(owner/'docs/devflow-org.json'),p.source_bindings['files'])
        preparation.assert_preparation_current(self.root,p,p._state)

    def test_missing_repository_retains_live_preflight_error(self):
        state=read_state(self.root)
        transact(self.root,state['version'],'unregistered-fixture',{'kind':'fixture','payload':{'repositories':{}}})
        with self.assertRaises(WorkflowError) as caught:self.proposal()
        self.assertEqual(caught.exception.code,'REPO_NOT_FOUND')
