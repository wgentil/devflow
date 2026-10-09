import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError, read_state
from workflow_lib.pr_setup import configure_pr_setup, inspect_pr_setup
from workflow_lib.github_pr import GithubClient
from commands import pr


class FakeGithub:
    def __init__(self):
        self.rules = [{'id': 3, 'name': 'Existing CI', 'target': 'branch', 'enforcement': 'active'}]
        self.writes = []
        self.mismatch = False

    def api(self, method, path, body=None):
        if path == '/users/wayne':
            return {'id': 17, 'login': 'wayne'}
        if path == '/repos/acme/app/rulesets':
            if method == 'GET':
                return [{'id': rule['id'], 'name': rule['name']} for rule in self.rules]
            self.writes.append((method, path, body))
            rule = {**body, 'id': 4}
            self.rules.append(rule)
            return rule
        if path == '/repos/acme/app/rulesets/4':
            if method == 'GET':
                rule = next(rule for rule in self.rules if rule['id'] == 4)
                return {**rule, 'enforcement': 'disabled'} if self.mismatch else rule
            self.writes.append((method, path, body))
            self.rules = [rule if rule['id'] != 4 else {**body, 'id': 4} for rule in self.rules]
            return next(rule for rule in self.rules if rule['id'] == 4)
        raise AssertionError((method, path, body))


class PrSetupTests(unittest.TestCase):
    def test_configure_creates_only_owned_strict_rule_and_is_idempotent(self):
        client = FakeGithub()
        selected = [{'actor_type': 'User', 'login': 'wayne'}]
        result = configure_pr_setup(client, 'acme', 'app', 'main', selected)
        self.assertEqual(result['ruleset_id'], 4)
        self.assertTrue(result['verified'])
        self.assertEqual(client.rules[0]['name'], 'Existing CI')
        rule = client.rules[1]
        self.assertEqual(rule['conditions']['ref_name']['include'], ['refs/heads/main'])
        self.assertEqual(rule['bypass_actors'], [{'actor_id': 17, 'actor_type': 'User', 'bypass_mode': 'always'}])
        self.assertEqual(rule['rules'], [{'type': 'required_status_checks', 'parameters': {
            'strict_required_status_checks': True,
            'required_status_checks': [{'context': 'devflow/pr-review'}]}}])
        self.assertEqual(configure_pr_setup(client, 'acme', 'app', 'main', selected), result)
        self.assertEqual(len(client.writes), 1)

    def test_inspect_is_read_only_and_detects_bad_rule(self):
        client = FakeGithub()
        self.assertFalse(inspect_pr_setup(client, 'acme', 'app', 'main')['configured'])
        configure_pr_setup(client, 'acme', 'app', 'main', [{'actor_type': 'User', 'login': 'wayne'}])
        client.mismatch = True
        self.assertFalse(inspect_pr_setup(client, 'acme', 'app', 'main')['configured'])
        self.assertEqual(len(client.writes), 1)

    def test_missing_actor_and_readback_mismatch_fail_closed(self):
        client = FakeGithub()
        with self.assertRaises(WorkflowError) as caught:
            configure_pr_setup(client, 'acme', 'app', 'main', [{'actor_type': 'User', 'login': ''}])
        self.assertEqual(caught.exception.code, 'PR_BYPASS_ACTOR_INVALID')
        self.assertEqual(client.writes, [])
        client.mismatch = True
        with self.assertRaises(WorkflowError) as caught:
            configure_pr_setup(client, 'acme', 'app', 'main', [{'actor_type': 'User', 'login': 'wayne'}])
        self.assertEqual(caught.exception.code, 'PR_RULESET_UNVERIFIED')

    def test_github_adapter_classifies_permission_and_timeout(self):
        client = GithubClient(timeout_seconds=1)
        denied = subprocess.CompletedProcess(['gh'], 1, '', 'HTTP 403: Resource not accessible by integration')
        with patch('workflow_lib.github_pr.subprocess.run', return_value=denied):
            with self.assertRaises(WorkflowError) as caught:
                client.api('GET', '/repos/acme/app/rulesets')
        self.assertEqual(caught.exception.code, 'GITHUB_PERMISSION_DENIED')
        with patch('workflow_lib.github_pr.subprocess.run', side_effect=subprocess.TimeoutExpired(['gh'], 1)):
            with self.assertRaises(WorkflowError) as caught:
                client.api('POST', '/repos/acme/app/rulesets', {'name': 'DevFlow PR review'})
        self.assertEqual(caught.exception.code, 'GITHUB_WRITE_UNCERTAIN')

    def test_setup_command_journals_verified_readback_and_exact_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'control'
            source = Path(directory) / 'request.json'
            request = {'owner': 'acme', 'repo': 'app', 'base': 'main',
                       'bypass_actors': [{'actor_type': 'User', 'login': 'wayne'}]}
            source.write_text(json.dumps(request))
            parsed = argparse.Namespace(pr_command='setup', root=str(root), request_file=str(source),
                                        operation_id='setup-1')
            client = FakeGithub()
            with patch('commands.pr.GithubClient', return_value=client):
                first = pr.dispatch(parsed)
                second = pr.dispatch(parsed)
            self.assertTrue(first['verified'])
            self.assertEqual(second['ruleset_id'], 4)
            self.assertEqual(len(client.writes), 1)
            self.assertEqual(read_state(root)['data']['pr_setup']['setup-1']['status'], 'verified')
            source.write_text(json.dumps({**request, 'base': 'release'}))
            with patch('commands.pr.GithubClient', return_value=client):
                with self.assertRaises(WorkflowError) as caught:
                    pr.dispatch(parsed)
            self.assertEqual(caught.exception.code, 'OPERATION_CONFLICT')

    def test_uncertain_setup_write_leaves_reconciliation_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'control'
            source = Path(directory) / 'request.json'
            source.write_text(json.dumps({'owner': 'acme', 'repo': 'app', 'base': 'main',
                                          'bypass_actors': [{'actor_type': 'User', 'login': 'wayne'}]}))
            parsed = argparse.Namespace(pr_command='setup', root=str(root), request_file=str(source),
                                        operation_id='setup-uncertain')
            client = FakeGithub()
            original = client.api
            def api(method, path, body=None):
                if method == 'POST':
                    original(method, path, body)
                    raise WorkflowError('GITHUB_WRITE_UNCERTAIN', 'response lost')
                return original(method, path, body)
            client.api = api
            with patch('commands.pr.GithubClient', return_value=client):
                with self.assertRaises(WorkflowError):
                    pr.dispatch(parsed)
            self.assertEqual(read_state(root)['data']['pr_setup']['setup-uncertain']['status'], 'uncertain')
            client.api = original
            with patch('commands.pr.GithubClient', return_value=client):
                recovered = pr.dispatch(parsed)
            self.assertTrue(recovered['verified'])
            self.assertEqual(read_state(root)['data']['pr_setup']['setup-uncertain']['status'], 'verified')
            self.assertEqual(len(client.writes), 1)
