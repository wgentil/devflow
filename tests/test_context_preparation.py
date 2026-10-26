import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from large_context_fixtures import make_context_project
from workflow_lib.store import read_state,transact,WorkflowError
from workflow_lib.document_units import canonical
from workflow_lib.runs import issue_attempt
from workflow_lib.lifecycle_hooks import prepared_context

class ContextPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.f=make_context_project(Path(self.temp.name)/'project',delivered_runs=3,history_bytes=50000)
    def prepare(self,run=None,**kw):
        from workflow_lib.context_preparation import prepare_context
        return prepare_context(self.f['root'],run or self.f['run'],{'run_id':'current'},['W1'],stage='implementation',**kw)
    def test_projection_excludes_history_and_operations(self):
        p=self.prepare(state=self.f['state']);body=canonical(p.payload).decode()
        self.assertNotIn('historical-',body);self.assertNotIn('review_packages',body);self.assertNotIn('operations',p.payload)
        self.assertEqual([r['id'] for r in p.payload['selection']['spec']['requirements']],['R1'])
        self.assertEqual(p.journal_version,self.f['state']['version'])
    def test_projection_rejects_arbitrary_run_override(self):
        run=copy.deepcopy(self.f['run']);run['authorization_scope']={'write':True}
        with self.assertRaises(WorkflowError):self.prepare(run)
    def test_proposed_attempt_binding_is_preserved(self):
        updated=issue_attempt(self.f['run'],'W1');p=self.prepare(updated)
        self.assertEqual(p.scope['attempt_id'],updated['active_attempt']['token'])
        value=prepared_context(self.f['root'],updated,{'run_id':'current'},['W1'],stage='implementation',prepared=p)
        self.assertEqual(value['task_view']['coverage']['missing_ids'],[])
    def test_direct_helper_still_checks_live_approval(self):
        self.prepare();pair=self.f['state']['data']['spec_pair'];(self.f['repo']/pair['markdown_path']).write_text('unapproved',encoding='utf-8')
        with self.assertRaises(WorkflowError):self.prepare()
        self.assertTrue(read_state(self.f['root'])['data']['spec_approval_invalidated'])
    def test_read_view_rejects_changed_journal_tail(self):
        from workflow_lib.context_preparation import assert_preparation_current
        p=self.prepare();state=read_state(self.f['root']);transact(self.f['root'],state['version'],'concurrent',{'kind':'fixture','payload':{'concurrent':True}})
        with self.assertRaises(WorkflowError):assert_preparation_current(self.f['root'],p,state)
    def test_preflight_time_does_not_consume_worker_deadline(self):
        from workflow_lib.repo_input_gate import preflight_inputs
        def costly(*args,**kw):
            result=preflight_inputs(*args,**kw);result['timing']['preflight_ms']=6000;return result
        with patch('workflow_lib.context_preparation.preflight_inputs',side_effect=costly):p=self.prepare()
        value=prepared_context(self.f['root'],self.f['run'],{'run_id':'current'},['W1'],stage='implementation',prepared=p)
        self.assertGreaterEqual(value['preparation']['preflight_ms'],6000)
        self.assertGreaterEqual(value['preparation']['worker_ms'],0)
        self.assertLessEqual(value['budget']['serialized_bytes'],20000)
    def test_standalone_entry_adds_at_most_one_replay(self):
        original=read_state;calls=[]
        def counted(root,*args,**kwargs):calls.append(root);return original(root)
        with patch('workflow_lib.context_preparation.read_current',side_effect=counted):self.prepare()
        self.assertEqual(len(calls),1)
        calls.clear()
        with patch('workflow_lib.context_preparation.read_current',side_effect=counted):self.prepare(state=self.f['state'])
        self.assertEqual(calls,[])

    def test_prepared_scope_cannot_be_reused_for_another_stage_or_attempt(self):
        p=self.prepare()
        with self.assertRaises(WorkflowError):prepared_context(self.f['root'],self.f['run'],{'run_id':'current'},['W1'],stage='review',prepared=p)
        updated=issue_attempt(self.f['run'],'W1')
        with self.assertRaises(WorkflowError):prepared_context(self.f['root'],updated,{'run_id':'current'},['W1'],stage='implementation',prepared=p)
    def test_public_hook_output_stays_bounded_after_parent_expands_worker_artifact(self):
        from workflow_lib.lifecycle_hooks import run_lifecycle_hook
        response=run_lifecycle_hook('prepare-context',{'root':str(self.f['root']),'run_id':'current','item_ids':['W1']},required=True)
        self.assertEqual(response['status'],'allow')
        self.assertLessEqual(len(canonical(response)),8192)
        self.assertEqual(response['output_bytes'],len(canonical(response)))

    def test_untrusted_envelope_cannot_inject_approval_or_history(self):
        from workflow_lib.context_preparation import prepare_context
        for extra in ({'authorization_scope':{'write':True}},{'reviews':{'raw_history':'must not cross worker boundary'}},{'run_id':'foreign'}):
            with self.subTest(extra=extra):
                with self.assertRaises(WorkflowError):prepare_context(self.f['root'],self.f['run'],{'run_id':'current',**extra},['W1'],stage='implementation')

    def test_required_worker_timeout_identifies_phase_and_keeps_token_absent(self):
        from workflow_lib.lifecycle_hooks import run_lifecycle_hook
        from workflow_lib.process_liveness import process_alive
        worker=self.f['repo']/'slow.py';pid=self.f['root']/'worker.pid'
        worker.write_text('import os,sys,time\nfrom pathlib import Path\nsys.stdin.readline()\nPath('+repr(str(pid))+').write_text(str(os.getpid()))\ntime.sleep(30)\n')
        with patch('workflow_lib.lifecycle_hooks.WORKER_PATH',worker):
            response=run_lifecycle_hook('prepare-context',{'root':str(self.f['root']),'run_id':'current','item_ids':['W1']},required=True,deadline_seconds=0.3)
        self.assertEqual(response['reason_code'],'HOOK_DEADLINE_EXCEEDED')
        self.assertFalse(process_alive(int(pid.read_text())))
        self.assertIsNone(read_state(self.f['root'])['data']['runs']['current']['active_attempt'])
        self.assertEqual(response['details']['phase'],'worker')
        self.assertEqual(response['limits']['deadline_seconds'],0.3)

    def test_parent_elapsed_preflight_over_five_seconds_preserves_worker_allowance(self):
        import time
        from workflow_lib.repo_input_gate import preflight_inputs
        from workflow_lib.lifecycle_hooks import run_lifecycle_hook
        clock=time.monotonic;offset=[0]
        def costly(*args,**kw):
            value=preflight_inputs(*args,**kw);offset[0]=6;return value
        with patch('time.monotonic',side_effect=lambda:clock()+offset[0]),patch('workflow_lib.context_preparation.preflight_inputs',side_effect=costly):
            response=run_lifecycle_hook('prepare-context',{'root':str(self.f['root']),'run_id':'current','item_ids':['W1']},required=True)
        self.assertEqual(response['status'],'allow',response)
        self.assertGreaterEqual(response['result']['preparation']['preflight_ms'],6000)
