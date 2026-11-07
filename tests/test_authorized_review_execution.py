"""Actual native coordinator execution against an explicitly synthetic backend."""
import copy
import json
import itertools
import unittest
from unittest.mock import patch
import test_review_dispatch as fixtures
from test_review_authorizations import selection
from workflow_lib import store, review_authorizations as auth


class AuthorizedReviewExecutionTests(unittest.TestCase):
    def fixture(self, acceptance=False):
        fixture = fixtures.ReviewDispatchTests()
        self.addCleanup(fixture.doCleanups)
        root, repo, request, backend = fixture.native_fixture()
        state = store.read_state(root)
        run = state['data']['runs']['run']
        chosen = {**selection(), 'model': 'small-sounding-preferred'}
        proposal = auth.propose_authorization(run, chosen)
        run = auth.record_authorization(run, {'proposal': proposal, 'confirmed_hash': proposal['proposal_hash'],
            'actor_id': 'fixture-human', 'provenance': {'kind': 'user-message', 'ref': 'synthetic:execution-consent'}})
        state['data']['runs']['run'] = run
        if acceptance:
            binding = state['data']['host_bindings']['review']
            binding.update(role='acceptance-reviewer')
            binding.pop('perspective', None)
            request.pop('perspective', None)
            package = run['review_packages'][binding['package_hash']]
            package['role'] = 'acceptance'
            # Deliberately recompute a real acceptance package; do not assert a changed package hash.
            from workflow_lib.reviews import prepare_review
            head = package['repositories']['repo']['head']
            package = prepare_review(run, 'acceptance', {'repo': {'location': str(repo), 'base': head, 'head': head}})
            binding['package_hash'] = package['package_hash']
            run['review_packages'] = {package['package_hash']: package}
        store.transact(root, state['version'], 'consent-fixture', {'kind': 'fixture', 'payload': state['data']})
        request['review_authorization_hash'] = proposal['proposal_hash']
        request['context_max_bytes'] = 32768
        policy = fixture.policy(); policy['hosts'] = {'codex': {}}
        policy['stages']['acceptance'] = 'deep-reasoning'
        return root, repo, request, backend, policy

    def call(self, root, request, backend, policy):
        from workflow_lib.review_dispatch import dispatch_workflow_review
        with patch('workflow_lib.native_runtime.policy', return_value=policy), patch('workflow_lib.native_runtime.CodexBackend', return_value=backend):
            return dispatch_workflow_review(root, request, 'authorized-execution')

    def revoke(self, root, request):
        state = store.read_state(root)
        record = {'authorization_hash': request['review_authorization_hash'], 'actor_id': 'fixture-human',
                  'reason': 'Stop', 'provenance': {'kind': 'user-message', 'ref': 'synthetic:execution-revoke'}}
        store.transact(root, state['version'], 'revoke-during-execution', {'kind': 'domain.enforcement.review-model-revoke',
            'payload': {'request': {'run_id': 'run', 'record': record}}})

    def blocked_call(self, root, request, backend, policy):
        try:
            return self.call(root, request, backend, policy)
        except store.WorkflowError as exc:
            return {'status': 'block', 'reason_code': exc.code}

    def test_real_coordinator_retains_authorization_and_exact_retry(self):
        root, repo, request, backend, policy = self.fixture()
        result = self.call(root, request, backend, policy)
        self.assertEqual(result['status'], 'allow', result)
        self.assertFalse(result['capability_validated'])
        self.assertEqual(result['review_authorization_hash'], request['review_authorization_hash'])
        self.assertEqual(result['observed']['effort'], 'high')
        self.assertEqual(backend.configure.call_args.args[2], 'read-only')
        run = store.read_state(root)['data']['runs']['run']
        self.assertEqual(auth.validate_authorized_receipt(run, result, {'role': 'branch', 'perspective': 'security'})['status'], 'allow')
        self.assertTrue(self.call(root, request, backend, policy)['replayed'])
        backend.invoke.assert_called_once()
        for corruption in ('lineage', 'scope', 'basis'):
            forged = copy.deepcopy(run)
            receipt = copy.deepcopy(result)
            scope = {'role': 'branch', 'perspective': 'security'}
            if corruption == 'lineage': forged['native_invocations'] = {}
            if corruption == 'scope': scope['role'] = 'item'
            if corruption == 'basis': receipt['eligibility']['basis'] = 'invented'
            with self.subTest(corruption=corruption), self.assertRaises(store.WorkflowError):
                auth.validate_authorized_receipt(forged, receipt, scope)

    def test_real_transport_boundaries_recheck_consent(self):
        for boundary in ('discover', 'configure', 'invoke'):
            with self.subTest(boundary=boundary):
                root, repo, request, backend, policy = self.fixture()
                method = getattr(backend, boundary)
                original = copy.deepcopy(method.return_value)
                def change(*args, **kwargs):
                    self.revoke(root, request)
                    return original
                method.side_effect = change
                result = self.blocked_call(root, request, backend, policy)
                self.assertEqual(result['status'], 'block', result)
                if boundary != 'invoke':
                    backend.invoke.assert_not_called()
                else:
                    self.assertTrue(result['transport_completed'])
                    self.assertTrue(result['invocation_ref'])

    def test_substitution_missing_observation_and_portable_forgery_block(self):
        for boundary in ('configure', 'invoke'):
            for field in ('provider', 'model', 'effort', 'observation_source'):
                with self.subTest(boundary=boundary, field=field):
                    root, repo, request, backend, policy = self.fixture()
                    value = getattr(backend, boundary).return_value
                    if field == 'observation_source': value[field] = 'claimed-by-caller'
                    else: value['observed'][field] = 'substituted'
                    result = self.blocked_call(root, request, backend, policy)
                    self.assertEqual(result['status'], 'block', result)
                    if boundary == 'configure': backend.invoke.assert_not_called()

    def test_acceptance_uses_existing_acceptance_stage(self):
        root, repo, request, backend, policy = self.fixture(acceptance=True)
        result = self.call(root, request, backend, policy)
        self.assertEqual(result['status'], 'allow', result)
        self.assertEqual(result['stage'], 'acceptance')
        self.assertNotIn('perspective', result['scope'])
        self.assertFalse(result['capability_validated'])

    def test_released_route_can_replace_revoked_acceptance_authorization(self):
        root, repo, request, backend, policy = self.fixture(acceptance=True)
        self.revoke(root, request)
        request.pop('review_authorization_hash')
        policy = fixtures.ReviewDispatchTests().policy()
        policy['stages']['acceptance'] = 'deep-reasoning'
        result = self.call(root, request, backend, policy)
        self.assertEqual(result['status'], 'allow', result)
        self.assertTrue(result['capability_validated'])
        self.assertNotIn('review_authorization_hash', result)
        self.assertEqual(result['review_report_kind'], 'observed-acceptance-output/v1')
        auth.validate_acceptance_receipt(store.read_state(root)['data']['runs']['run'], result)

    def test_context_budget_is_explicit_before_backend_or_reservation(self):
        for invalid in ('omitted', None, 0, -1, True, '20000'):
            root, repo, request, backend, policy = self.fixture()
            if invalid == 'omitted': request.pop('context_max_bytes')
            else: request['context_max_bytes'] = invalid
            result = self.blocked_call(root, request, backend, policy)
            self.assertEqual(result['status'], 'block', result)
            backend.invoke.assert_not_called(); backend.discover.assert_not_called()
            self.assertFalse(store.read_state(root)['data']['runs']['run'].get('effects'))

    def test_later_reviewer_attachment_cannot_use_consent_actor(self):
        from workflow_lib.hosts import apply_host_event
        from test_hosts import attachment
        root, repo, request, backend, policy = self.fixture()
        data = store.read_state(root)['data']
        with self.assertRaises(store.WorkflowError):
            apply_host_event(data, 'attach', attachment(project=str(repo), binding_id='other-review',
                session_id='other-review-session', actor_id='fixture-human', role='branch-reviewer',
                perspective='security', package_hash=data['host_bindings']['review']['package_hash']))

    def test_policy_and_model_preference_changes_before_invoke_block(self):
        for change, boundary in itertools.product(('policy', 'preferences'), ('discover', 'configure', 'invoke')):
            root, repo, request, backend, policy = self.fixture()
            original = copy.deepcopy(getattr(backend, boundary).return_value)
            def alter(*args):
                state = store.read_state(root); run = state['data']['runs']['run']
                if change == 'policy': run['review_policy']['revision'] += 1
                else: run['model_overrides'] = [{'allowed_models': []}]
                store.transact(root, state['version'], 'synthetic-concurrent-policy-change', {'kind': 'fixture', 'payload': state['data']})
                return original
            getattr(backend, boundary).side_effect = alter
            result = self.blocked_call(root, request, backend, policy)
            self.assertEqual(result['status'], 'block', result)
            if boundary != 'invoke': backend.invoke.assert_not_called()
            else: self.assertTrue(result['transport_completed'])
