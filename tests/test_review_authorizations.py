"""Synthetic human consent records; no fixture is a live provider observation."""
import copy
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.document_units import digest
from workflow_lib.review_policy import new_review_policy
from workflow_lib.store import WorkflowError


def subject():
    return {'id': 'run-fixture', 'status': 'active', 'plan': {'spec_hash': 'spec-fixture'},
            'review_policy': new_review_policy(), 'actors': {'implementer': 'implementer'},
            'model_overrides': [], 'reviews': {}, 'effect_policy': {'max_invocations': 8}}


def selection():
    return {'host': 'codex', 'provider': 'openai', 'model': 'fixture-model',
            'profile': 'deep-reasoning', 'effort': 'high',
            'roles': ['item', 'branch', 'acceptance', 'pr'],
            'perspectives': ['code', 'test', 'architecture', 'security']}


def approved(api, original=None):
    original = original or subject()
    proposal = api.propose_authorization(original, selection())
    record = {'proposal': proposal, 'confirmed_hash': proposal['proposal_hash'],
              'actor_id': 'fixture-human',
              'provenance': {'kind': 'user-message', 'ref': 'synthetic:human-consent'}}
    return api.record_authorization(original, record), proposal['proposal_hash'], record


class ReviewAuthorizationTests(unittest.TestCase):
    def api(self):
        return importlib.import_module('workflow_lib.review_authorizations')

    def test_exact_human_approval_and_scope_are_required(self):
        api = self.api()
        original = subject()
        proposal = api.propose_authorization(original, selection())
        self.assertEqual(proposal['run_id'], 'run-fixture')
        self.assertEqual(proposal['spec_hash'], 'spec-fixture')
        self.assertEqual(proposal['review_policy_hash'], digest(original['review_policy']))
        self.assertEqual(proposal['suitability'], 'unvalidated')
        self.assertEqual(proposal['proposal_hash'], digest({k: v for k, v in proposal.items() if k != 'proposal_hash'}))
        updated, identifier, record = approved(api, original)
        scope = {'role': 'item', 'perspective': 'test', 'host': 'codex', 'model': 'fixture-model',
                 'provider': 'openai', 'effort': 'high', 'profile': 'deep-reasoning'}
        self.assertEqual(api.current_authorization(updated, identifier, scope)['proposal'], proposal)
        self.assertNotIn('review_model_authorizations', original)
        for field, value in [('confirmed_hash', 'wrong'), ('actor_id', 'implementer'),
                             ('provenance', {}), ('extra', True)]:
            with self.subTest(field=field), self.assertRaises(WorkflowError):
                api.record_authorization(original, {**record, field: value})
        for field, value in [('id', 'other-run'), ('plan', {'spec_hash': 'other-spec'}),
                             ('status', 'delivered'), ('review_policy', {**original['review_policy'], 'revision': 2})]:
            with self.subTest(field=field), self.assertRaises(WorkflowError):
                api.current_authorization({**updated, field: value}, identifier, scope)
        for field, value in [('host', 'claude'), ('model', 'other-model'), ('provider', 'other'),
                             ('effort', 'low'), ('profile', 'fast-analysis'), ('role', 'repair'),
                             ('perspective', 'unknown')]:
            with self.subTest(scope=field), self.assertRaises(WorkflowError):
                api.current_authorization(updated, identifier, {**scope, field: value})

    def test_idempotency_revocation_and_history(self):
        api = self.api()
        updated, identifier, record = approved(api)
        self.assertEqual(api.record_authorization(updated, record), updated)
        revoke = {'authorization_hash': identifier, 'actor_id': 'fixture-human', 'reason': 'Stop using this model.',
                  'provenance': {'kind': 'user-message', 'ref': 'synthetic:revoke'}}
        revoked = api.revoke_authorization(updated, revoke)
        self.assertEqual(api.revoke_authorization(revoked, revoke), revoked)
        self.assertEqual(revoked['review_model_authorizations'][identifier], updated['review_model_authorizations'][identifier])
        with self.assertRaises(WorkflowError):
            api.current_authorization(revoked, identifier, {'role': 'acceptance'})
        with self.assertRaises(WorkflowError):
            api.record_authorization(revoked, record)
        with self.assertRaises(WorkflowError):
            api.revoke_authorization(updated, {**revoke, 'actor_id': 'implementer'})

    def test_old_subject_and_standalone_have_no_implicit_consent(self):
        api = self.api()
        with self.assertRaises(WorkflowError):
            api.current_authorization(subject(), 'missing', {'role': 'item', 'perspective': 'code'})
        for value in [None, [], 'invalid', {**selection(), 'effort': 'low'},
                      {**selection(), 'host': []}, {**selection(), 'model': {}},
                      {**selection(), 'roles': ['repair']}, {**selection(), 'perspectives': ['invented']},
                      {**selection(), 'roles': []}, {**selection(), 'schema_version': 99}]:
            with self.subTest(value=value), self.assertRaises(WorkflowError):
                api.propose_authorization(subject(), value)
        with self.assertRaises(WorkflowError):
            api.propose_authorization({**subject(), 'review_contract_hash': 'session-only'}, selection())

    def test_source_changes_do_not_expand_or_expire_consent(self):
        api = self.api()
        updated, identifier, _ = approved(api)
        updated['source_identity'] = 'new-source'
        updated['model_overrides'] = [{'allowed_models': []}]
        self.assertEqual(api.current_authorization(updated, identifier, {'role': 'acceptance'})['proposal']['selection'], selection())
        tampered = copy.deepcopy(updated)
        tampered['review_model_authorizations'][identifier]['proposal']['selection']['effort'] = 'low'
        with self.assertRaises(WorkflowError):
            api.current_authorization(tampered, identifier, {'role': 'acceptance'})

    def test_public_cli_both_stores_preserves_history_and_operation_identity(self):
        from workflow_lib import store
        from control_store_fixtures import legacy_root
        entry = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'
        for legacy in (True, False):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                root = legacy_root(base / 'control') if legacy else base / 'control'
                store.transact(root, 0, 'fixture-seed', {'kind': 'fixture', 'payload': {'runs': {'run-fixture': subject()}}})
                def cli(command, record=None, operation=None, expected=0):
                    args = [sys.executable, '-B', str(entry), 'review', command, '--root', str(root), '--run-id', 'run-fixture']
                    if record is not None:
                        path = base / 'input.json'; path.write_text(json.dumps(record))
                        args += ['--input', str(path)]
                    if operation:
                        args += ['--operation-id', operation]
                    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                    return json.loads(result.stdout)
                before = store.read_state(root)
                proposal = cli('model-proposal', selection())
                self.assertEqual(store.read_state(root), before)
                consent = {'proposal': proposal, 'confirmed_hash': proposal['proposal_hash'], 'actor_id': 'fixture-human',
                           'provenance': {'kind': 'user-message', 'ref': 'synthetic:cli-consent'}}
                cli('authorize-model', consent, 'authorize')
                self.assertTrue(cli('authorize-model', consent, 'authorize')['replayed'])
                self.assertEqual(cli('authorize-model', {**consent, 'actor_id': 'another-human'}, 'authorize', 2)['error'], 'OPERATION_CONFLICT')
                snapshot = cli('model-authorizations')
                self.assertIn(proposal['proposal_hash'], snapshot['authorizations'])
                cli('revoke-model', {'authorization_hash': proposal['proposal_hash'], 'actor_id': 'fixture-human',
                                    'reason': 'Stop', 'provenance': {'kind': 'user-message', 'ref': 'synthetic:cli-revoke'}}, 'revoke')
                self.assertIn(proposal['proposal_hash'], cli('model-authorizations')['revocations'])
                self.assertEqual(store.read_state(root)['version'], before['version'] + 2)
