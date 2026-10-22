"""Input checks must preserve authority without replaying unchanged history."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from large_context_fixtures import make_context_project
from workflow_lib.store import read_state,transact,WorkflowError
from workflow_lib import repo_input_gate as gates
from workflow_lib.ground_interview import TOPICS

class ContextPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.f=make_context_project(Path(self.temp.name)/'project');self.root=self.f['root'];self.repo=self.f['repo']
    def governed(self):
        (self.repo/'rules.md').write_text('## A: Safety\nKeep checks.\n',encoding='utf-8')
        (self.repo/'docs/devflow-context.json').write_text(json.dumps({'schema_version':1,'documents':[{'category':'coding-standards','path':'rules.md','rule_ids':['A']}]}),encoding='utf-8')
        (self.repo/'docs/devflow-ground-interview.json').write_text(json.dumps({'schema_version':1,'topics':{name:{'status':'answered','material':True,'decision':'Offline fixture decision.'} for name in TOPICS}}),encoding='utf-8')
        subprocess.run(['git','-C',str(self.repo),'add','.'],check=True,capture_output=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','Fixture governing inputs'],check=True,capture_output=True)
    def preflight(self,state=None,phase='build',run_id='current'):
        return gates.preflight_inputs(self.root,state or read_state(self.root),phase,run_id)
    def test_unchanged_inputs_reuse_one_authoritative_state(self):
        state=read_state(self.root)
        with patch('workflow_lib.repo_input_gate.read_state',side_effect=AssertionError('duplicate replay')),patch('workflow_lib.document_approvals.read_state',side_effect=AssertionError('duplicate replay')):
            result=self.preflight(state)
        self.assertEqual(result['state']['version'],state['version']);self.assertEqual(result['inputs']['spec']['content_hash'],state['data']['spec_pair']['content_hash'])
    def test_receipt_write_returns_updated_state(self):
        self.governed();before=read_state(self.root)
        with patch('workflow_lib.document_approvals.read_state',side_effect=AssertionError('must use transaction state')):
            result=self.preflight(before,'plan-validation',None)
        self.assertGreater(result['state']['version'],before['version'])
        self.assertEqual(result['state']['data']['governing_input_receipt'],result['inputs']['governing'])
        self.assertEqual(result['state'],read_state(self.root))
    def test_concurrent_receipt_write_returns_stale(self):
        self.governed();original=transact;advanced=False
        def race(root,version,op,event):
            nonlocal advanced
            if not advanced:
                advanced=True;original(root,version,'other-writer',{'kind':'fixture','payload':{'other_writer':True}})
            return original(root,version,op,event)
        with patch('workflow_lib.document_approvals.transact',side_effect=race):
            with self.assertRaises(WorkflowError) as caught:self.preflight(phase='plan-validation',run_id=None)
        self.assertEqual(caught.exception.code,'CONTEXT_PREPARATION_STALE')
        self.assertNotIn('governing_input_receipt',read_state(self.root)['data'])
    def test_spec_drift_remains_durably_invalidated(self):
        path=self.repo/self.f['state']['data']['spec_pair']['markdown_path'];original=path.read_bytes();path.write_text('unapproved',encoding='utf-8')
        with self.assertRaises(WorkflowError):self.preflight()
        path.write_bytes(original)
        with self.assertRaises(WorkflowError) as caught:self.preflight()
        self.assertEqual(caught.exception.code,'SPEC_APPROVAL_STALE')
        self.assertTrue(read_state(self.root)['data']['spec_approval_invalidated'])
    def test_governing_reassessment_still_blocks(self):
        self.governed()
        with self.assertRaises(WorkflowError) as caught:self.preflight()
        self.assertEqual(caught.exception.code,'GOVERNING_REASSESSMENT_REQUIRED')
        self.assertTrue(read_state(self.root)['data']['governing_reassessment_required'])
