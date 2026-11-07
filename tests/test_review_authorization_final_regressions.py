"""Independent expected acceptance and approval evidence; all receipts are synthetic."""
import copy
import unittest
from unittest.mock import patch
import test_authorized_review_coverage as fixtures
from workflow_lib import review_authorizations as auth
from workflow_lib.store import WorkflowError


class ReviewAuthorizationFinalRegressions(unittest.TestCase):
    def acceptance(self, validated=False):
        from workflow_lib.adversarial_reviews import adversarial_bindings, review_input_id, expected_review_input_validation
        run, _, _ = fixtures.AuthorizedReviewCoverageTests().fixture()
        bindings = adversarial_bindings(run, {'role': 'acceptance'})
        package = {'role': 'acceptance', 'package_hash': 'synthetic-acceptance', 'review_inputs': [],
                   'adversarial_bindings': bindings, 'source_identity': run['source_identity']}
        review = {'role': 'acceptance', 'verdict': 'pass', 'findings': [], 'review_id': 'acceptance-review',
                  'package_hash': package['package_hash'], 'adversarial_bindings': bindings,
                  'actor_id': 'independent', 'invocation_ref': 'fixture:actual-invocation', 'model_invocation_id': 'actual-call',
                  'reviewed_inputs': [], 'review_input_ref': review_input_id(package), 'requirements': [
                      {'id': 'R1', 'verdict': 'MET', 'citations': [{'repo_id': 'repo', 'path': 'source.py', 'line': 1}],
                       'rationale': 'Synthetic expected behavior.'}]}
        receipt = run['model_receipts']['actual-call']
        receipt['scope'] = {'role': 'acceptance-reviewer', 'actor_id': 'independent', 'package_hash': package['package_hash']}
        receipt['review_input_validation'] = {key: expected_review_input_validation(package) for key in ('before', 'after')}
        receipt['diagnostic'] = False
        receipt['review_report_kind'] = 'observed-acceptance-output/v1'
        receipt['review_report_hash'] = auth.acceptance_report_hash(review)
        if validated:
            receipt.update(capability_validated=True, validation_ref='synthetic:released-mapping')
            for field in ('review_authorization_hash', 'eligibility', 'suitability'):
                receipt.pop(field, None)
        run['native_invocations']['actual-call'] = {'status': 'completed', 'scope': copy.deepcopy(receipt['scope']),
            'decision': copy.deepcopy(receipt), 'result': {key: copy.deepcopy(receipt.get(key)) for key in
                ('observed', 'observation_source', 'invocation_ref', 'output_ref', 'review_input_validation', 'review_report_hash')}}
        run['reviews'] = {'acceptance': [review]}
        run['review_packages'] = {package['package_hash']: package}
        return run, package, review

    def test_authorized_acceptance_seals_requirements_and_rejects_inconsistent_pass(self):
        from workflow_lib.adversarial_reviews import validate_acceptance_review, semantic_report_hash
        run, package, review = self.acceptance()
        self.assertEqual(validate_acceptance_review(run, package, review)['status'], 'allow')
        altered = copy.deepcopy(review); altered['requirements'][0]['verdict'] = 'CANNOT VERIFY'
        self.assertEqual(semantic_report_hash(altered), semantic_report_hash(review), 'Historical report hashing must remain unchanged.')
        self.assertNotEqual(auth.acceptance_report_hash(altered), auth.acceptance_report_hash(review))
        with self.assertRaises(WorkflowError): validate_acceptance_review(run, package, altered)
        # Authentic output saying overall pass with an unverified requirement is not acceptance.
        receipt = run['model_receipts']['actual-call']; receipt['review_report_hash'] = auth.acceptance_report_hash(altered)
        run['native_invocations']['actual-call']['result']['review_report_hash'] = receipt['review_report_hash']
        with self.assertRaises(WorkflowError): validate_acceptance_review(run, package, altered)

    def test_authenticated_malformed_requirements_have_typed_diagnostics(self):
        from workflow_lib.adversarial_reviews import validate_acceptance_review
        run, package, review = self.acceptance()
        review['requirements'][0]['verdict'] = []
        receipt = run['model_receipts']['actual-call']
        receipt['review_report_hash'] = auth.acceptance_report_hash(review)
        run['native_invocations']['actual-call']['result']['review_report_hash'] = receipt['review_report_hash']
        with self.assertRaises(WorkflowError): validate_acceptance_review(run, package, review)

    def test_acceptance_payload_matches_current_output_and_revocation_blocks_readiness(self):
        from workflow_lib.gates import accept_requirements, _review_current
        run, package, review = self.acceptance()
        report = {'package_hash': package['package_hash'], 'requirements': copy.deepcopy(review['requirements'])}
        self.assertEqual(auth.validate_acceptance_payload(run, report)['review_id'], review['review_id'])
        altered = copy.deepcopy(report); altered['requirements'][0]['rationale'] = 'Caller invented evidence.'
        with self.assertRaisesRegex(WorkflowError, 'actual independent'):
            accept_requirements(run, altered, {})
        with patch('workflow_lib.gates._review_snapshot_current', return_value=True):
            self.assertTrue(_review_current(run, review, False))
            key = next(iter(run['review_model_authorizations']))
            run['review_model_revocations'] = {key: {'reason': 'Synthetic revocation'}}
            self.assertFalse(_review_current(run, review, False))
        with self.assertRaises(WorkflowError): auth.validate_acceptance_payload(run, report)

    def test_released_validated_acceptance_still_works_after_authorization_history(self):
        from workflow_lib.adversarial_reviews import validate_acceptance_review
        run, package, review = self.acceptance(validated=True)
        key = next(iter(run['review_model_authorizations'])); run['review_model_revocations'] = {key: {'reason': 'Stop authorized route'}}
        self.assertEqual(validate_acceptance_review(run, package, review)['status'], 'allow')
        run['native_invocations'] = {}
        with self.assertRaises(WorkflowError): validate_acceptance_review(run, package, review)

    def test_exact_head_pr_terminal_gate_rejects_revocation(self):
        from workflow_lib.pr_reporting import complete_pr_delivery
        run, package, reports = fixtures.AuthorizedReviewCoverageTests().complete('pr')
        run['pending_pr'] = {'pr_id': '1', 'head_sha': 'h', 'base_sha': 'b', 'manifest_hash': 'synthetic-manifest'}
        # The hosted metadata fixture is a separate terminal-gateway input; independent coverage uses its original package.
        hosted = {**package, 'pr_id': '1', 'pr_number': 1, 'head_sha': 'h', 'base_sha': 'b'}
        review = reports[-1]
        published = {'state': 'success', 'status_url': 'https://example.invalid/status', 'pr_id': '1',
            'head_sha': 'h', 'base_sha': 'b', 'review_id': review['review_id'], 'package_hash': package['package_hash']}
        self.assertEqual(complete_pr_delivery(run, hosted, review, published)['outcome'], 'pull-request')
        key = next(iter(run['review_model_authorizations'])); run['review_model_revocations'] = {key: {'reason': 'Stop'}}
        with self.assertRaises(ValueError): complete_pr_delivery(run, hosted, review, published)

    def test_delivery_approval_artifact_discloses_unvalidated_suitability(self):
        import test_delivery as delivery_fixtures
        from workflow_lib.delivery import prepare_delivery
        from workflow_lib.gates import gate_status
        from workflow_lib.reporting import export_report
        fixture = delivery_fixtures.DeliveryTests(); fixture.setUp(); self.addCleanup(fixture.tearDown)
        run, _, _ = fixtures.AuthorizedReviewCoverageTests().complete('branch')
        run['id'] = 'run-1'
        self.assertEqual(gate_status(run, live=False)['reviewer_models'][0]['suitability'], 'unvalidated')
        # Gate correctness has positive/revoked direct consumer tests; isolate manifest rendering here.
        with patch('workflow_lib.delivery._delivery_gate_open', return_value=True), patch(
                'workflow_lib.delivery._current_acceptance', return_value={'acceptance_hash': 'synthetic-acceptance'}):
            manifest = prepare_delivery(run, fixture.repos(), 'retained-branch')
        self.assertEqual(manifest['reviewer_models'][0]['suitability'], 'unvalidated')
        self.assertIsNone(manifest['reviewer_models'][0]['model_revision'])
        for format in ('json', 'markdown', 'csv'):
            self.assertIn('unvalidated', export_report(manifest, format))
