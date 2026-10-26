"""New roots choose v2; legacy authority and recovery remain explicit."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib import store,sqlite_store
from workflow_lib.storage_format import detect_layout
from workflow_lib.releases import release_descriptor
from control_store_fixtures import legacy_root

class StorageCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory());self.base=Path(self.temp).resolve();self.root=self.base/'new control é東京'
    def cli(self,*args,expected=0):
        result=subprocess.run([sys.executable,str(ROOT/'skills/workflow/scripts/run.py'),*map(str,args)],capture_output=True,encoding='utf-8',timeout=60)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr);return json.loads(result.stdout)
    def test_new_default_uses_separate_storage_and_logical_versions(self):
        self.assertEqual(store.read_state(self.root)['version'],0);self.assertFalse(self.root.exists())
        first=store.transact(self.root,0,'first',{'kind':'note','payload':{'value':'é東京'}})
        self.assertEqual(detect_layout(self.root)['layout'],'v2');self.assertEqual(first['state']['schema_version'],1)
        descriptor=release_descriptor();self.assertEqual(descriptor['storage_format_version'],2);self.assertEqual(descriptor['supported_storage_formats'],[1,2]);self.assertEqual(descriptor['supported_schemas'],[1])
        self.assertEqual(store.transact(self.root,-1,'first',{'kind':'different','payload':{}})['event'],first['event'])
    def test_new_default_does_not_convert_existing_root(self):
        legacy_root(self.root);store.transact(self.root,0,'seed',{'kind':'note','payload':{'value':'legacy'}})
        project=self.base/'project';project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True)
        self.cli('host','init','--project-dir',project,'--root',self.root,'--operation-id','init-existing')
        self.assertEqual(detect_layout(self.root)['layout'],'legacy');self.assertFalse((self.root/'format.json').exists())
        self.assertEqual(json.loads((self.root/'events/00000001.json').read_text(encoding="utf-8"))['schema_version'],1)
    def test_missing_sqlite_preserves_legacy_access_and_new_root_retry(self):
        legacy=legacy_root(self.base/'legacy');store.transact(legacy,0,'one',{'kind':'note','payload':{'value':'old'}})
        with patch.object(sqlite_store,'_sqlite',side_effect=store.WorkflowError('SQLITE_UNAVAILABLE','Use Python with SQLite support.')):
            self.assertEqual(store.read_state(legacy)['data']['value'],'old')
            store.transact(legacy,1,'two',{'kind':'note','payload':{'value':'updated'}})
            with self.assertRaises(store.WorkflowError) as caught:store.transact(self.root,0,'first',{'kind':'note','payload':{'value':'new'}})
            self.assertEqual(caught.exception.code,'SQLITE_UNAVAILABLE')
        self.assertEqual(detect_layout(self.root)['layout'],'uninitialized')
        store.transact(self.root,0,'first',{'kind':'note','payload':{'value':'new'}})
        self.assertEqual(detect_layout(self.root)['layout'],'v2')
    def crash_initialize(self,phase):
        code="""import os,sys
from pathlib import Path
from workflow_lib import store
original=store._atomic_json
def publish(path,value):
 original(path,value)
 if (sys.argv[2]=='ready' and path.name=='intent.json' and value.get('kind')=='initialize' and value.get('phase')=='ready') or (sys.argv[2]=='selected' and path.name=='format.json'):os._exit(73)
store._atomic_json=publish
store.transact(Path(sys.argv[1]),0,'first',{'kind':'note','payload':{'value':'first'}})
"""
        result=subprocess.run([sys.executable,'-B','-c',code,str(self.root),phase],env={**os.environ,'PYTHONPATH':str(ROOT/'skills/workflow/scripts')},capture_output=True,timeout=20)
        self.assertEqual(result.returncode,73,result.stdout+result.stderr)
    def test_public_resume_initialization_and_retry_first_work(self):
        self.crash_initialize('ready')
        with self.assertRaises(store.WorkflowError):store.read_state(self.root)
        result=self.cli('state','compact','--root',self.root,'--resume','--operation-id','recover-init','--actor-id','owner')
        self.assertTrue(result['completed']);self.assertEqual(store.read_state(self.root)['version'],0)
        store.transact(self.root,0,'first',{'kind':'note','payload':{'value':'first'}})
        self.assertEqual(store.read_state(self.root)['data']['value'],'first')
    def test_public_initialization_resume_preserves_a_newer_selected_tail(self):
        self.crash_initialize('selected')
        store.transact(self.root,0,'new-writer',{'kind':'note','payload':{'value':'committed tail'}})
        self.cli('state','compact','--root',self.root,'--resume','--operation-id','recover-init','--actor-id','owner')
        self.assertEqual(store.read_state(self.root)['version'],1);self.assertEqual(store.read_state(self.root)['data']['value'],'committed tail')
    def test_unselected_initialization_preserves_a_late_legacy_writer(self):
        from workflow_lib.storage_maintenance import resume_compaction
        self.crash_initialize('ready');legacy_root(self.root)
        event={'schema_version':1,'sequence':1,'operation_id':'old-writer','kind':'note','payload':{'legacy':'committed'}}
        path=self.root/'events/00000001.json';path.write_text(json.dumps(event));original=path.read_bytes()
        with self.assertRaises(store.WorkflowError):resume_compaction(self.root)
        self.assertEqual(path.read_bytes(),original);self.assertFalse((self.root/'format.json').exists())

    def test_corrupt_initial_operation_identity_refuses_activation(self):
        from workflow_lib.storage_maintenance import resume_compaction
        self.crash_initialize('ready');path=self.root/'maintenance/intent.json'
        value=json.loads(path.read_text(encoding="utf-8"));value['initiating_operation_hash']='not-a-hash';path.write_text(json.dumps(value))
        with self.assertRaises(store.WorkflowError):resume_compaction(self.root)
        self.assertFalse((self.root/'format.json').exists())

    def test_guided_lifecycle_both_formats(self):
        from test_verification_flow import VerificationFlowTests
        from test_foundation_flow import FoundationFlowTests
        for format_version in (1,2):
            for fixture,name,root_field in (
                    (FoundationFlowTests,'test_repository_spec_approval_rechecks_pair_without_events','control'),
                    (VerificationFlowTests,'test_end_to_end_code_gate_review_acceptance_and_delivery_preparation','control')):
                with self.subTest(format=format_version,flow=name):
                    case=fixture(name);case.setUp()
                    try:
                        root=getattr(case,root_field)
                        if format_version==1:legacy_root(root)
                        getattr(case,name)()
                        self.assertEqual(detect_layout(root)['storage_format'],format_version)
                    finally:case.tearDown()
