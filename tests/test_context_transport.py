import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from large_context_fixtures import make_context_project
from workflow_lib.store import WorkflowError
from workflow_lib.lifecycle_hooks import prepared_context

class ContextTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name);self.f=make_context_project(self.base/'project')
    def prepare(self):
        from workflow_lib.context_preparation import prepare_context
        return prepare_context(self.f['root'],self.f['run'],{'run_id':'current'},['W1'],stage='implementation')
    def test_wrong_root_run_hash_symlink_and_oversize_artifacts_rejected(self):
        from workflow_lib.context_transport import store_preparation,load_preparation
        p=self.prepare();ref=store_preparation(self.f['root'],p)
        self.assertEqual(load_preparation(self.f['root'],ref,p.binding_hash)['scope']['run_id'],'current')
        path=self.f['root']/'context-preparations'/(ref['id']+'.json');self.assertEqual(path.stat().st_mode&0o777,0o600)
        for root,reference,binding in ((self.base/'foreign',ref,p.binding_hash),(self.f['root'],{**ref,'id':'../bad'},p.binding_hash),(self.f['root'],ref,'0'*64)):
            with self.subTest(root=root):
                with self.assertRaises(WorkflowError):load_preparation(root,reference,binding)
        raw=json.loads(path.read_text(encoding='utf-8'));raw['payload']['scope']['run_id']='foreign';path.write_text(json.dumps(raw),encoding='utf-8')
        with self.assertRaises(WorkflowError):load_preparation(self.f['root'],ref,p.binding_hash)
        path.unlink();path.symlink_to(self.f['repo']/'docs/spec.json')
        with self.assertRaises(WorkflowError):load_preparation(self.f['root'],ref,p.binding_hash)
        with patch('workflow_lib.context_transport.MAX_PREPARATION_BYTES',512):
            with self.assertRaises(WorkflowError):store_preparation(self.f['root'],p)
    def test_input_artifact_removed_on_success_timeout_and_overflow(self):
        p=self.prepare();prepared_context(self.f['root'],self.f['run'],{'run_id':'current'},['W1'],stage='implementation',prepared=p)
        directory=self.f['root']/'context-preparations';self.assertEqual(list(directory.glob('*.json')),[])
        for reason in ('HOOK_DEADLINE_EXCEEDED','HOOK_OUTPUT_OVERFLOW'):
            with patch('workflow_lib.lifecycle_hooks._dispatch_worker',return_value={'status':'block','reason_code':reason,'details':{}}):
                with self.assertRaises(WorkflowError):prepared_context(self.f['root'],self.f['run'],{'run_id':'current'},['W1'],stage='implementation',prepared=p)
            self.assertEqual(list(directory.glob('*.json')),[])
