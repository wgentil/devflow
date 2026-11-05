"""Owned Git observations support compact, pure historical receipt validation."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError


class ProtectionReceiptTests(unittest.TestCase):
    def fixture(self):
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.enforcement_live import source_observation
        repo=Path(self.enterContext(tempfile.TemporaryDirectory()))
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):
            subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'z.conf').write_text('strict');(repo/'a.py').write_text('assert True')
        subprocess.run(['git','add','.'],cwd=repo,check=True)
        subprocess.run(['git','commit','-qm','baseline'],cwd=repo,check=True)
        inventory={'paths':['z.conf','a.py'],'governing_digest':'fixture-governing'}
        subject={'enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1},
            'repositories':{'r':{'location':str(repo)}},'protected_inventories':{
                'r':{'inventory':inventory,'baseline':snapshot_protected(repo,inventory)}}}
        subject['source_identity']=source_observation(subject)['source_identity']
        return repo,subject

    def test_actual_receipt_validates_without_live_reads_and_is_not_new_authorization(self):
        from workflow_lib.enforcement_live import assert_protection_current
        from workflow_lib.protection_receipts import validate_receipts
        repo,subject=self.fixture();receipts=assert_protection_current(subject)
        self.assertNotIn('content_base64',str(receipts))
        (repo/'z.conf').write_text('weakened after original observation')
        with patch('subprocess.run',side_effect=AssertionError('Historical validation must not run Git.')):
            with patch.object(Path,'read_bytes',side_effect=AssertionError('Historical validation must not read current files.')):
                validate_receipts(subject,receipts)
        with self.assertRaises(WorkflowError):assert_protection_current(subject)

    def test_changed_metadata_missing_scope_and_unretained_observation_are_rejected(self):
        from workflow_lib.enforcement_live import assert_protection_current
        from workflow_lib.protection_receipts import validate_receipts
        _,subject=self.fixture();receipts=assert_protection_current(subject)
        for field in ('after_hash','baseline_hash','inventory_hash','observation_hash'):
            altered=copy.deepcopy(receipts);altered['r'][field]='0'*64
            with self.subTest(field=field),self.assertRaises(WorkflowError):validate_receipts(subject,altered)
        with self.assertRaises(WorkflowError):validate_receipts(subject,{})
