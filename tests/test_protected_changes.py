import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class ProtectedTests(unittest.TestCase):
    def setup_repo(self):
        tmp=self.enterContext(tempfile.TemporaryDirectory());repo=Path(tmp)
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):
            subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'acceptance.py').write_text('assert True\n')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        subprocess.run(['git','commit','-qm','baseline'],cwd=repo,check=True)
        return repo
    def api(self):
        from workflow_lib import protected_changes
        return protected_changes
    def test_edit_delete_rename_and_index_changes_detected(self):
        for operation in ('edit','delete','rename','index'):
            repo=self.setup_repo();api=self.api();inventory={'paths':['acceptance.py'],'governing_digest':'g'}
            baseline=api.snapshot_protected(repo,inventory)
            if operation=='edit':(repo/'acceptance.py').write_text('assert False\n')
            if operation=='delete':(repo/'acceptance.py').unlink()
            if operation=='rename':(repo/'acceptance.py').rename(repo/'renamed.py')
            if operation=='index':
                (repo/'acceptance.py').write_text('changed\n');subprocess.run(['git','add','.'],cwd=repo,check=True)
                (repo/'acceptance.py').write_text('assert True\n')
            observed=api.observe_protected_changes(repo,inventory,baseline)
            self.assertEqual(observed['changed_paths'],['acceptance.py'])
            with self.assertRaises(WorkflowError):api.validate_protected_changes(observed,[],[])
    def test_inventory_cannot_remove_its_own_protection(self):
        repo=self.setup_repo();api=self.api();baseline=api.snapshot_protected(repo,{'paths':['acceptance.py']})
        observation=api.observe_protected_changes(repo,{'paths':[]},baseline)
        with self.assertRaises(WorkflowError):api.validate_protected_changes(observation,[],[])
    def test_exact_approval_and_independent_review_required(self):
        repo=self.setup_repo();api=self.api();inv={'paths':['acceptance.py']};baseline=api.snapshot_protected(repo,inv)
        (repo/'acceptance.py').write_text('changed')
        observation=api.observe_protected_changes(repo,inv,baseline)
        approval={'approved':True,'observation_hash':observation['observation_hash'],'actor_id':'fixture-user','reason':'fixture change'}
        with self.assertRaises(WorkflowError):api.validate_protected_changes(observation,[approval],[])
        review={'observation_hash':observation['observation_hash'],'actor_id':'reviewer','implementer_actor':'author',
                'invocation_ref':'fixture-invocation','verdict':'pass'}
        self.assertTrue(api.validate_protected_changes(observation,[approval],[review])['passed'])
        (repo/'acceptance.py').write_text('different')
        with self.assertRaises(WorkflowError):api.validate_protected_changes(api.observe_protected_changes(repo,inv,baseline),[approval],[review])
    def test_inventory_requires_governing_approval_and_cannot_reset_baseline(self):
        from workflow_lib.enforcement_events import apply_enforcement
        repo=self.setup_repo();inv={'paths':['acceptance.py'],'governing_digest':'g'}
        record={'repo_id':'r','inventory':inv,'baseline':self.api().snapshot_protected(repo,inv)}
        subject={'id':'run','enforcement':{'policy_version':1},'governing_digest':'g','repositories':{'r':{'location':str(repo)}}}
        with self.assertRaises(WorkflowError):apply_enforcement(subject,'protect-inventory',record)
        record['authorization']={'approved':True,'actor_id':'fixture-user','inventory_hash':record['baseline']['inventory_hash'],'governing_digest':'g','reason':'declared acceptance contract'}
        updated=apply_enforcement(subject,'protect-inventory',record)
        self.assertEqual(updated['protected_inventories']['r']['inventory'],inv)
        record['inventory']={'paths':[],'governing_digest':'g'}
        with self.assertRaises(WorkflowError):apply_enforcement(updated,'protect-inventory',record)
