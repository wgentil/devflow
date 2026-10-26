"""Indexed authority and scoped cache regressions found in the final audit."""
import copy
import json
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"skills/workflow/scripts"))
from unittest.mock import patch
from workflow_lib import sqlite_store, store
from workflow_lib.host_hook import evaluate
from workflow_lib.host_locators import locator_path
from workflow_lib.storage_format import DATABASE_FILE
from workflow_lib.storage_maintenance import verify_store

class StorageSafetyAuditTests(unittest.TestCase):
    def fixture(self):
        from test_storage_host_views import IndexedHookTests
        case=IndexedHookTests('test_inactive_no_files_or_shell_effect');case.setUp()
        self.addCleanup(case.doCleanups);case.attach()
        return case

    def test_missing_hints_cannot_hide_a_stale_authoritative_mapping(self):
        case=self.fixture();state=store.read_state(case.root)
        data=state['data'];old=copy.deepcopy(data['runs']['run']);old['id']='old'
        old.update(status='discarded',active_attempt=None)
        data['runs']['old']=old
        data['host_tasks']['claude:s1:task']['run_id']='old'
        data['host_tasks']['claude:s1:task']['binding_id']='retired'
        data['host_bindings']['retired']={**data['host_bindings']['b1'],'binding_id':'retired','run_id':'old','status':'detached'}
        store.transact(case.root,3,'stale-mapping',{'kind':'fixture','payload':data})
        hint=locator_path(case.project,'claude','s1');hint.unlink(missing_ok=True);hint.with_suffix('.tasks.json').unlink(missing_ok=True)
        result=evaluate(case.project,'s1','TaskCompleted','task')
        self.assertEqual(result['status'],'block',result)
        self.assertEqual(result['reason_code'],'STALE_BINDING')

    def test_remap_cannot_overwrite_a_mapping_outside_the_selected_run(self):
        case=self.fixture();state=store.read_state(case.root)
        data=state['data'];old=copy.deepcopy(data['runs']['run']);old['id']='old'
        data['runs']['old']=old
        data['host_tasks']['claude:s1:task']['run_id']='old'
        data['host_tasks']['claude:s1:task']['binding_id']='retired'
        store.transact(case.root,3,'stale-map',{'kind':'fixture','payload':data})
        with self.assertRaises(store.WorkflowError):
            store.transact(case.root,4,'overwrite',{'kind':'domain.host.task-bind','payload':{'request':{
                'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'}}})
        self.assertEqual(store.read_state(case.root)['version'],4)

    def test_selected_task_row_loss_and_header_corruption_fail_closed(self):
        for corruption in ('task-row','binding-status','binding-witness','task-space'):
            with self.subTest(corruption=corruption):
                case=self.fixture()
                conn=sqlite_store._sqlite().connect(case.root/DATABASE_FILE)
                conn.execute('PRAGMA foreign_keys=ON')
                if corruption=='task-row':
                    conn.execute('DELETE FROM entities WHERE space=? AND key=?',(sqlite_store._space(('host_tasks',)),'claude:s1:task'))
                elif corruption=='task-space':
                    conn.execute('DELETE FROM spaces WHERE path=?',(sqlite_store._space(('host_tasks',)),))
                elif corruption=='binding-witness':
                    conn.execute('DELETE FROM entity_catalog WHERE space=? AND key=?',(sqlite_store._space(('host_bindings',)),'b1'))
                else:
                    conn.execute('UPDATE entities SET status=? WHERE space=? AND key=?',('detached',sqlite_store._space(('host_bindings',)),'b1'))
                conn.commit();conn.close()
                hint=locator_path(case.project,'claude','s1');hint.unlink(missing_ok=True);hint.with_suffix('.tasks.json').unlink(missing_ok=True)
                with self.assertRaises(store.WorkflowError):evaluate(case.project,'s1','TaskCompleted','task')
                self.assertFalse(verify_store(case.root,full=True)['valid'])

    def test_current_context_does_not_read_legacy_or_unrelated_cache_index(self):
        from test_context_artifacts import ArtifactTests
        case=ArtifactTests('test_warm_cache_fresh_provenance_and_source_drift');case.setUp();self.addCleanup(case.doCleanups)
        sqlite_store.initialize_store(case.control)
        import workflow_lib.context_artifacts as cache
        directory=case.control/'context-artifacts';directory.mkdir(exist_ok=True)
        legacy=directory/'index.json';legacy.write_text(json.dumps({'schema_version':1,'entries':{str(i):{'history':'x'*1000} for i in range(1000)}}))
        original=cache._read
        def selected(path):
            if Path(path).resolve()==legacy.resolve():raise AssertionError('HISTORICAL_CACHE_INDEX_READ')
            return original(path)
        with patch.object(cache,'_read',side_effect=selected):
            cold=cache.resolve_cached_units(case.control,case.selection)
            warm=cache.resolve_cached_units(case.control,case.selection)
        self.assertEqual(cold['cache_outcome'],'miss');self.assertEqual(warm['cache_outcome'],'hit')
        self.assertEqual(cold['artifact_id'],warm['artifact_id'])
        self.assertTrue(legacy.exists(),'retained legacy cache cannot be deleted by ordinary reads')


    def test_v2_cache_invalidation_retains_content_and_unknown_files(self):
        from test_context_artifacts import ArtifactTests
        from workflow_lib import context_artifacts as cache
        from workflow_lib.document_units import digest
        case=ArtifactTests('test_warm_cache_fresh_provenance_and_source_drift');case.setUp();self.addCleanup(case.doCleanups)
        sqlite_store.initialize_store(case.control)
        first=cache.resolve_cached_units(case.control,case.selection)
        other=cache.resolve_cached_units(case.control,{**case.selection,'selections':[{'source_id':'other'}]})
        unknown=case.control/'context-artifacts/scopes/unknown.json';unknown.write_text('{}')
        result=cache.invalidate_context_artifacts(case.control,{'b':'changed'},digest({}))
        self.assertFalse(result['affected_ids_complete'])
        self.assertIn(first['artifact_id'],result['affected_ids'])
        self.assertNotIn(other['artifact_id'],result['affected_ids'])
        self.assertTrue(unknown.is_file())
        self.assertTrue(cache.inspect_context_artifact(case.control,first['artifact_id']))
        self.assertEqual(cache.resolve_cached_units(case.control,case.selection)['cache_outcome'],'miss')
        self.assertEqual(cache.resolve_cached_units(case.control,{**case.selection,'selections':[{'source_id':'other'}]})['cache_outcome'],'hit')

    def test_opaque_unknown_metadata_retains_legacy_types(self):
        import tempfile
        from control_store_fixtures import legacy_root
        value={'unknown_records':{'entry':{'status':42,'host':['opaque'],'id':True,'run_id':{'opaque':1}}}}
        with tempfile.TemporaryDirectory() as temporary:
            legacy=legacy_root(Path(temporary)/'legacy');indexed=Path(temporary)/'indexed'
            for root in (legacy,indexed):store.transact(root,0,'opaque',{'kind':'unknown.patch','payload':value})
            self.assertEqual(store.read_state(legacy),store.read_state(indexed))
            self.assertTrue(verify_store(indexed,full=True)['valid'])

    def test_explicit_full_read_cannot_omit_a_missing_witness(self):
        case=self.fixture()
        conn=sqlite_store._sqlite().connect(case.root/DATABASE_FILE)
        conn.execute('DELETE FROM entity_catalog WHERE space=? AND key=?',(sqlite_store._space(('host_bindings',)),'b1'))
        conn.commit();conn.close()
        with self.assertRaises(store.WorkflowError):store.read_state(case.root)
