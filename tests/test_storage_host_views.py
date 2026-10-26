"""Host hints cannot authorize work or force historical materialization."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from test_claude_hooks import HookTests as _HookTests
from workflow_lib import store, sqlite_store
from workflow_lib.host_hook import evaluate
from workflow_lib.host_locators import locator_path
from workflow_lib.hosts import apply_host_event
from workflow_lib.storage_access import read_current

class IndexedHookTests(_HookTests):
    def attach(self):
        sqlite_store.initialize_store(self.root)
        super().attach()

class StorageHostViewTests(unittest.TestCase):
    def setUp(self):
        self.fixture=IndexedHookTests('test_inactive_no_files_or_shell_effect');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);self.fixture.attach()
        self.root,self.project=self.fixture.root,self.fixture.project
    def test_missing_hints_preserve_completion(self):
        path=locator_path(self.project,'claude','s1');path.unlink(missing_ok=True);path.with_suffix('.tasks.json').unlink(missing_ok=True)
        with patch.object(sqlite_store,'read_state',side_effect=AssertionError('full replay')):
            result=evaluate(self.project,'s1','TaskCompleted','task')
        self.assertEqual((result['status'],result['reason_code']),('block','ACTIVE_ATTEMPT'))
    def test_cached_view_cannot_waive_authority(self):
        path=locator_path(self.project,'claude','s1').with_suffix('.brief.json')
        path.write_text('{"fingerprint":"old","status":"allow"}')
        from workflow_lib.host_locators import write_task_index
        write_task_index(self.project,'claude','s1',self.root,['task'])
        store.transact(self.root,3,'detach',{'kind':'domain.host.detach','payload':{'request':{'binding_id':'b1','revision':1}}})
        with patch.object(sqlite_store,'read_state',side_effect=AssertionError('full replay')):
            decision=evaluate(self.project,'s1','TaskCompleted','task')
        self.assertEqual(decision['status'],'block')
    def test_sessions_read_only_selected_history(self):
        data=store.read_state(self.root)['data'];other=copy.deepcopy(data['runs']['run']);other['id']='other'
        data['runs']['other']=other;data['host_bindings']['other-binding']={**data['host_bindings']['b1'],'binding_id':'other-binding','session_id':'s2','run_id':'other'}
        data['host_tasks']['claude:s2:other-task']={'host':'claude','session_id':'s2','task_id':'other-task','binding_id':'other-binding','run_id':'other'}
        store.transact(self.root,3,'other',{'kind':'fixture','payload':data})
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.host_projection'),'indexed host reader is missing')
        from workflow_lib.host_projection import read_host
        selected=read_host(self.root,host='claude',session_id='s1')
        self.assertEqual(set(selected['data']['runs']),{'run'})
        self.assertEqual(set(selected['data']['host_bindings']),{'b1'})
        self.assertEqual(len(selected['data']['host_tasks']),1)
        self.assertEqual(evaluate(self.project,'s1','TaskCompleted','task')['reason_code'],'ACTIVE_ATTEMPT')

    def test_session_refresh_skips_retired_bindings_and_unused_prices(self):
        from workflow_lib.host_projection import read_host
        from workflow_lib.run_archives import archive_run
        data=store.read_state(self.root)['data'];closed=copy.deepcopy(data['runs']['run'])
        closed.update(id='closed',status='discarded',active_attempt=None,_unrelated_storage_body=True)
        data['runs']['closed']=closed
        data['runs']['run']['model_overrides']=[{'price_version':'current-price'}]
        data['host_bindings']['retired']={**data['host_bindings']['b1'],'binding_id':'retired','status':'detached','run_id':'closed'}
        data['prices']={'old-price':{'_unrelated_storage_body':True},'current-price':{'version':'current-price'}}
        store.transact(self.root,3,'history',{'kind':'fixture','payload':data});archive_run(self.root,'closed')
        original=sqlite_store._decode
        def guard(*args,**options):
            value=original(*args,**options)
            if isinstance(value,dict) and value.get('_unrelated_storage_body'):raise AssertionError('UNRELATED_HOST_HISTORY')
            return value
        with patch.object(sqlite_store,'_decode',side_effect=guard):
            selected=read_host(self.root,host='claude',session_id='s1')
            self.assertEqual(evaluate(self.project,'s1','TaskCompleted','task')['reason_code'],'ACTIVE_ATTEMPT')
        self.assertEqual(set(selected['data']['runs']),{'run'})
        self.assertEqual(set(selected['data']['prices']),{'current-price'})

    def test_v2_outbox_crash_reconciles_without_resending(self):
        from test_journal_integration import DurableOutboxTests
        case=DurableOutboxTests('test_crash_after_external_receipt_reconciles_without_resending')
        case.setUp();self.addCleanup(case.tearDown);sqlite_store.initialize_store(case.root)
        case.test_crash_after_external_receipt_reconciles_without_resending()

if __name__=='__main__':unittest.main()

# The original v1 suite is collected in test_claude_hooks itself.
del _HookTests
