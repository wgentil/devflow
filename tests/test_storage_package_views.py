"""Routine reads and delta writes never hydrate a run's old package bodies."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib import store,sqlite_store,stored_records
from workflow_lib.storage_access import read_current
from workflow_lib.storage_maintenance import compaction_plan,apply_compaction
from large_context_fixtures import make_context_project

class PackageViewTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory());f=make_context_project(Path(self.temp)/'project');self.root=f['root']
        state=store.read_state(self.root);run=state['data']['runs']['current'];run['review_packages']={}
        for i in range(12):
            package={'schema_version':1,'run_id':'current','role':'branch','input_paths':['a.py'],'text':str(i)+'x'*100000}
            package['package_hash']=stored_records.digest(package);run['review_packages'][package['package_hash']]=package
        self.expected=copy.deepcopy(run)
        store.transact(self.root,state['version'],'packages',{'kind':'fixture','payload':{'runs':{'current':run}}})
        plan=compaction_plan(self.root);apply_compaction(self.root,plan['plan_hash'])
    def test_selected_run_read_prepare_and_delta_write_skip_package_bodies(self):
        original=stored_records.read_object
        def guarded(root,reference,**options):
            if reference['kind']=='review-package':raise AssertionError('HISTORICAL_PACKAGE_BODY_READ')
            return original(root,reference,**options)
        from workflow_lib.context_preparation import prepare_context,commit_prepared_attempt
        from workflow_lib.runs import issue_attempt
        with patch.object(stored_records,'read_object',side_effect=guarded):
            state=read_current(self.root,run_id='current');run=state['data']['runs']['current']
            proposed=issue_attempt(run,'W1');prepared=prepare_context(self.root,proposed,{'run_id':'current'},['W1'],stage='implementation',state=state)
            event={'kind':'run.attempt.issued','payload':{'run_id':'current','attempt':proposed['active_attempt']}}
            result=commit_prepared_attempt(self.root,prepared,'next',event)
            self.assertFalse(result['replayed'])
        actual=store.read_state(self.root)['data']['runs']['current']
        self.assertEqual(actual['review_packages'],self.expected['review_packages'])
    def test_explicit_inspection_and_selected_validator_require_verified_body(self):
        from workflow_lib.run_archives import read_run
        self.assertEqual(read_run(self.root,'current'),self.expected)
        selected=read_current(self.root,run_id='current')['data']['runs']['current']
        package=next(iter(selected['review_packages'].values()))
        with patch.object(stored_records,'read_object',side_effect=store.WorkflowError('STORAGE_OBJECT_MISSING','missing selected body')):
            with self.assertRaises(store.WorkflowError):
                from workflow_lib.host_completion import package_current
                package_current(selected,package)
