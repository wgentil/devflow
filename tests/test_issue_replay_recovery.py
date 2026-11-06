"""Recovery requires explicit choices, unchanged history and complete copy validation."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib import store

FIXTURES = Path(__file__).parent / 'fixtures/issue-replay-upgrade'

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.tmp) / 'control é東京'
        self.case = self.seed('v0.3.17-proof.json')

    def seed(self, name):
        case = json.loads((FIXTURES / name).read_text())
        (self.root / 'events').mkdir(parents=True, exist_ok=True)
        for p in (self.root / 'events').glob('*.json'): p.unlink()
        for event in case['events']:
            (self.root / 'events' / f"{event['sequence']:08d}.json").write_text(json.dumps(event))
        return case

    def api(self):
        path = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/workflow_lib/issue_replay_recovery.py'
        self.assertTrue(path.exists(), 'explicit replay recovery implementation missing')
        from workflow_lib import issue_replay_recovery
        return issue_replay_recovery

    def request(self, choice='legacy'):
        inspected = self.api().inspect_replay_recovery(self.root)
        return {'inspection': inspected['binding'],
            'selections': [{'event_digest': e['event_digest'], 'choice': choice} for e in inspected['unresolved']],
            'actor_id': 'fixture-owner', 'operation_id': 'recover-one', 'confirmed': True,
            'provenance': {'kind': 'user-message', 'ref': 'fixture-confirmation'}}

    def recover(self, choice='legacy'):
        req = self.request(choice)
        validation = self.api().validate_replay_recovery(self.root, req)
        return self.api().apply_replay_recovery(self.root, {**req, 'validation': validation})

    def event_bytes(self):
        return {p.name: p.read_bytes() for p in (self.root / 'events').glob('*.json')}

    def test_unstamped_start_requires_choice_even_without_proofs(self):
        self.seed('v0.3.18-start.json')
        with self.assertRaises(store.WorkflowError) as caught: store.read_state(self.root)
        self.assertEqual(caught.exception.code, 'ISSUE_POLICY_SELECTION_REQUIRED')

    def test_recovery_inspection_works_before_materialization(self):
        before = self.event_bytes()
        result = self.api().inspect_replay_recovery(self.root)
        self.assertEqual(len(result['unresolved']), 1)
        self.assertNotIn('choice', result['unresolved'][0])
        self.assertEqual(before, self.event_bytes())
        self.assertFalse((self.root / 'replay-recovery').exists())

    def test_legacy_choice_replays_old_red_proof(self):
        before = self.event_bytes(); self.recover()
        result = store.read_state(self.root)
        self.assertEqual(result['data'], self.case['expected']['data'])
        self.assertEqual(result['operations'], self.case['expected']['operations'])
        self.assertEqual(before, self.event_bytes())

    def test_v0318_choice_keeps_both_policies(self):
        case = self.seed('v0.3.18-question.json'); self.recover('v0.3.18')
        self.assertEqual(store.read_state(self.root)['data'], case['expected']['data'])

    def test_wrong_choice_cannot_hide_modern_records(self):
        self.seed('v0.3.18-question.json')
        with self.assertRaises(store.WorkflowError): self.recover('legacy')
        self.assertFalse((self.root / 'replay-recovery').exists())

    def test_unknown_or_partial_choices_reject(self):
        for entries in ([], [{'event_digest': 'a'*64, 'choice': 'legacy'}]):
            req = self.request(); req['selections'] = entries
            with self.assertRaises(store.WorkflowError): self.api().validate_replay_recovery(self.root, req)
        req = self.request('guess')
        with self.assertRaises(store.WorkflowError): self.api().validate_replay_recovery(self.root, req)
        req = self.request(); req['confirmed'] = False
        with self.assertRaises(store.WorkflowError): self.api().validate_replay_recovery(self.root, req)

    def test_changed_prefix_or_head_rejects_apply(self):
        req = self.request(); receipt = self.api().validate_replay_recovery(self.root, req)
        path = self.root / 'events/00000001.json'; path.write_text(path.read_text() + ' ')
        with self.assertRaises(store.WorkflowError): self.api().apply_replay_recovery(self.root, {**req, 'validation': receipt})
        self.assertFalse((self.root / 'replay-recovery').exists())

    def test_failed_copy_validation_does_not_publish(self):
        req = self.request('v0.3.18')
        with self.assertRaises(store.WorkflowError): self.api().validate_replay_recovery(self.root, req)
        self.assertFalse((self.root / 'replay-recovery').exists())

    def test_identical_retry_returns_original_receipt(self):
        req = self.request(); receipt = self.api().validate_replay_recovery(self.root, req)
        applied = {**req, 'validation': receipt}
        first = self.api().apply_replay_recovery(self.root, applied)
        second = self.api().apply_replay_recovery(self.root, applied)
        self.assertTrue(second['replayed'])
        self.assertEqual(first['validation'], second['validation'])

    def test_conflicting_identity_cannot_overwrite(self):
        self.recover()
        req = self.request(); req['selections'] = []
        with self.assertRaises(store.WorkflowError): self.api().apply_replay_recovery(self.root, {**req, 'validation': {}})

    def test_replay_does_not_observe_live_sources(self):
        self.recover()
        with patch('subprocess.run', side_effect=AssertionError('live process')):
            self.assertEqual(store.read_state(self.root)['data'], self.case['expected']['data'])

    def test_interrupted_publication_is_not_success(self):
        req = self.request(); receipt = self.api().validate_replay_recovery(self.root, req)
        with patch('workflow_lib.issue_replay_recovery.publish_manifest', side_effect=OSError('owned interruption')):
            with self.assertRaises(OSError): self.api().apply_replay_recovery(self.root, {**req, 'validation': receipt})
        with self.assertRaises(store.WorkflowError): store.read_state(self.root)

    def test_recovery_path_symlink_rejects(self):
        outside = Path(self.tmp) / 'outside'; outside.mkdir()
        (self.root / 'replay-recovery').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(store.WorkflowError): self.api().inspect_replay_recovery(self.root)

    def test_recovery_operation_reserves_logical_namespace(self):
        self.recover()
        with self.assertRaises(store.WorkflowError) as caught:
            store.transact(self.root,6,'recover-one',{'kind':'note','payload':{}})
        self.assertEqual(caught.exception.code,'OPERATION_CONFLICT')

    def test_physical_operation_cannot_be_reused_for_recovery(self):
        from workflow_lib.storage_audit import write_record, paths
        req=self.request()
        request={'fixture':'owned'}
        from workflow_lib.document_units import digest
        write_record(paths(self.root,'recover-one')[0],{'audit_version':1,'operation_id':'recover-one',
            'actor_id':'fixture-owner','kind':'backup','request':request,
            'request_hash':digest({'kind':'backup','request':request,'actor_id':'fixture-owner'}),
            'result':{'completed':True}})
        with self.assertRaises(store.WorkflowError) as caught:
            self.api().validate_replay_recovery(self.root,req)
        self.assertEqual(caught.exception.code,'OPERATION_CONFLICT')

    def test_malformed_manifest_is_a_typed_error(self):
        from workflow_lib.document_units import digest
        self.recover();manifest=next((self.root/'replay-recovery').glob('*.json'))
        original=json.loads(manifest.read_text())
        for body in ([], {'schema_version':True,'request':original['body']['request'],'validation':original['body']['validation']}):
            manifest.write_text(json.dumps({'body':body,'sha256':digest(body)}))
            with self.assertRaises(store.WorkflowError): self.api().inspect_replay_recovery(self.root)

    def test_public_cli_inspects_validates_applies_and_retries(self):
        import subprocess
        entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        req=self.request();input_=Path(self.tmp)/'request.json'
        def cli(action,data=None,expected=0):
            args=[sys.executable,str(entry),'issues','replay-recovery-'+action,'--root',str(self.root)]
            if data is not None:
                input_.write_text(json.dumps(data));args+=['--input',str(input_),'--operation-id','recover-one']
            result=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(len(cli('inspect')['unresolved']),1)
        receipt=cli('validate',req)
        applied={**req,'validation':receipt}
        self.assertTrue(cli('apply',applied)['completed'])
        self.assertTrue(cli('apply',applied)['replayed'])
        self.root=Path(self.tmp)/'modern-control'
        self.seed('v0.3.18-question.json')
        wrong=self.request('legacy')
        self.assertEqual(cli('validate',wrong,expected=2)['error'],'ISSUE_RECOVERY_INVALID')
        req=self.request('v0.3.18');receipt=cli('validate',req)
        self.assertTrue(cli('apply',{**req,'validation':receipt})['completed'])


    def test_explicit_adoption_is_not_retroactive_recovery(self):
        self.recover()
        original=store.read_state(self.root)
        run=next(iter(original['data']['runs'].values()))
        self.assertNotIn('enforcement',run)
        store.transact(self.root,6,'abandon',{'kind':'run.attempt.abandoned',
            'payload':{'run_id':run['id'],'token':'owned-token'}})
        current=store.read_state(self.root)['data']['runs'][run['id']]
        store.transact(self.root,7,'adopt',{'kind':'domain.enforcement.adopt','payload':{'request':{
            'run_id':run['id'],'authorization':{'approved':True,'actor_id':'fixture-owner',
                'run_id':run['id'],'state_version':current['state_version']}}}})
        updated=store.read_state(self.root)['data']['runs'][run['id']]
        self.assertEqual(updated['enforcement']['policy_version'],1)
        self.assertFalse(next(iter(updated['verification_proofs'].values()))['passed'])
