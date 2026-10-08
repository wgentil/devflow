import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.store import read_state, transact, WorkflowError
from workflow_lib.document_approvals import propose_document_change, approve_document_change, require_current_governing_inputs

class DocumentApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'repo'; self.repo.mkdir()
        self.root = Path(self.tmp.name) / 'state'
        self.git('init', '-q'); self.write('rules.md', '## A: Rule\noriginal\n')
        self.write('docs/devflow-context.json', json.dumps({'schema_version':1, 'documents':[{'category':'coding-standards','path':'rules.md','rule_ids':['A']}]}))
        self.commit()
        transact(self.root, 0, 'register', {'kind':'test.setup','payload':{'repositories':{'p':{'location':str(self.repo)}}, 'spec_pair':{'repo_id':'p'}}})
    def git(self, *args):
        return subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True,text=True)
    def commit(self):
        self.git('add','.'); self.git('-c','user.name=Test','-c','user.email=t@example.com','commit','-qm','baseline')
    def write(self, path, value):
        target=self.repo/path; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(value)
    def gate(self): return require_current_governing_inputs(self.root, read_state(self.root), 'build')
    def test_historical_and_unrelated_files_do_not_block(self):
        before=self.gate(); self.write('irrelevant.md','unrelated')
        self.assertEqual(before['effective_digest'],self.gate()['effective_digest'])
    def test_changed_files_require_separate_exact_approval(self):
        self.write('rules.md','## A: Rule\nchanged\n')
        with self.assertRaises(WorkflowError): self.gate()
        proposal=propose_document_change(self.root,'p',['rules.md'])
        approve_document_change(self.root,proposal['proposal_hash'],'human')
        self.gate()
        self.write('rules.md','## A: Rule\nchanged again\n')
        with self.assertRaises(WorkflowError): self.gate()
    def test_commit_does_not_approve_drift(self):
        self.gate(); self.write('rules.md','## A: Rule\nchanged\n'); self.commit()
        with self.assertRaises(WorkflowError): self.gate()
    def test_stale_proposal_and_empty_actor_rejected(self):
        self.write('rules.md','## A: Rule\nchanged\n')
        p=propose_document_change(self.root,'p',['rules.md'])
        with self.assertRaises(WorkflowError): approve_document_change(self.root,p['proposal_hash'],'')
        self.write('rules.md','## A: Rule\nother\n')
        with self.assertRaises(WorkflowError): approve_document_change(self.root,p['proposal_hash'],'human')
    def test_replay_is_pure(self):
        self.gate(); state=read_state(self.root); self.write('rules.md','broken')
        self.assertEqual(state,read_state(self.root))

    def test_explicit_irrelevance_does_not_drift_block(self):
        manifest=json.loads((self.repo/'docs/devflow-context.json').read_text())
        manifest['irrelevance_decisions']=[{'rule_id':'A','reason':'feature does not change code'}]
        self.write('docs/devflow-context.json',json.dumps(manifest)); self.commit()
        before=self.gate(); self.write('rules.md','## A: Rule\nchanged\n')
        self.assertEqual(before['effective_digest'],self.gate()['effective_digest'])

    def test_spec_approval_cannot_approve_policy_edits(self):
        self.write('rules.md','## A: Rule\nchanged\n')
        state=read_state(self.root)
        transact(self.root,state['version'],'spec-evidence',{'kind':'test.setup','payload':{'approval':{'confirmed':True,'actor_id':'human'}}})
        with self.assertRaises(WorkflowError): self.gate()

    def test_approval_is_scoped_to_owning_repository(self):
        self.write('rules.md','## A: Rule\nchanged\n')
        state=read_state(self.root)
        transact(self.root,state['version'],'second-repo',{'kind':'test.setup','payload':{'repositories':{'p':{'location':str(self.repo)},'other':{'location':str(self.repo)}}}})
        proposal=propose_document_change(self.root,'other',['rules.md'])
        approve_document_change(self.root,proposal['proposal_hash'],'human')
        with self.assertRaises(WorkflowError): self.gate()

    def test_committed_drift_proposal_preserves_accepted_before_image(self):
        self.gate()
        self.write('rules.md', '## A: Rule\ncommitted change\n'); self.commit()
        with self.assertRaises(WorkflowError): self.gate()
        proposal = propose_document_change(self.root, 'p', ['rules.md'])
        self.assertIn('-original\n', proposal['files']['rules.md']['diff'])
        self.assertIn('+committed change\n', proposal['files']['rules.md']['diff'])
        approve_document_change(self.root, proposal['proposal_hash'], 'human')
        self.gate()

    def test_old_after_image_approval_cannot_authorize_restoration(self):
        self.gate()
        for content in ('B', 'C'):
            self.write('rules.md', '## A: Rule\n' + content + '\n')
            proposal = propose_document_change(self.root, 'p', ['rules.md'])
            approve_document_change(self.root, proposal['proposal_hash'], 'human')
            self.gate(); self.commit(); self.gate()
        self.write('rules.md', '## A: Rule\nB\n')
        with self.assertRaises(WorkflowError): self.gate()
        proposal = propose_document_change(self.root, 'p', ['rules.md'])
        self.assertIn('-C\n', proposal['files']['rules.md']['diff'])
        approve_document_change(self.root, proposal['proposal_hash'], 'human')
        self.gate()
