"""Public CLI and durable admission in both stores; transport/proofs are synthetic."""
import copy
import json
import itertools
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_review_dispatch as fixtures
from test_review_authorizations import selection
from workflow_lib import store


class ReviewAuthorizationIntegrationTests(unittest.TestCase):
    def test_public_workflow_authorization_both_storage_formats(self):
        from control_store_fixtures import legacy_root
        from workflow_lib.adversarial_reviews import review_input_id, review_coverage
        from workflow_lib.reviews import prepare_review
        from workflow_lib.review_dispatch import dispatch_workflow_review
        from workflow_lib.stored_records import require_package
        entry = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'
        for legacy, role in itertools.product((True, False), ('branch', 'acceptance')):
            with self.subTest(legacy=legacy, role=role):
                fixture = fixtures.ReviewDispatchTests(); self.addCleanup(fixture.doCleanups)
                original_root, repo, request, backend = fixture.native_fixture()
                data = store.read_state(original_root)['data']
                run = data['runs']['run']
                run['verification_proofs'] = {'synthetic-green': {'id': 'synthetic-green', 'passed': True,
                    'kind': 'code', 'phase': 'GREEN', 'source_identity': run['source_identity'],
                    'item_id': 'W1', 'token': 't', 'fresh': True}}
                package = require_package(next(iter(run['review_packages'].values())))
                head = package['repositories']['repo']['head']
                package = prepare_review(run, role, {'repo': {'location': str(repo), 'base': head, 'head': head}})
                run['review_packages'] = {package['package_hash']: package}
                data['host_bindings']['review']['package_hash'] = package['package_hash']
                if role == 'acceptance':
                    data['host_bindings']['review']['role'] = 'acceptance-reviewer'
                    data['host_bindings']['review'].pop('perspective', None)
                    request.pop('perspective', None)
                root = legacy_root(original_root.parent / 'legacy') if legacy else original_root.parent / 'v2'
                store.transact(root, 0, 'synthetic-source-and-proof-fixture', {'kind': 'fixture', 'payload': data})
                def cli(command, value=None, operation=None, extra=()):
                    args = [sys.executable, '-B', str(entry), 'review', command, '--root', str(root), '--run-id', 'run']
                    if value is not None:
                        path = root.parent / 'cli-input.json'; path.write_text(json.dumps(value))
                        args += ['--input', str(path)]
                    if operation: args += ['--operation-id', operation]
                    result = subprocess.run([*args, *extra], capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    return json.loads(result.stdout)
                proposed = cli('model-proposal', {**selection(), 'model': 'small-sounding-preferred'})
                cli('authorize-model', {'proposal': proposed, 'confirmed_hash': proposed['proposal_hash'],
                    'actor_id': 'fixture-human', 'provenance': {'kind': 'user-message', 'ref': 'synthetic:integration-consent'}}, 'consent')
                report = {'package_hash': package['package_hash'], 'verdict': 'pass', 'findings': [],
                    'perspective': 'security', 'review_input_ref': review_input_id(package),
                    'reviewed_inputs': copy.deepcopy(package['review_inputs'])}
                if role == 'acceptance':
                    report.pop('perspective')
                    report['requirements'] = [{'id': 'R1', 'verdict': 'MET', 'citations': [
                        {'repo_id': 'repo', 'path': 'code.py', 'line': 1}], 'rationale': 'Synthetic fixture requirement.'}]
                backend.invoke.return_value['output'] = json.dumps(report)
                request.update(review_authorization_hash=proposed['proposal_hash'], diagnostic=False, context_max_bytes=32768)
                policy = fixture.policy(); policy['hosts'] = {'codex': {}}
                policy['stages']['acceptance'] = 'deep-reasoning'
                with patch('workflow_lib.native_runtime.policy', return_value=policy), patch('workflow_lib.native_runtime.CodexBackend', return_value=backend):
                    result = dispatch_workflow_review(root, request, 'actual-coordinator-synthetic-transport')
                self.assertEqual(result['status'], 'allow', result)
                saved = cli('record', operation='actual-output-admission', extra=(
                    '--package-hash', package['package_hash'], '--actor-id', 'independent',
                    '--invocation-ref', result['invocation_ref'], '--model-invocation-id', result['invocation_id'],
                    '--tool-available', '--report-json', json.dumps(report)))
                self.assertEqual(saved['verdict'], 'pass')
                before = store.read_state(root)
                current = before['data']['runs']['run']
                from workflow_lib.hosts import apply_host_event
                from workflow_lib.host_completion import check_completion
                binding = before['data']['host_bindings']['review']
                apply_host_event(before['data'], 'task-bind', {'binding_id': 'review', 'revision': 1, 'task_id': 'review-done',
                    'scope': 'review', 'package_hash': package['package_hash'], 'invocation_id': result['invocation_id']})
                self.assertEqual(check_completion(before['data'], binding, 'review-done', live=False)['status'], 'allow')
                if role == 'branch':
                    coverage = review_coverage(current, 'branch')
                    self.assertIn('security', coverage['effective'])
                    self.assertNotIn('security', coverage['missing_perspectives'])
                else:
                    from workflow_lib.adversarial_reviews import validate_acceptance_review
                    self.assertEqual(saved['requirements'], report['requirements'])
                    self.assertEqual(validate_acceptance_review(current, package, saved)['status'], 'allow')
                summary = cli('summary')
                self.assertEqual(summary['reviewer_models'][0]['suitability'], 'unvalidated')
                self.assertEqual(store.read_state(root)['version'], before['version'])
                cli('revoke-model', {'authorization_hash': proposed['proposal_hash'], 'actor_id': 'fixture-human',
                    'reason': 'Stop', 'provenance': {'kind': 'user-message', 'ref': 'synthetic:integration-revoke'}}, 'revoke')
                revoked = store.read_state(root)['data']['runs']['run']
                if role == 'branch':
                    self.assertIn('security', review_coverage(revoked, 'branch')['missing_perspectives'])
                else:
                    with self.assertRaises(store.WorkflowError): validate_acceptance_review(revoked, package, saved)
                self.assertEqual(revoked['reviews'], current['reviews'])
                self.assertEqual(revoked['model_receipts'], current['model_receipts'])
                before['data']['runs']['run'] = revoked
                self.assertEqual(check_completion(before['data'], binding, 'review-done', live=False)['status'], 'block')
