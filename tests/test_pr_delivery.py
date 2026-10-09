import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.delivery import prepare_delivery, verify_delivery, record_delivery
from workflow_lib.pr_delivery import open_pr_delivery, reconcile_pr_delivery
from workflow_lib.store import WorkflowError
from workflow_lib.store import read_state, transact
from tests import test_delivery as delivery_tests
from commands import pr as pr_commands


class FakePrGithub:
    def __init__(self, base_sha, head_sha):
        self.base_sha = base_sha
        self.head_sha = head_sha
        self.pr = None
        self.statuses = []
        self.writes = []

    def api(self, method, path, body=None):
        if method == 'GET' and path.startswith('/repos/acme/app/rulesets?'):
            return [{'id': 2, 'name': 'DevFlow PR review', 'source_type': 'Repository'}]
        if method == 'GET' and path == '/repos/acme/app/rulesets/2':
            return {'id': 2, 'name': 'DevFlow PR review', 'target': 'branch',
                    'enforcement': 'active', 'bypass_actors': [],
                    'conditions': {'ref_name': {'include': ['refs/heads/main'], 'exclude': []}},
                    'rules': [{'type': 'required_status_checks', 'parameters': {
                        'strict_required_status_checks_policy': True,
                        'required_status_checks': [{'context': 'devflow/pr-review'}]}}]}
        if path.startswith('/repos/acme/app/pulls?'):
            return [self.pr] if self.pr else []
        if path == '/repos/acme/app/pulls' and method == 'POST':
            self.writes.append((method, path, body))
            self.pr = {'number': 12, 'id': 412, 'html_url': 'https://github.com/acme/app/pull/12',
                       'state': 'open', 'head': {'sha': self.head_sha},
                       'base': {'ref': 'main', 'sha': self.base_sha}}
            return self.pr
        if path == '/repos/acme/app/pulls/12':
            return self.pr
        if path == f'/repos/acme/app/statuses/{self.head_sha}' and method == 'POST':
            self.writes.append((method, path, body))
            self.statuses.insert(0, {**body, 'id': len(self.statuses) + 1})
            return self.statuses[0]
        if path == f'/repos/acme/app/commits/{self.head_sha}/statuses?per_page=100':
            return self.statuses
        raise AssertionError((method, path, body))


class PrDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = delivery_tests.DeliveryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.git('remote', 'add', 'origin', 'https://github.com/acme/app.git')
        self.run = self.fixture.run
        self.manifest = prepare_delivery(self.run, self.fixture.repos(), 'pull-request')
        self.verified = verify_delivery(self.run, self.manifest,
                                        self.manifest['manifest_hash'], self.fixture.repos())
        self.client = FakePrGithub(self.fixture.base, self.fixture.head)
        self.request = {'owner': 'acme', 'repo': 'app', 'base_branch': 'main',
                        'head_branch': 'feature', 'title': 'Change', 'body': 'Implements R1',
                        'authorization': {'approved': True, 'actor_id': 'owner',
                            'manifest_hash': self.manifest['manifest_hash'], 'action': 'delivery.pull-request'},
                        'setup': {'verified': True, 'owner': 'acme', 'repo': 'app',
                                  'base': 'main', 'context': 'devflow/pr-review', 'ruleset_id': 2}}

    def test_open_pr_keeps_delivery_pending_and_publishes_initial_status(self):
        result = open_pr_delivery(self.run, self.verified, self.request, self.client)
        self.assertEqual(result['status'], 'pending-review')
        self.assertEqual(result['pr_id'], '412')
        self.assertEqual(result['head_sha'], self.fixture.head)
        self.assertEqual(result['base_sha'], self.fixture.base)
        self.assertEqual(self.client.statuses[0]['context'], 'devflow/pr-review')
        self.assertEqual(self.client.statuses[0]['state'], 'pending')
        self.assertEqual(len(self.client.writes), 2)
        self.assertEqual(reconcile_pr_delivery(self.run, self.verified, self.request, self.client), result)
        self.assertEqual(len(self.client.writes), 2)

    def test_open_pr_rejects_unauthorized_and_stale_manifest_before_provider_write(self):
        bad = {**self.request, 'authorization': {**self.request['authorization'], 'approved': False}}
        with self.assertRaises(ValueError):
            open_pr_delivery(self.run, self.verified, bad, self.client)
        stale = {**self.verified, 'verification': {'passed': False}}
        with self.assertRaises(ValueError):
            open_pr_delivery(self.run, stale, self.request, self.client)
        self.assertEqual(self.client.writes, [])

    def test_open_pr_rechecks_local_head_after_manifest_verification(self):
        (self.fixture.repo / 'app.py').write_text('VALUE = 3\n')
        with self.assertRaises(ValueError):
            open_pr_delivery(self.run, self.verified, self.request, self.client)
        self.assertEqual(self.client.writes, [])

    def test_pending_pr_operation_does_not_hide_stale_verification(self):
        self.run['pr_open'] = {'status': 'pending', 'operation_id': 'open-1'}
        (self.fixture.repo / 'app.py').write_text('VALUE = 3\n')
        with self.assertRaises(ValueError):
            open_pr_delivery(self.run, self.verified, self.request, self.client)
        self.assertEqual(self.client.writes, [])

    def test_open_pr_rejects_repository_identity_mismatch(self):
        wrong = {**self.request, 'owner': 'other',
                 'setup': {**self.request['setup'], 'owner': 'other'}}
        with self.assertRaises(ValueError):
            open_pr_delivery(self.run, self.verified, wrong, self.client)
        self.assertEqual(self.client.writes, [])

    def test_direct_delivery_cannot_open_pr_and_old_terminal_record_is_disabled(self):
        direct = prepare_delivery(self.run, self.fixture.repos(), 'retained-branch')
        with self.assertRaises(ValueError):
            open_pr_delivery(self.run, direct, self.request, self.client)
        actual = {'authorization': self.request['authorization'], 'outcome': 'pull-request',
                  'repository_heads': {'repo-1': self.fixture.head},
                  'pull_request': {'id': '412'}}
        with self.assertRaises(ValueError):
            record_delivery(self.run, self.verified, actual)
        self.assertEqual(self.client.writes, [])

    def test_changed_provider_head_blocks_reconciliation(self):
        open_pr_delivery(self.run, self.verified, self.request, self.client)
        self.client.pr['head']['sha'] = 'f' * 40
        with self.assertRaises(WorkflowError) as caught:
            reconcile_pr_delivery(self.run, self.verified, self.request, self.client)
        self.assertEqual(caught.exception.code, 'PR_HEAD_STALE')

    def test_open_command_journals_pending_pr_and_exact_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'control'
            manifest_file = Path(directory) / 'manifest.json'
            request_file = Path(directory) / 'request.json'
            manifest_file.write_text(json.dumps(self.verified))
            request_file.write_text(json.dumps({**self.request, 'setup_operation_id': 'setup-1'}))
            run = {**self.run, 'repositories': self.run['repositories']}
            transact(root, 0, 'fixture', {'kind': 'fixture', 'payload': {
                'runs': {run['id']: run}, 'pr_setup': {'setup-1': {'status': 'verified',
                    'receipt': self.request['setup'], 'request_hash': 'fixture'}}}})
            parsed = argparse.Namespace(pr_command='open', root=str(root), run_id=run['id'],
                                        manifest_file=str(manifest_file), request_file=str(request_file),
                                        operation_id='open-1')
            with patch('commands.pr.GithubClient', return_value=self.client):
                first = pr_commands.dispatch(parsed)
                second = pr_commands.dispatch(parsed)
            self.assertEqual(first['status'], 'pending-review')
            self.assertEqual(second['pr_id'], first['pr_id'])
            self.assertEqual(len(self.client.writes), 2)
            saved = read_state(root)['data']['runs'][run['id']]
            self.assertEqual(saved['status'], 'active')
            self.assertEqual(saved['pending_pr']['head_sha'], self.fixture.head)
            self.assertEqual(saved['pr_open']['status'], 'verified')

    def test_uncertain_pr_create_reconciles_existing_provider_pr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'control'
            manifest_file = Path(directory) / 'manifest.json'
            request_file = Path(directory) / 'request.json'
            manifest_file.write_text(json.dumps(self.verified))
            request_file.write_text(json.dumps({**self.request, 'setup_operation_id': 'setup-1'}))
            transact(root, 0, 'fixture', {'kind': 'fixture', 'payload': {
                'runs': {self.run['id']: self.run}, 'pr_setup': {'setup-1': {'status': 'verified',
                    'receipt': self.request['setup'], 'request_hash': 'fixture'}}}})
            parsed = argparse.Namespace(pr_command='open', root=str(root), run_id=self.run['id'],
                                        manifest_file=str(manifest_file), request_file=str(request_file),
                                        operation_id='open-uncertain')
            original = self.client.api
            def lost_response(method, path, body=None):
                if method == 'POST' and path == '/repos/acme/app/pulls':
                    original(method, path, body)
                    raise WorkflowError('GITHUB_WRITE_UNCERTAIN', 'response lost')
                return original(method, path, body)
            self.client.api = lost_response
            with patch('commands.pr.GithubClient', return_value=self.client):
                with self.assertRaises(WorkflowError):
                    pr_commands.dispatch(parsed)
            self.assertEqual(read_state(root)['data']['runs'][self.run['id']]['pr_open']['status'], 'uncertain')
            self.client.api = original
            # An explicit retry may post the missing pending status only after
            # finding the exact existing PR.
            with patch('commands.pr.GithubClient', return_value=self.client):
                recovered = pr_commands.dispatch(parsed)
            self.assertEqual(recovered['pr_id'], '412')
            self.assertEqual(len([write for write in self.client.writes if write[1] == '/repos/acme/app/pulls']), 1)

    def test_failed_pr_input_can_be_corrected_with_new_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'control'
            manifest_file = Path(directory) / 'manifest.json'
            request_file = Path(directory) / 'request.json'
            manifest_file.write_text(json.dumps(self.verified))
            transact(root, 0, 'fixture', {'kind': 'fixture', 'payload': {
                'runs': {self.run['id']: self.run}, 'pr_setup': {'setup-1': {'status': 'verified',
                    'receipt': self.request['setup'], 'request_hash': 'fixture'}}}})
            bad = {**self.request, 'setup_operation_id': 'setup-1',
                   'authorization': {**self.request['authorization'], 'approved': False}}
            request_file.write_text(json.dumps(bad))
            parsed = argparse.Namespace(pr_command='open', root=str(root), run_id=self.run['id'],
                                        manifest_file=str(manifest_file), request_file=str(request_file),
                                        operation_id='bad-open')
            with patch('commands.pr.GithubClient', return_value=self.client):
                with self.assertRaises(ValueError):
                    pr_commands.dispatch(parsed)
                self.assertEqual(read_state(root)['data']['runs'][self.run['id']]['pr_open']['status'], 'failed')
                request_file.write_text(json.dumps({**self.request, 'setup_operation_id': 'setup-1'}))
                parsed.operation_id = 'corrected-open'
                result = pr_commands.dispatch(parsed)
            self.assertEqual(result['status'], 'pending-review')
