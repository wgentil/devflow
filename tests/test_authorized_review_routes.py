"""Authorized routing uses synthetic capabilities, never live-validation claims."""
import copy
import unittest
from test_review_authorizations import approved, subject


class AuthorizedReviewRouteTests(unittest.TestCase):
    def setUp(self):
        from workflow_lib import review_authorizations as api
        self.api = api
        self.subject, self.key, _ = approved(api)
        self.policy = {'schema_version': 3, 'version': '3', 'profiles': {'deep-reasoning': {'effort': 'high'}},
                       'hosts': {'codex': {}}}
        self.cap = {'configure': True, 'observe': True, 'models': ['fixture-model'], 'efforts': ['high'],
                    'model_efforts': {'fixture-model': ['high']}}
        self.discovery = {'models': {'fixture-model': 'available'}, 'model_revisions': {}, 'host_version': '1.2.3'}
        self.request = {'host': 'codex', 'stage': 'review', 'mode': 'strict'}
        self.scope = {'role': 'item', 'perspective': 'code'}

    def route(self, **kwargs):
        return self.api.resolve_authorized_review(self.subject, kwargs.get('request', self.request),
            kwargs.get('scope', self.scope), kwargs.get('capabilities', self.cap),
            kwargs.get('discovery', self.discovery), kwargs.get('prices'), kwargs.get('key', self.key), self.policy)

    def test_empty_mappings_block_without_explicit_authorization(self):
        from workflow_lib.review_dispatch import select_review_route
        self.assertEqual(select_review_route(self.policy, {**self.request, 'perspective': 'code'}, self.cap, self.discovery, None)['status'], 'block')
        self.assertEqual(self.route(key=None)['status'], 'block')

    def test_named_authorization_selects_only_observable_high_model(self):
        result = self.route()
        self.assertEqual(result['status'], 'allow', result)
        self.assertEqual(result['resolved'], {'provider': 'openai', 'model': 'fixture-model', 'effort': 'high'})
        self.assertEqual(result['profile'], 'deep-reasoning')
        self.assertFalse(result['capability_validated'])
        self.assertEqual(result['suitability'], 'unvalidated')
        self.assertEqual(result['review_authorization_hash'], self.key)
        self.assertEqual(result['eligibility']['basis'], 'human-authorized-observed/v1')
        self.assertIsNone(result['model_revision'])
        self.assertEqual(self.route(request={**self.request, 'stage': 'acceptance'}, scope={'role': 'acceptance'})['status'], 'allow')
        self.assertEqual(self.subject['effect_policy'], {'max_invocations': 8})

    def test_existing_restrictions_remain_effective(self):
        for restrictions in ({'allowed_models': []}, {'pin': 'other'}, {'effort': 'low'},
                             {'profile': 'fast-analysis'}, {'max_cost': 1},
                             {'max_cost': 0, 'estimated_tokens': {'input': 100, 'output': 100}}):
            with self.subTest(restrictions=restrictions):
                self.assertEqual(self.route(request={**self.request, **restrictions})['status'], 'block')
        for cap in ({**self.cap, 'configure': False}, {**self.cap, 'observe': False},
                    {**self.cap, 'model_efforts': {}}, {**self.cap, 'models': []}):
            with self.subTest(cap=cap):
                self.assertEqual(self.route(capabilities=cap)['status'], 'block')
        self.assertEqual(self.route(discovery={'models': {'fixture-model': 'unknown'}})['status'], 'block')
        prices = {'version': 'fixture-price', 'source': 'synthetic:price', 'rates': {'openai/fixture-model': {'input': 1, 'output': 1}}}
        request = {**self.request, 'max_cost': .00001, 'estimated_tokens': {'input': 100, 'output': 100}}
        self.assertEqual(self.route(request=request, prices=prices)['status'], 'block')

    def test_authorized_route_cannot_select_lightweight_or_repair(self):
        self.assertEqual(self.route(request={**self.request, 'assessment': {'lightweight': True}})['resolved']['effort'], 'high')
        for stage in ('implementation', 'debugging', 'delivery'):
            self.assertEqual(self.route(request={**self.request, 'stage': stage})['status'], 'block')
        for role in ('session', 'repair', 'implementer'):
            self.assertEqual(self.route(scope={'role': role, 'perspective': 'code'})['status'], 'block')
        for invalid in (None, [], 'bad'):
            self.assertEqual(self.route(request=invalid)['status'], 'block')
