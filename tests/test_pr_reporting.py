"""GitHub PR report idempotence and terminal gate."""
import unittest

from skills.workflow.scripts.workflow_lib.pr_reporting import publish_pr_review, complete_pr_delivery


class FakeClient:
    def __init__(self):
        self.comments = []
        self.statuses = [{'context': 'devflow/pr-review', 'state': 'pending'}]
        self.posts = []
    def api(self, method, path, body=None):
        if method == 'GET' and '/issues/1/comments' in path:
            return self.comments
        if method == 'GET' and '/pulls/1/comments' in path:
            return []
        if method == 'GET' and '/statuses' in path:
            return list(reversed(self.statuses))
        if method == 'POST':
            self.posts.append((path, body))
            if '/issues/1/comments' in path:
                row = {'id': len(self.comments) + 1, 'body': body['body'], 'html_url': 'https://github.com/o/r/pull/1#issuecomment-1'}
                self.comments.append(row)
                return row
            if '/statuses/' in path:
                row = {'id': len(self.statuses) + 1, **body, 'url': 'https://api.github.com/status/1'}
                self.statuses.append(row)
                return row
        raise AssertionError((method, path, body))


class PrReportingTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.package = {'package_hash': 'pkg', 'pr_id': '123', 'pr_number': 1,
                        'owner': 'o', 'repo': 'r', 'head_sha': 'a' * 40,
                        'base_sha': 'b' * 40, 'changed_files': ['a.py']}
        self.review = {'review_id': 'review', 'package_hash': 'pkg', 'verdict': 'pass',
                       'findings': [], 'reviewed_files': ['a.py']}

    def test_publish_success_idempotently(self):
        first = publish_pr_review(self.client, self.package, self.review, [])
        second = publish_pr_review(self.client, self.package, self.review, [])
        self.assertEqual(first['state'], 'success')
        self.assertEqual(second['state'], 'success')
        self.assertEqual(len(self.client.posts), 2)

    def test_nonpass_never_success(self):
        self.review['verdict'] = 'human-decision-required'
        receipt = publish_pr_review(self.client, self.package, self.review, [])
        self.assertNotEqual(receipt['state'], 'success')

    def test_terminal_gate_requires_confirmed_status(self):
        run = {'id': 'run', 'status': 'active', 'pending_pr': {'pr_id': '123', 'head_sha': 'a' * 40,
                'base_sha': 'b' * 40,
                'manifest_hash': 'manifest'}, 'reviews': {'pr': [self.review]}}
        with self.assertRaisesRegex(ValueError, 'success'):
            complete_pr_delivery(run, self.package, self.review, {'state': 'pending'})
        result = complete_pr_delivery(run, self.package, self.review,
            {'state': 'success', 'package_hash': 'pkg', 'review_id': 'review',
             'pr_id': '123', 'head_sha': 'a' * 40, 'base_sha': 'b' * 40,
             'status_url': 'https://api.github.com/status/1'})
        self.assertEqual(result['outcome'], 'pull-request')
