"""The last dispatch commit must use the context that was actually prepared."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib import store
from control_store_fixtures import legacy_root
import test_routed_native_runtime as native_fixtures
import test_interactive_routing as interactive_fixtures

class DispatchFreshnessTests(unittest.TestCase):
    def fixture(self,interactive=False,legacy=False):
        case=(interactive_fixtures.InteractiveRoutingTests() if interactive else native_fixtures.RoutedNativeRuntimeTests())
        case.setUp();self.addCleanup(case.doCleanups)
        if legacy:
            data=store.read_state(case.root)['data'];root=Path(case.root)/'legacy-root';legacy_root(root)
            store.transact(root,0,'seed',{'kind':'fixture','payload':data});case.root=root
        return case
    def revoke(self,root):
        state=store.read_state(root)
        store.transact(root,state['version'],'revoke-approval',{'kind':'spec.stored','payload':{'spec':state['data']['spec'],'approval':None}})
    def assert_no_start(self,root):
        state=store.read_state(root)
        self.assertFalse(any(event['kind']=='domain.host.native-start' for event in state['operations'].values()))

    def test_native_discovery_cannot_dispatch_after_approval_revocation(self):
        for legacy in (False,True):
            with self.subTest(legacy=legacy):
                case=self.fixture(legacy=legacy);revoked=False
                def discover():
                    nonlocal revoked
                    if not revoked:self.revoke(case.root);revoked=True
                    return copy.deepcopy(case.context)
                case.backend.discover.side_effect=discover
                with self.assertRaises(store.WorkflowError) as caught:case.call()
                self.assertEqual(caught.exception.code,'CONTEXT_PREPARATION_STALE')
                case.backend.invoke.assert_not_called();case.backend.configure.assert_not_called()
                self.assert_no_start(case.root)

    def test_interactive_final_commit_cannot_dispatch_a_stale_preparation(self):
        from workflow_lib import interactive_routing as routing
        for legacy in (False,True):
            with self.subTest(legacy=legacy):
                case=self.fixture(interactive=True,legacy=legacy);bridge=interactive_fixtures.Bridge(case.context);original=routing._commit
                def commit(root,identifier,kind,request,binding,**options):
                    if kind=='native-start':self.revoke(root)
                    return original(root,identifier,kind,request,binding,**options)
                with patch.object(routing,'_commit',side_effect=commit):
                    with self.assertRaises(store.WorkflowError) as caught:routing.dispatch_delegation(case.root,case.request,'interactive-op',bridge)
                self.assertEqual(caught.exception.code,'CONTEXT_PREPARATION_STALE')
                self.assertFalse(bridge.spawns);self.assert_no_start(case.root)
