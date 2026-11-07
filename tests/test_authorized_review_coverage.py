"""Synthetic native lineage for pure admission; no fixture claims live execution."""
import copy
import unittest
import test_review_dispatch as fixtures
from test_review_authorizations import selection
from workflow_lib import review_authorizations as auth
from workflow_lib.store import WorkflowError


class AuthorizedReviewCoverageTests(unittest.TestCase):
    def complete(self, role):
        import test_adversarial_reviews as adversarial_fixtures
        run, package, reports = adversarial_fixtures.AdversarialReviewTests().complete(role)
        proposal = auth.propose_authorization(run, {**selection(), 'model': 'fixture-eligible'})
        run = auth.record_authorization(run, {'proposal': proposal, 'confirmed_hash': proposal['proposal_hash'],
            'actor_id': 'fixture-human', 'provenance': {'kind': 'user-message', 'ref': 'synthetic:full-coverage'}})
        run['native_invocations'] = {}
        for key, receipt in run['model_receipts'].items():
            receipt.update(mode='strict', capability_validated=False, validation_ref=None,
                suitability='unvalidated', review_authorization_hash=proposal['proposal_hash'],
                eligibility={'schema_version': 1, 'basis': auth.BASIS, 'authorization_hash': proposal['proposal_hash']},
                transport_completed=True, output_ref='synthetic:raw-output-' + key)
            run['native_invocations'][key] = {'status': 'completed', 'scope': copy.deepcopy(receipt['scope']),
                'decision': copy.deepcopy(receipt), 'result': {name: copy.deepcopy(receipt.get(name)) for name in
                    ('observed', 'observation_source', 'invocation_ref', 'output_ref', 'review_input_validation', 'review_report_hash')}}
        return run, package, reports

    def fixture(self):
        fixture = fixtures.ReviewDispatchTests()
        run, package, review = fixture.receipt_fixture()
        proposal = auth.propose_authorization(run, {**selection(), 'model': 'small-sounding-preferred'})
        run = auth.record_authorization(run, {'proposal': proposal, 'confirmed_hash': proposal['proposal_hash'],
            'actor_id': 'fixture-human', 'provenance': {'kind': 'user-message', 'ref': 'synthetic:coverage-consent'}})
        receipt = run['model_receipts']['actual-call']
        receipt.update(mode='strict', capability_validated=False, validation_ref=None,
            suitability='unvalidated', review_authorization_hash=proposal['proposal_hash'],
            eligibility={'schema_version': 1, 'basis': auth.BASIS, 'authorization_hash': proposal['proposal_hash']},
            transport_completed=True, output_ref='fixture:raw-structured-output', model_revision=None)
        run['native_invocations'] = {'actual-call': {'status': 'completed', 'scope': copy.deepcopy(receipt['scope']),
            'decision': copy.deepcopy(receipt), 'result': {key: copy.deepcopy(receipt.get(key)) for key in
                ('observed', 'observation_source', 'invocation_ref', 'output_ref', 'review_input_validation', 'review_report_hash')}}}
        return run, package, review

    def test_current_observed_basis_is_accepted_without_claiming_validation(self):
        from workflow_lib.review_dispatch import validate_review_model
        run, package, review = self.fixture()
        result = validate_review_model(run, package, review)
        self.assertEqual(result['status'], 'allow')
        self.assertEqual(result['suitability'], 'unvalidated')
        self.assertFalse(run['model_receipts']['actual-call']['capability_validated'])

    def test_revoke_after_execution_or_forged_lineage_blocks_admission(self):
        from workflow_lib.review_dispatch import validate_review_model
        for bad in ('revoked', 'lineage', 'validated-flag', 'unknown-basis', 'provider', 'actor', 'scope', 'preferences'):
            run, package, review = self.fixture()
            receipt = run['model_receipts']['actual-call']
            if bad == 'revoked': run['review_model_revocations'] = {receipt['review_authorization_hash']: {'reason': 'synthetic:revoke'}}
            if bad == 'lineage': run['native_invocations'] = {}
            if bad == 'validated-flag': receipt['capability_validated'] = True
            if bad == 'unknown-basis': receipt['eligibility']['basis'] = 'invented'
            if bad == 'provider': receipt['observed']['provider'] = 'other'
            if bad == 'actor': review['actor_id'] = 'implementer'; run['actors'] = {'implementer': 'implementer'}
            if bad == 'scope': package['package_hash'] = 'different'
            if bad == 'preferences': run['model_overrides'] = [{'allowed_models': []}]
            with self.subTest(bad=bad), self.assertRaises(WorkflowError):
                validate_review_model(run, package, review)

    def test_summary_discloses_unvalidated_suitability_and_unknown_revision(self):
        from workflow_lib.review_summary import summarize_review
        from workflow_lib.reporting import export_report
        run, package, review = self.fixture()
        report = summarize_review(run)
        details = report['reviewer_models'][0]
        self.assertEqual(details['eligibility_basis'], auth.BASIS)
        self.assertEqual(details['suitability'], 'unvalidated')
        self.assertIsNone(details['model_revision'])
        self.assertEqual(details['review_authorization_hash'], run['model_receipts']['actual-call']['review_authorization_hash'])
        for format in ('json', 'markdown', 'csv'):
            self.assertIn('unvalidated', export_report(report, format))

    def test_fresh_reauthorization_cannot_resurrect_old_invocation(self):
        run, package, review = self.fixture()
        receipt = run['model_receipts']['actual-call']
        key = receipt['review_authorization_hash']
        run = auth.revoke_authorization(run, {'authorization_hash': key, 'actor_id': 'fixture-human', 'reason': 'Stop',
            'provenance': {'kind': 'user-message', 'ref': 'synthetic:revoke'}})
        proposal = auth.propose_authorization(run, {**selection(), 'model': 'small-sounding-preferred'})
        self.assertNotEqual(proposal['proposal_hash'], key)
        run = auth.record_authorization(run, {'proposal': proposal, 'confirmed_hash': proposal['proposal_hash'],
            'actor_id': 'fixture-human', 'provenance': {'kind': 'user-message', 'ref': 'synthetic:fresh-consent'}})
        with self.assertRaises(WorkflowError):
            auth.validate_authorized_receipt(run, receipt, {'role': 'item', 'perspective': 'security'})

    def test_acceptance_without_actual_authorized_receipt_cannot_fall_through(self):
        from workflow_lib.adversarial_reviews import adversarial_bindings, validate_acceptance_review
        run, _, _ = self.fixture()
        bindings = adversarial_bindings(run, {'role': 'acceptance'})
        package = {'role': 'acceptance', 'package_hash': 'acceptance-fixture',
                   'adversarial_bindings': bindings, 'source_identity': run['source_identity']}
        review = {'role': 'acceptance', 'verdict': 'pass', 'adversarial_bindings': bindings,
                  'actor_id': 'independent-acceptance', 'package_hash': package['package_hash']}
        with self.assertRaises(WorkflowError):
            validate_acceptance_review(run, package, review)

    def test_revocation_invalidates_item_branch_pr_coverage_and_original_reuse(self):
        from workflow_lib.adversarial_reviews import review_coverage
        from workflow_lib.review_summary import review_reuse
        for role in ('item', 'branch', 'pr'):
            with self.subTest(role=role):
                run, package, reports = self.complete(role)
                item = 'W1' if role == 'item' else None
                self.assertTrue(review_coverage(run, role, item)['complete'])
                if role != 'pr': self.assertTrue(review_reuse(run, package, reports[0])['reusable'])
                key = next(iter(run['review_model_authorizations']))
                run['review_model_revocations'] = {key: {'reason': 'synthetic:revoke'}}
                before = copy.deepcopy(run['reviews'])
                self.assertFalse(review_coverage(run, role, item)['complete'])
                self.assertFalse(review_reuse(run, package, reports[0])['reusable'])
                self.assertEqual(run['reviews'], before)

    def test_authorization_cannot_replace_test_oracles_or_independence(self):
        from workflow_lib.adversarial_reviews import review_coverage
        for bad in ('oracle', 'self-review', 'shared-invocation'):
            run, _, reports = self.complete('item')
            reports = run['reviews']['item']
            if bad == 'oracle': reports[1]['test_quality'] = {}
            if bad == 'self-review': reports[0]['actor_id'] = 'author'
            if bad == 'shared-invocation': reports[2]['model_invocation_id'] = reports[0]['model_invocation_id']
            if bad == 'oracle':
                from workflow_lib.adversarial_reviews import semantic_report_hash
                report_hash = semantic_report_hash(reports[1])
                run['model_receipts'][reports[1]['model_invocation_id']]['review_report_hash'] = report_hash
                run['native_invocations'][reports[1]['model_invocation_id']]['result']['review_report_hash'] = report_hash
            with self.subTest(bad=bad):
                self.assertFalse(review_coverage(run, 'item', 'W1')['complete'])
