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
        subject={'enforcement':{'policy_version':1},'repositories':{'r':{'location':str(repo)}}}
        observation=source_observation(subject);subject['source_identity']=observation['source_identity']
        assert_source_current(subject)
        (repo/'a').write_text('after')
        with self.assertRaises(WorkflowError):assert_source_current(subject)
    def test_enforced_legacy_finding_resolution_cannot_bypass_review(self):
        from workflow_lib.gates import resolve_finding
        run={'enforcement':{'policy_version':1},'unresolved_findings':[{'id':'f'}]}
        with self.assertRaises(WorkflowError):resolve_finding(run,'f','implementer','fixed',['arbitrary'])
    def test_protection_rechecks_current_bytes_without_reverting_edits(self):
        from workflow_lib.enforcement_live import assert_protection_current
        from workflow_lib.protected_changes import snapshot_protected
        repo=Path(self.enterContext(tempfile.TemporaryDirectory()))
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        target=repo/'acceptance.py';target.write_text('before')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','base'],cwd=repo,check=True)
        inventory={'paths':['acceptance.py']}
        subject={'enforcement':{'policy_version':1},'repositories':{'r':{'location':str(repo)}},
            'protected_inventories':{'r':{'inventory':inventory,'baseline':snapshot_protected(repo,inventory)}}}
        assert_protection_current(subject)
        target.write_text('after')
        with self.assertRaises(WorkflowError):assert_protection_current(subject)
        self.assertEqual(target.read_text(),'after')
