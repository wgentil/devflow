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
    def test_literal_path_with_brackets_detects_index_only_change(self):
        repo=self.setup_repo();api=self.api();name='acceptance[1].py'
        (repo/name).write_text('original')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        subprocess.run(['git','commit','-qm','literal baseline'],cwd=repo,check=True)
        inventory={'paths':[name]};baseline=api.snapshot_protected(repo,inventory)
        (repo/name).write_text('staged replacement')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        (repo/name).write_text('original')
        self.assertEqual(api.observe_protected_changes(repo,inventory,baseline)['changed_paths'],[name])

    def test_directory_inventory_requires_explicit_file_scope(self):
        repo=self.setup_repo();(repo/'contracts').mkdir()
        with self.assertRaises(WorkflowError):
            self.api().snapshot_protected(repo,{'paths':['contracts']})

    def test_snapshot_retains_reviewable_preimages_from_all_three_layers(self):
        import base64
        repo=self.setup_repo();api=self.api()
        (repo/'acceptance.py').write_text('staged bytes')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        (repo/'acceptance.py').write_text('working bytes')
        entry=api.snapshot_protected(repo,{'paths':['acceptance.py']})['entries']['acceptance.py']
        self.assertEqual(base64.b64decode(entry['worktree']['content_base64']),b'working bytes')
        self.assertEqual(base64.b64decode(entry['index_preimages'][0]['content_base64']),b'staged bytes')
        self.assertEqual(base64.b64decode(entry['commit_preimages'][0]['content_base64']),b'assert True\n')

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
        subject={'id':'run','enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'governing_digest':'g','repositories':{'r':{'location':str(repo)}}}
        with self.assertRaises(WorkflowError):apply_enforcement(subject,'protect-inventory',record)
        record['authorization']={'approved':True,'actor_id':'fixture-user','inventory_hash':record['baseline']['inventory_hash'],'governing_digest':'g','reason':'declared acceptance contract'}
        updated=apply_enforcement(subject,'protect-inventory',record)
        self.assertEqual(updated['protected_inventories']['r']['inventory'],inv)
        record['inventory']={'paths':[],'governing_digest':'g'}
        with self.assertRaises(WorkflowError):apply_enforcement(updated,'protect-inventory',record)

    def test_proposal_and_user_approval_bind_exact_retained_change(self):
        from workflow_lib.enforcement_events import apply_enforcement
        repo=self.setup_repo();api=self.api();inventory={'paths':['acceptance.py']}
        baseline=api.snapshot_protected(repo,inventory)
        subject={'enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1},
            'repositories':{'r':{'location':str(repo)}},
            'protected_inventories':{'r':{'inventory':inventory,'baseline':baseline}}}
        (repo/'acceptance.py').write_text('approved candidate')
        observation=api.observe_protected_changes(repo,inventory,baseline)
        subject=apply_enforcement(subject,'propose-protected-change',{'repo_id':'r','observation':observation})
        approval={'repo_id':'r','observation_hash':observation['observation_hash'],'approved':True,
            'actor_id':'fixture-user','reason':'changed business acceptance rule',
            'provenance':{'kind':'user-message','ref':'fixture-message'}}
        updated=apply_enforcement(subject,'approve-protected-change',approval)
        self.assertEqual(updated['protected_authorizations'],[approval])
        with self.assertRaises(WorkflowError):
            apply_enforcement(subject,'approve-protected-change',{**approval,'observation_hash':'different'})
        with self.assertRaises(WorkflowError):
            apply_enforcement(subject,'approve-protected-change',{**approval,'provenance':{}})

    def test_ignored_symlink_referent_changes_and_external_targets_are_not_unprotected(self):
        repo=self.setup_repo();api=self.api()
        (repo/'.git/info/exclude').write_text('target\n')
        (repo/'target').write_text('strict scanner')
        (repo/'config-link').symlink_to('target')
        subprocess.run(['git','add','config-link'],cwd=repo,check=True)
        subprocess.run(['git','commit','-qm','protected link'],cwd=repo,check=True)
        inventory={'paths':['config-link']};baseline=api.snapshot_protected(repo,inventory)
        (repo/'target').write_text('relaxed scanner')
        self.assertEqual(api.observe_protected_changes(repo,inventory,baseline)['changed_paths'],['config-link'])
        outside=repo.parent/('outside-'+repo.name);outside.write_text('outside scope')
        self.addCleanup(outside.unlink)
        (repo/'config-link').unlink();(repo/'config-link').symlink_to(outside)
        with self.assertRaises(WorkflowError):api.snapshot_protected(repo,inventory)
