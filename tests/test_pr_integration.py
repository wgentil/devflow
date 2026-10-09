"""PR rework and journal gate integration without provider writes."""
import unittest
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from commands import pr as pr_commands, review as review_commands
from workflow_lib.specs import content_hash
from workflow_lib.store import read_state, transact, WorkflowError as CliWorkflowError
from workflow_lib.delivery import prepare_delivery, verify_delivery

from skills.workflow.scripts.workflow_lib.journal_domains import reduce_event
from skills.workflow.scripts.workflow_lib.store import WorkflowError


class PrFlowTests(unittest.TestCase):
    def setUp(self):
        self.run = {'id': 'run', 'status': 'active',
                    'pending_pr': {'status': 'pending-review', 'pr_id': '123', 'pr_number': 1,
                                   'owner': 'o', 'repo': 'r', 'base_branch': 'main',
                                   'base_sha': 'b', 'head_sha': 'h', 'manifest_hash': 'old'},
                    'items': {'w1': {'status': 'complete', 'attempts': []}},
                    'verification_proofs': {'p': {'fresh': True}},
                    'reviews': {'item': [{'verdict': 'pass', 'fresh': True}],
                                'pr': [{'review_id': 'rev', 'verdict': 'changes-requested',
                                        'package_hash': 'pkg', 'fresh': True}]},
                    'acceptances': [{'fresh': True}], 'hardening_proofs': {'g': {'passed': True}},
                    'pr_publications': [{'review_id': 'rev', 'state': 'failure'}]}
        self.data = {'runs': {'run': self.run}}

    def test_rework_invalidates_old_proof_and_refreshes_identity(self):
        reduce_event(self.data, 'domain.pr.rework', {'request': {'run_id': 'run', 'review_id': 'rev'}}, 1)
        self.assertEqual(self.run['items']['w1']['status'], 'pending')
        self.assertFalse(self.run['verification_proofs']['p']['fresh'])
        self.assertFalse(self.run['reviews']['item'][0]['fresh'])
        self.assertFalse(self.run['acceptances'][0]['fresh'])
        self.run['plan'] = {'work_items': []}
        self.run['reviews']['branch'] = [{'verdict': 'pass', 'fresh': True}]
        self.run['acceptances'] = [{'complete': True, 'fresh': True}]
        receipt = {**self.run['pending_pr'], 'base_sha': 'b2', 'head_sha': 'h2', 'manifest_hash': 'new'}
        reduce_event(self.data, 'domain.pr.refresh', {'request': {'run_id': 'run', 'receipt': receipt}}, 2)
        self.assertEqual(self.run['pending_pr']['head_sha'], 'h2')
        self.assertIsNone(self.run['pr_rework'])

    def test_cannot_rework_without_published_review(self):
        self.run['pr_publications'] = []
        with self.assertRaises(WorkflowError):
            reduce_event(self.data, 'domain.pr.rework', {'request': {'run_id': 'run', 'review_id': 'rev'}}, 1)

    def test_external_update_reopens_gates_without_reviewer_verdict(self):
        self.run['reviews']['pr'] = []
        self.run['pr_publications'] = []
        result = reduce_event(self.data, 'domain.pr.rework', {'request': {
            'run_id': 'run', 'reason': 'external-update',
            'observed_head': 'h2', 'observed_base': 'b'}}, 1)
        self.assertEqual(result['reason'], 'external-update')
        self.assertEqual(self.run['items']['w1']['status'], 'pending')

    def test_rework_allows_only_new_pr_manifest_preparation(self):
        self.run['pr_rework'] = {'reason': 'changes-requested', 'round': 1}
        self.run['plan'] = {'spec_hash': 'spec', 'work_items': []}
        self.run['acceptances'] = [{'complete': True, 'fresh': True,
                                    'acceptance_hash': 'accepted'}]
        self.run['reviews']['branch'] = [{'verdict': 'pass', 'fresh': True}]
        self.run['repositories'] = {}
        repositories = {'app': {'location': '/tmp/app', 'base': 'b', 'head': 'h2'}}
        fingerprint = {'location': '/tmp/app', 'base': 'b', 'head': 'h2',
                       'repository_head': 'h2', 'worktree_digest': 'clean',
                       'status': '', 'changed_paths': ['a.txt']}
        with patch('workflow_lib.delivery._repo_fingerprint', return_value=fingerprint), \
             patch('workflow_lib.delivery.gate_status', side_effect=lambda run: {
                 'stage': 'delivery' if 'pending_pr' not in run else 'pr-rework'}):
            manifest = prepare_delivery(self.run, repositories, 'pull-request')
            verified = verify_delivery(self.run, manifest, manifest['manifest_hash'], repositories)
            self.assertTrue(verified['verification']['passed'])
            with self.assertRaisesRegex(ValueError, 'gates'):
                prepare_delivery(self.run, repositories, 'local-merge')

    def test_two_automatic_repairs_then_human_direction(self):
        self.run['pr_rework_history'] = [
            {'reason': 'changes-requested', 'direction': None},
            {'reason': 'changes-requested', 'direction': None}]
        with self.assertRaisesRegex(WorkflowError, 'human direction'):
            reduce_event(self.data, 'domain.pr.rework', {'request': {
                'run_id': 'run', 'review_id': 'rev'}}, 1)
        direction = {'review_id': 'rev', 'choice': 'continue', 'actor_id': 'human',
                     'rationale': 'Repair this issue', 'cost_if_wrong': 'Delay'}
        result = reduce_event(self.data, 'domain.pr.rework', {'request': {
            'run_id': 'run', 'review_id': 'rev', 'direction': direction}}, 1)
        self.assertEqual(result['direction'], direction)

    def test_human_request_changes_can_rework_but_reject_cannot(self):
        self.run['reviews']['pr'][-1]['verdict'] = 'human-decision-required'
        self.run['pr_human_decisions'] = [{'package_hash': 'pkg', 'effect': 'reject'}]
        with self.assertRaisesRegex(WorkflowError, 'human owner'):
            reduce_event(self.data, 'domain.pr.rework', {'request': {
                'run_id': 'run', 'review_id': 'rev'}}, 1)
        self.run['pr_human_decisions'][0]['effect'] = 'request-changes'
        result = reduce_event(self.data, 'domain.pr.rework', {'request': {
            'run_id': 'run', 'review_id': 'rev'}}, 1)
        self.assertEqual(result['reason'], 'human-requested-changes')


class FullPrCommandFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=self.repo, text=True).strip()
        git('init', '-q'); git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.com')
        (self.repo / 'a.txt').write_text('before\n')
        git('add', '.'); git('commit', '-qm', 'base')
        self.base = git('rev-parse', 'HEAD')
        (self.repo / 'a.txt').write_text('after\n')
        git('add', '.'); git('commit', '-qm', 'change')
        self.head = git('rev-parse', 'HEAD')
        self.spec = {'id': 'spec', 'requirements': []}
        self.receipt = {'effective_digest': 'rules-1'}
        run = {'id': 'run', 'status': 'active', 'plan': {'spec_hash': content_hash(self.spec),
               'work_items': []}, 'governing_digest': 'rules-1',
               'actors': {'implementer': 'dev'}, 'reviews': {},
               'pending_pr': {'status': 'pending-review', 'pr_id': '123', 'pr_number': 1,
                              'owner': 'o', 'repo': 'r', 'base_branch': 'main',
                              'base_sha': self.base, 'head_sha': self.head,
                              'manifest_hash': 'manifest', 'url': 'https://github.com/o/r/pull/1',
                              'setup_operation_id': 'setup-1'}}
        for i, event in enumerate([
            {'kind': 'spec.created', 'payload': {'spec': self.spec}},
            {'kind': 'spec.approved', 'payload': {'approval': {
                'actor_id': 'human', 'confirmed': True, 'content_hash': content_hash(self.spec)}}},
            {'kind': 'governing.inputs.recorded', 'payload': {'receipt': self.receipt}},
            {'kind': 'setup.seeded', 'payload': {'pr_setup': {'setup-1': {
                'status': 'verified', 'receipt': {'verified': True, 'ruleset_id': 2,
                    'owner': 'o', 'repo': 'r', 'base': 'main', 'context': 'devflow/pr-review',
                    'bypass_actors': []}}}}},
            {'kind': 'run.started', 'payload': {'run': run}},
        ]):
            transact(self.root, i, f'seed-{i}', event)
        self.comments = []
        self.statuses = [{'context': 'devflow/pr-review', 'state': 'pending', 'description': 'pending'}]
        self.hosted_head = self.head
        self.ruleset_enabled = True

    def tearDown(self):
        self.tmp.cleanup()

    def api(self, method, path, body=None):
        if method == 'GET' and path.startswith('/repos/o/r/rulesets?'):
            return [{'id': 2, 'name': 'DevFlow PR review', 'source_type': 'Repository'}]
        if method == 'GET' and path == '/repos/o/r/rulesets/2':
            return {'id': 2, 'name': 'DevFlow PR review', 'target': 'branch',
                    'enforcement': 'active' if self.ruleset_enabled else 'disabled',
                    'bypass_actors': [],
                    'conditions': {'ref_name': {'include': ['refs/heads/main'], 'exclude': []}},
                    'rules': [{'type': 'required_status_checks', 'parameters': {
                        'strict_required_status_checks_policy': True,
                        'required_status_checks': [{'context': 'devflow/pr-review'}]}}]}
        if method == 'GET' and path.endswith('/pulls/1'):
            return {'id': 123, 'number': 1, 'state': 'open', 'title': 'Change', 'body': 'Reason',
                    'head': {'sha': self.hosted_head}, 'base': {'ref': 'main', 'sha': self.base},
                    'changed_files': 1, 'mergeable': True}
        if method == 'GET' and '/pulls/1/files?' in path:
            return [{'filename': 'a.txt'}]
        if method == 'GET' and '/pulls/1/commits?' in path:
            return [{'sha': self.head}]
        if method == 'GET' and '/issues/1/comments?' in path:
            return self.comments
        if method == 'GET' and '/pulls/1/comments?' in path:
            return []
        if method == 'GET' and '/pulls/1/reviews?' in path:
            return []
        if method == 'GET' and '/check-runs?' in path:
            return {'total_count': 1, 'check_runs': [
                {'id': 22, 'name': 'unit', 'status': 'completed', 'conclusion': 'success'}]}
        if method == 'GET' and '/statuses' in path:
            return list(reversed(self.statuses))
        if method == 'POST' and '/issues/1/comments' in path:
            row = {'id': len(self.comments) + 1, 'body': body['body'],
                   'html_url': 'https://github.com/o/r/pull/1#issuecomment-1'}
            self.comments.append(row)
            return row
        if method == 'POST' and '/statuses/' in path:
            row = {'id': len(self.statuses) + 1, **body, 'url': 'https://api.github.com/status/1'}
            self.statuses.append(row)
            return row
        raise AssertionError((method, path, body))

    def test_package_review_publish_complete(self):
        fake = self
        with patch.object(review_commands, 'GithubClient', return_value=fake), \
             patch.object(pr_commands, 'GithubClient', return_value=fake):
            package = review_commands.dispatch(argparse.Namespace(
                root=str(self.root), run_id='run', review_command='pr-package',
                repository=str(self.repo), operation_id='package-1'))['package']
            report = {'package_hash': package['package_hash'], 'verdict': 'pass',
                      'reviewed_files': ['a.txt'], 'findings': []}
            review = review_commands.dispatch(argparse.Namespace(
                root=str(self.root), run_id='run', review_command='record',
                package_hash=package['package_hash'], actor_id='fresh-reviewer',
                invocation_ref='inv-1', tool_available=True, report_json=json.dumps(report),
                operation_id='review-1', operation_id_explicit=True))
            published = pr_commands.dispatch(argparse.Namespace(
                root=str(self.root), run_id='run', pr_command='publish',
                review_id=review['review_id'], operation_id='publish-1'))
            self.assertEqual(published['state'], 'success')
            delivered = pr_commands.dispatch(argparse.Namespace(
                root=str(self.root), run_id='run', pr_command='complete',
                review_id=review['review_id'], operation_id='complete-1'))
            self.assertEqual(delivered['outcome'], 'pull-request')
            self.assertEqual(read_state(self.root)['data']['runs']['run']['status'], 'delivered')

    def test_hosted_head_change_blocks_old_review(self):
        with patch.object(review_commands, 'GithubClient', return_value=self):
            package = review_commands.dispatch(argparse.Namespace(
                root=str(self.root), run_id='run', review_command='pr-package',
                repository=str(self.repo), operation_id='package-1'))['package']
            self.hosted_head = 'f' * 40
            report = {'package_hash': package['package_hash'], 'verdict': 'pass',
                      'reviewed_files': ['a.txt'], 'findings': []}
            with self.assertRaisesRegex(ValueError, 'changed'):
                review_commands.dispatch(argparse.Namespace(
                    root=str(self.root), run_id='run', review_command='record',
                    package_hash=package['package_hash'], actor_id='fresh-reviewer',
                    invocation_ref='inv-1', tool_available=True, report_json=json.dumps(report),
                    operation_id='review-1', operation_id_explicit=True))

    def test_deleted_ruleset_blocks_publication(self):
        with patch.object(review_commands, 'GithubClient', return_value=self), \
             patch.object(pr_commands, 'GithubClient', return_value=self):
            package = review_commands.dispatch(argparse.Namespace(
                root=str(self.root), run_id='run', review_command='pr-package',
                repository=str(self.repo), operation_id='package-1'))['package']
            report = {'package_hash': package['package_hash'], 'verdict': 'pass',
                      'reviewed_files': ['a.txt'], 'findings': []}
            review = review_commands.dispatch(argparse.Namespace(
                root=str(self.root), run_id='run', review_command='record',
                package_hash=package['package_hash'], actor_id='fresh-reviewer',
                invocation_ref='inv-1', tool_available=True, report_json=json.dumps(report),
                operation_id='review-1', operation_id_explicit=True))
            self.ruleset_enabled = False
            with self.assertRaisesRegex(CliWorkflowError, 'policy'):
                pr_commands.dispatch(argparse.Namespace(
                    root=str(self.root), run_id='run', pr_command='publish',
                    review_id=review['review_id'], operation_id='publish-1'))
