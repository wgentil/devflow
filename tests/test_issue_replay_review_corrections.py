"""Reproduce final review findings without bypassing normal positive controls."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_issue_replay_recovery as fixtures
from workflow_lib import store, storage_maintenance as maintenance
from workflow_lib import issue_replay_recovery as recovery
from workflow_lib.platform_lock import sync_directory

class ReviewCorrectionTests(unittest.TestCase):
    setUp = fixtures.RecoveryTests.setUp
    seed = fixtures.RecoveryTests.seed
    api = fixtures.RecoveryTests.api
    request = fixtures.RecoveryTests.request
    recover = fixtures.RecoveryTests.recover

    def test_post_link_retry_syncs_source_directory_before_success(self):
        req=self.request();validation=recovery.validate_replay_recovery(self.root,req)
        applied={**req,'validation':validation}
        source_dir=(self.root/'replay-recovery').resolve()
        def interrupted(path):
            if Path(path).resolve()==source_dir: raise OSError('post-link interruption')
            return sync_directory(path)
        with patch.object(recovery,'sync_directory',side_effect=interrupted):
            with self.assertRaises(OSError): recovery.apply_replay_recovery(self.root,applied)
        self.assertTrue(list(source_dir.glob('*.json')))
        with patch.object(recovery,'sync_directory',wraps=sync_directory) as synced:
            result=recovery.apply_replay_recovery(self.root,applied)
        self.assertTrue(result['completed'])
        synced_paths=[Path(call.args[0]).resolve() for call in synced.call_args_list]
        self.assertIn(source_dir,synced_paths)
        self.assertIn(self.root.resolve(),synced_paths)

    def test_audit_returns_invalid_result_for_broken_recovery_metadata(self):
        directory=self.root/'replay-recovery';directory.mkdir()
        (directory/'broken.json').write_text('{}')
        result=maintenance.verify_store(self.root,full=True)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'],'ISSUE_RECOVERY_INVALID')

    def test_malformed_start_request_is_typed_during_inspection_and_replay(self):
        path=self.root/'events/00000004.json'
        value=json.loads(path.read_text())
        for malformed in ([], None, 7):
            value['payload']['request']=malformed;path.write_text(json.dumps(value))
            for operation in (recovery.inspect_replay_recovery,store.read_state):
                with self.subTest(value=malformed,operation=operation.__name__),self.assertRaises(store.WorkflowError):operation(self.root)

    def test_nonobject_cli_input_returns_json_error(self):
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        input_=Path(self.tmp)/'request.json';input_.write_text('[]')
        for operation in ('start','replay-recovery-validate','replay-recovery-apply'):
            result=subprocess.run([sys.executable,str(entry),'issues',operation,'--root',str(self.root),
                '--input',str(input_),'--operation-id','owned-recovery'],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(json.loads(result.stdout)['error'],'INVALID_INPUT')
            self.assertNotIn('Traceback',result.stderr)

    def test_full_audit_rejects_recovery_logical_operation_collision(self):
        req=self.request();validation=recovery.validate_replay_recovery(self.root,req)
        applied={**req,'validation':validation};recovery.apply_replay_recovery(self.root,applied)
        (self.root/'events/00000007.json').write_text(json.dumps({'schema_version':1,'sequence':7,
            'operation_id':'recover-one','kind':'note','payload':{}}))
        result=maintenance.verify_store(self.root,full=True)
        self.assertFalse(result['valid'])
        with self.assertRaises(store.WorkflowError): recovery.apply_replay_recovery(self.root,applied)

    def test_full_audit_rejects_recovery_physical_operation_collision(self):
        from workflow_lib.storage_audit import paths,write_record
        from workflow_lib.document_units import digest
        self.recover()
        request={'output':'owned-fixture'}
        write_record(paths(self.root,'recover-one')[0],{'audit_version':1,'operation_id':'recover-one',
            'actor_id':'fixture-owner','kind':'backup','request':request,
            'request_hash':digest({'kind':'backup','request':request,'actor_id':'fixture-owner'}),
            'result':{'completed':True}})
        result=maintenance.verify_store(self.root,full=True)
        self.assertFalse(result['valid'])

    def test_scalar_and_null_cli_recovery_inputs_are_typed(self):
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        input_=Path(self.tmp)/'request.json'
        for value in ('null','7'):
            input_.write_text(value)
            result=subprocess.run([sys.executable,str(entry),'issues','replay-recovery-validate','--root',str(self.root),
                '--input',str(input_),'--operation-id','owned-recovery'],capture_output=True,text=True)
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(json.loads(result.stdout)['error'],'INVALID_INPUT')

    def test_stale_prefix_returns_specific_invalid_audit_result(self):
        self.recover()
        path=self.root/'events/00000001.json';path.write_text(path.read_text()+' ')
        result=maintenance.verify_store(self.root,full=True)
        self.assertFalse(result['valid'])
        self.assertEqual(result['error_code'],'ISSUE_RECOVERY_STALE')

    def test_v2_audit_detects_recovery_namespace_collisions(self):
        import test_issue_replay_upgrade as upgrades
        from workflow_lib.storage_audit import paths,write_record
        from workflow_lib.document_units import digest
        for collision in ('logical','physical-pending'):
            self.root=Path(self.tmp)/collision;self.seed('v0.3.17-proof.json');self.recover()
            upgrades.UpgradeTests.convert(self)
            if collision=='logical':
                # Simulate corrupted/imported data with internally valid indexes.
                with patch('workflow_lib.storage_audit.operation_reserved',return_value=None):
                    store.transact(self.root,7,'recover-one',{'kind':'note','payload':{}})
            else:
                request={'output':'owned-fixture'}
                write_record(paths(self.root,'recover-one')[1],{'audit_version':1,'operation_id':'recover-one',
                    'actor_id':'fixture-owner','kind':'backup','request':request,
                    'request_hash':digest({'kind':'backup','request':request,'actor_id':'fixture-owner'})})
            self.assertFalse(maintenance.verify_store(self.root,full=True)['valid'])
