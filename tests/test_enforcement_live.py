import sys
import unittest
import tempfile
import subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class LiveChecks(unittest.TestCase):
    def test_source_observation_detects_changed_bytes(self):
        from workflow_lib.enforcement_live import source_observation, assert_source_current
        repo=Path(self.enterContext(tempfile.TemporaryDirectory()))
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'a').write_text('before');subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','baseline'],cwd=repo,check=True)
        subject={'enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'repositories':{'r':{'location':str(repo)}}}
        observation=source_observation(subject);subject['source_identity']=observation['source_identity']
        assert_source_current(subject)
        (repo/'a').write_text('after')
        with self.assertRaises(WorkflowError):assert_source_current(subject)
    def test_enforced_legacy_finding_resolution_cannot_bypass_review(self):
        from workflow_lib.gates import resolve_finding
        run={'enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'unresolved_findings':[{'id':'f'}]}
        with self.assertRaises(WorkflowError):resolve_finding(run,'f','implementer','fixed',['arbitrary'])
    def test_protection_rechecks_current_bytes_without_reverting_edits(self):
        from workflow_lib.enforcement_live import assert_protection_current
        from workflow_lib.protected_changes import snapshot_protected
        repo=Path(self.enterContext(tempfile.TemporaryDirectory()))
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        target=repo/'acceptance.py';target.write_text('before')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','base'],cwd=repo,check=True)
        inventory={'paths':['acceptance.py']}
        subject={'enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'repositories':{'r':{'location':str(repo)}},
            'protected_inventories':{'r':{'inventory':inventory,'baseline':snapshot_protected(repo,inventory)}}}
        from unittest.mock import patch
        subject['reviews']={'branch':[{'actor_id':'fixture-reviewer','invocation_ref':'fixture-call',
            'verdict':'pass','package_hash':'irrelevant'} for _ in range(100)]}
        subject['review_packages']={'irrelevant':{'package_hash':'irrelevant'}}
        with patch('workflow_lib.host_completion.package_current', side_effect=AssertionError('Unrelated review history must not be loaded.')) as check:
            assert_protection_current(subject)
            check.assert_not_called()
        target.write_text('after')
        with self.assertRaises(WorkflowError):assert_protection_current(subject)
        self.assertEqual(target.read_text(),'after')
    def test_ignored_declared_input_change_invalidates_runtime_proof(self):
        import hashlib
        from workflow_lib.evidence import repository_fingerprint
        from workflow_lib.gates import _required_proof
        repo=Path(self.enterContext(tempfile.TemporaryDirectory()))
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'source.py').write_text('value=1')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','base'],cwd=repo,check=True)
        (repo/'.git/info/exclude').write_text('ignored.fixture\n')
        target=repo/'ignored.fixture';target.write_text('before')
        fingerprint=repository_fingerprint(repo);sha=hashlib.sha256(b'before').hexdigest()
        evidence={'id':'p','item_id':'W1','kind':'code','phase':'GREEN','repo_id':'r','fresh':True,
                  'repository_head':fingerprint['head'],'worktree_digest':fingerprint['worktree_digest'],
                  'integrity':{'contract':{'input_hashes':{'ignored.fixture':sha},'input_bindings':{
                    'ignored.fixture':{'type':'file','resolved_path':'ignored.fixture','sha256':sha,'executable':False}}}}}
        run={'enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'repositories':{'r':{'location':str(repo)}},
             'items':{'W1':{'attempts':[{'token':'t'}]}},'verification_proofs':{'p':evidence},
             'verifier_proofs':{'p':{'passed':True,'item_id':'W1','token':'t','evidence_id':'p'}}}
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.enforcement_live import assert_protection_current
        inventory={'paths':[]}
        run['protected_inventories']={'r':{'inventory':inventory,'baseline':snapshot_protected(repo,inventory)}}
        evidence['protection_receipts']=assert_protection_current(run)
        item={'id':'W1','kind':'code'}
        self.assertIsNotNone(_required_proof(run,item))
        target.write_text('after')
        self.assertEqual(repository_fingerprint(repo),fingerprint)
        self.assertIsNone(_required_proof(run,item))
        from workflow_lib.runs import record_result
        run.update(state_version=1,plan={'work_items':[item]},
            active_attempt={'token':'t','item_id':'W1','state_version':1})
        run['items']['W1']['attempts']=[dict(run['active_attempt'])]
        with self.assertRaises(WorkflowError):
            record_result(run,'t',{'outcome':'passed','verifier_proof_id':'p'})
