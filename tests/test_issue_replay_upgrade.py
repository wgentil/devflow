"""Cross-version and storage maintenance coverage uses frozen independent oracles."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib import store, storage_maintenance as maintenance
from workflow_lib import issue_replay_recovery as recovery
from test_issue_replay_recovery import FIXTURES

class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.tmp) / 'control'
        (self.root / 'events').mkdir(parents=True)
        self.case = json.loads((FIXTURES / 'v0.3.17-proof.json').read_text())
        for e in self.case['events']:
            (self.root / 'events' / f"{e['sequence']:08d}.json").write_text(json.dumps(e))

    def recover(self, choice='legacy'):
        inspected = recovery.inspect_replay_recovery(self.root)
        req = {'inspection': inspected['binding'], 'selections': [
            {'event_digest': e['event_digest'], 'choice': choice} for e in inspected['unresolved']],
            'actor_id':'fixture-user','operation_id':'recovery','confirmed':True,
            'provenance':{'kind':'user-message','ref':'fixture-confirmation'}}
        validation = recovery.validate_replay_recovery(self.root, req)
        return recovery.apply_replay_recovery(self.root, {**req,'validation':validation})

    def convert(self):
        # Explicitly abandon the owned fixture attempt; production active-work rules stay intact.
        run = next(iter(store.read_state(self.root)['data']['runs'].values()))
        if run['active_attempt']:
            store.transact(self.root, 6, 'abandon-fixture', {'kind':'run.attempt.abandoned',
                'payload':{'run_id':run['id'],'token':run['active_attempt']['token']}})
        plan = maintenance.compaction_plan(self.root)
        return maintenance.apply_compaction(self.root, plan['plan_hash'])

    def test_recovered_legacy_root_backup_relocate_convert_and_audit(self):
        before_bytes = {p.name:p.read_bytes() for p in (self.root/'events').glob('*.json')}
        self.recover()
        run=next(iter(store.read_state(self.root)['data']['runs'].values()))
        store.transact(self.root,6,'abandon-fixture',{'kind':'run.attempt.abandoned',
            'payload':{'run_id':run['id'],'token':run['active_attempt']['token']}})
        expected=store.read_state(self.root)['data']
        backup = Path(self.tmp)/'backup'
        maintenance.backup_control(self.root, backup)
        self.assertTrue(maintenance.verify_store(backup,full=True)['valid'])
        self.assertEqual(store.read_state(backup)['data'], expected)
        self.convert()
        self.assertTrue(maintenance.verify_store(self.root, full=True)['valid'])
        for name, raw in before_bytes.items():
            self.assertEqual(maintenance.read_raw_event(self.root,int(name[:-5]))['bytes'],raw)
        backup2=Path(self.tmp)/'v2-backup';maintenance.backup_control(self.root,backup2)
        self.assertTrue(maintenance.verify_store(backup2,full=True)['valid'])

    def test_append_preserves_prefix_selection(self):
        self.recover()
        store.transact(self.root,6,'normal-append',{'kind':'note','payload':{'retained':'yes'}})
        self.assertEqual(store.read_state(self.root)['data']['retained'],'yes')
        self.assertTrue(maintenance.verify_store(self.root,full=True)['valid'])

    def test_missing_or_tampered_recovery_authority_fails(self):
        self.recover()
        manifest=next((self.root/'replay-recovery').glob('*.json'))
        manifest.unlink()
        with self.assertRaises(store.WorkflowError) as caught: store.read_state(self.root)
        self.assertEqual(caught.exception.code,'ISSUE_POLICY_SELECTION_REQUIRED')

    def test_recovered_v2_full_replay_and_archived_events(self):
        self.recover();self.convert()
        plan=maintenance.compaction_plan(self.root);maintenance.apply_compaction(self.root,plan['plan_hash'])
        self.assertTrue(maintenance.verify_store(self.root,full=True)['valid'])

    def test_v2_scoped_reads_do_not_scan_history(self):
        self.recover();self.convert()
        from workflow_lib.storage_access import read_current
        with patch.object(recovery,'raw_history',side_effect=AssertionError('full scan')):
            self.assertIn('spec',read_current(self.root)['data'])

    def test_conversion_resume_retains_recovery_authority(self):
        self.recover()
        # Crash after the verified backup, before source activation; resume the same plan.
        run=next(iter(store.read_state(self.root)['data']['runs'].values()))
        store.transact(self.root,6,'abandon-fixture',{'kind':'run.attempt.abandoned',
            'payload':{'run_id':run['id'],'token':run['active_attempt']['token']}})
        plan=maintenance.compaction_plan(self.root)
        with patch.object(maintenance, '_publish_database', side_effect=OSError('owned interruption')):
            with self.assertRaises(store.WorkflowError) as caught: maintenance.apply_compaction(self.root,plan['plan_hash'])
        self.assertEqual(caught.exception.code,'MAINTENANCE_IO_FAILED')
        first=maintenance.resume_compaction(self.root)
        self.assertEqual(maintenance.apply_compaction(self.root,plan['plan_hash']),first)
        self.assertTrue(maintenance.verify_store(self.root,full=True)['valid'])

    def test_v2_existing_unstamped_projection_cannot_change_policy(self):
        root=self.root
        for p in (root/'events').glob('*.json'):p.unlink()
        root.rmdir() if not root.exists() else None
        with tempfile.TemporaryDirectory() as oldtmp:
            archive=subprocess.run(['git','archive','v0.3.18','skills/workflow/scripts'],capture_output=True,check=True).stdout
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(oldtmp,filter='data')
            script='''import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from workflow_lib import store,sqlite_store
root=Path(sys.argv[2]);sqlite_store.initialize_store(root)
for event in json.loads(Path(sys.argv[3]).read_text())['events']:
 store.transact(root,event['sequence']-1,event['operation_id'],{'kind':event['kind'],'payload':event['payload']})
'''
            subprocess.run([sys.executable,'-B','-c',script,str(Path(oldtmp)/'skills/workflow/scripts'),str(root),str(FIXTURES/'v0.3.18-start.json')],check=True)
        with self.assertRaises(store.WorkflowError): self.recover('legacy')
        self.recover('v0.3.18')
        self.assertTrue(maintenance.verify_store(root,full=True)['valid'])
