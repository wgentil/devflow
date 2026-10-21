import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_project_setup as setup_fixtures
from workflow_lib.project_setup import initialize_project_documents
from workflow_lib.document_approvals import approve_document_change,require_current_governing_inputs
from workflow_lib.store import read_state,transact,WorkflowError


class SetupApprovalProposalTests(unittest.TestCase):
    def setUp(self):
        self.f=setup_fixtures.ProjectSetupTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.repo=self.f.repo
        subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.test','commit','--allow-empty','-qm','base'],cwd=self.repo,check=True)
        self.root=self.repo/'.devflow/control'
    def test_setup_returns_exact_proposal_and_does_not_approve_it(self):
        result=initialize_project_documents(self.repo,{'mode':'project-only'},'setup')
        self.assertEqual(result['approval_status'],'required');self.assertTrue(result['approval_required'])
        proposal=result['approval_proposal'];self.assertEqual(len(proposal['proposal_hash']),64)
        self.assertIn('docs/devflow-context.json',proposal['files']);self.assertIn('docs/devflow-context.json',result['review_diff'])
        record=proposal['files']['docs/devflow-context.json'];self.assertEqual(len(record['after_hash']),64)
        state=read_state(self.root);self.assertFalse(state['data'].get('document_approvals'))
        state['data']['spec_pair']={'repo_id':result['repo_id']}
        transact(self.root,state['version'],'spec-pair-fixture',{'kind':'fixture','payload':state['data']})
        with self.assertRaises(WorkflowError) as error:require_current_governing_inputs(self.root,read_state(self.root),'plan-validation')
        self.assertEqual(error.exception.code,'DOCUMENT_APPROVAL_REQUIRED')
        approve_document_change(self.root,proposal['proposal_hash'],'human')
        require_current_governing_inputs(self.root,read_state(self.root),'plan-validation')
    def test_repeat_preserves_approval_and_changed_content_requires_new_proposal(self):
        first=initialize_project_documents(self.repo,{'mode':'project-only'},'setup')
        approve_document_change(self.root,first['approval_proposal']['proposal_hash'],'human')
        second=initialize_project_documents(self.repo,{'mode':'project-only'},'repeat')
        self.assertEqual(second['approval_status'],'approved');self.assertFalse(second['approval_required'])
        self.assertEqual(second['approval_proposal']['proposal_hash'],first['approval_proposal']['proposal_hash'])
        path=self.repo/'docs/devflow-context.json';manifest=json.loads(path.read_text(encoding='utf-8'))
        manifest['irrelevance_decisions']=[];path.write_text(json.dumps(manifest),encoding='utf-8')
        third=initialize_project_documents(self.repo,{'mode':'project-only'},'changed')
        self.assertEqual(third['approval_status'],'required');self.assertNotEqual(third['approval_proposal']['proposal_hash'],first['approval_proposal']['proposal_hash'])
    def test_proposal_failure_after_creation_is_visible_and_recoverable(self):
        with patch('workflow_lib.document_approvals.propose_document_change',side_effect=WorkflowError('DOCUMENT_PROPOSAL_UNAVAILABLE','fixture read failure')):
            first=initialize_project_documents(self.repo,{'mode':'project-only'},'setup')
        self.assertTrue((self.repo/'docs/devflow-context.json').exists())
        self.assertTrue(first['approval_required']);self.assertEqual(first['approval_status'],'pending')
        self.assertIsNone(first['approval_proposal']);self.assertIn('next_action',first)
        second=initialize_project_documents(self.repo,{'mode':'project-only'},'recover')
        self.assertTrue(second['unchanged']);self.assertEqual(second['approval_status'],'required')
    def test_ambiguous_existing_control_does_not_claim_approval_ready(self):
        transact(self.root,0,'other',{'kind':'fixture','payload':{'repositories':{'old-repo':{'location':str(self.repo/'old-location')}}}})
        result=initialize_project_documents(self.repo,{'mode':'project-only'},'setup')
        self.assertEqual(result['approval_status'],'pending');self.assertEqual(result['approval_reason_code'],'PROJECT_RELOCATION_REQUIRED')
        self.assertTrue(result['approval_required']);self.assertIsNone(result['approval_proposal'])
    def test_external_control_root_is_used_by_cli(self):
        root=(Path(self.f.temp.name)/'external control').resolve()
        choice=Path(self.f.temp.name)/'choice.json';choice.write_text('{"mode":"project-only"}',encoding='utf-8')
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        result=subprocess.run([sys.executable,str(entry),'setup','initialize','--project-dir',str(self.repo),'--root',str(root),
            '--choice',str(choice),'--operation-id','setup'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        value=json.loads(result.stdout);self.assertEqual(Path(value['control_root']),root)
        self.assertIn(value['approval_proposal']['proposal_hash'],read_state(root)['data']['document_proposals'])
        self.assertFalse((self.repo/'.devflow/control').exists())
    def test_organization_checkout_is_registered_and_keeps_inherited_source(self):
        org=(Path(self.f.temp.name)/'organization').resolve()
        result=initialize_project_documents(self.repo,{'mode':'create-org','name':'Team','target_dir':str(org)},'setup')
        self.assertEqual(result['approval_status'],'required')
        state=read_state(self.root);self.assertTrue(any(Path(row['location'])==Path(result['org_checkout']) for row in state['data']['repositories'].values()))
        self.assertEqual(result['manifest']['org']['url'],str(org))
        self.assertIn(result['manifest']['org']['id'],state['data']['repositories'])
        self.assertEqual(result['additional_approval_proposals'][0]['repo_id'],result['manifest']['org']['id'])
