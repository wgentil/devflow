"""PR reviewer verdict and human judgment boundaries."""
import unittest

from skills.workflow.scripts.workflow_lib.pr_reviews import record_pr_review, record_pr_human_decision


class PrDecisionTests(unittest.TestCase):
    def setUp(self):
        self.package = {'package_hash': 'pkg', 'role': 'pr', 'changed_files': ['a.py', 'b.py'],
                        'snapshot': {'checks': [{'name': 'unit', 'status': 'completed', 'conclusion': 'success'}],
                                     'mergeable': True},
                        'pr_id': '123', 'head_sha': 'a' * 40}
        self.run = {'id': 'run', 'pending_pr': {'pr_id': '123', 'head_sha': 'a' * 40},
                    'actors': {'implementer': 'dev', 'branch_reviewer': 'old-reviewer'},
                    'review_packages': {'pkg': self.package}, 'reviews': {}}
        self.reviewer = {'role': 'pr', 'actor_id': 'fresh', 'invocation_ref': 'inv-1', 'tool_available': True}
        self.report = {'package_hash': 'pkg', 'verdict': 'pass', 'reviewed_files': ['a.py', 'b.py'],
                       'findings': []}

    def test_complete_pass(self):
        self.assertEqual(record_pr_review(self.run, 'pkg', self.reviewer, self.report)['verdict'], 'pass')

    def test_missing_coverage_blocks(self):
        self.report['reviewed_files'] = ['a.py']
        with self.assertRaisesRegex(ValueError, 'every changed file'):
            record_pr_review(self.run, 'pkg', self.reviewer, self.report)

    def test_prior_actor_rejected(self):
        self.reviewer['actor_id'] = 'old-reviewer'
        with self.assertRaisesRegex(ValueError, 'distinct'):
            record_pr_review(self.run, 'pkg', self.reviewer, self.report)

    def test_failed_ci_cannot_pass(self):
        self.package['snapshot']['checks'][0]['conclusion'] = 'failure'
        with self.assertRaisesRegex(ValueError, 'CI'):
            record_pr_review(self.run, 'pkg', self.reviewer, self.report)

    def test_neutral_and_skipped_check_runs_are_acceptable(self):
        self.package['snapshot']['checks'] = [
            {'kind': 'check-run', 'name': 'optional', 'status': 'completed', 'conclusion': 'skipped'},
            {'kind': 'check-run', 'name': 'analysis', 'status': 'completed', 'conclusion': 'neutral'},
            {'kind': 'status', 'name': 'unit', 'status': 'completed', 'conclusion': 'success'}]
        self.assertEqual(record_pr_review(self.run, 'pkg', self.reviewer, self.report)['verdict'], 'pass')

    def test_blocked_requires_next_action(self):
        self.report['verdict'] = 'blocked'
        with self.assertRaisesRegex(ValueError, 'next action'):
            record_pr_review(self.run, 'pkg', self.reviewer, self.report)
        self.report['blockers'] = [{'reason': 'CI unavailable', 'next_action': 'Rerun CI'}]
        self.assertEqual(record_pr_review(self.run, 'pkg', self.reviewer, self.report)['verdict'], 'blocked')

    def test_human_question_and_decision(self):
        self.report.update(verdict='human-decision-required', findings=[{
            'id': 'f1', 'severity': 'important', 'path': 'a.py', 'line': 1,
            'reason': 'Ambiguous rule', 'acceptance_condition': 'Choose behavior',
            'question': 'Which rule applies?', 'options': [
                {'choice': 'A', 'consequence': 'Users see A', 'effect': 'accept'},
                {'choice': 'B', 'consequence': 'Users see B', 'effect': 'request-changes'}],
            'impact': 'Wrong user result', 'recommendation': 'A', 'owner': 'owner-1'}])
        review = record_pr_review(self.run, 'pkg', self.reviewer, self.report)
        self.run['reviews']['pr'] = [review]
        decision = record_pr_human_decision(self.run, 'pkg', 'owner-1', 'f1', 'A', 'Reason')
        self.assertEqual(decision['choice'], 'A')
        self.assertEqual(decision['effect'], 'accept')
        with self.assertRaisesRegex(ValueError, 'distinct'):
            record_pr_human_decision(self.run, 'pkg', 'fresh', 'f1', 'A', 'Reason')

    def test_human_required_finding_blocks_later_pass_without_decision(self):
        self.run['reviews']['pr'] = [{'review_id': 'review-1', 'package_hash': 'pkg',
            'verdict': 'human-decision-required', 'actor_id': 'prior-pr',
            'findings': [{'id': 'f1'}]}]
        with self.assertRaisesRegex(ValueError, 'human-required'):
            record_pr_review(self.run, 'pkg', self.reviewer, self.report)

    def test_third_changes_report_remains_recordable_for_human_direction(self):
        self.report.update(verdict='changes-requested', findings=[{
            'id': 'f1', 'severity': 'important', 'path': 'a.py', 'line': 1,
            'reason': 'Wrong', 'acceptance_condition': 'Correct result'}])
        self.run['reviews']['pr'] = [{'verdict': 'changes-requested'}, {'verdict': 'changes-requested'}]
        self.assertEqual(record_pr_review(self.run, 'pkg', self.reviewer, self.report)['verdict'],
                         'changes-requested')

    def test_reject_choice_cannot_become_pass(self):
        self.run['reviews']['pr'] = [{'review_id': 'review-1', 'package_hash': 'pkg',
            'verdict': 'human-decision-required', 'actor_id': 'prior-pr',
            'findings': [{'id': 'f1'}]}]
        self.run['pr_human_decisions'] = [{'package_hash': 'pkg', 'finding_id': 'f1', 'effect': 'reject'}]
        with self.assertRaisesRegex(ValueError, 'accepting decisions'):
            record_pr_review(self.run, 'pkg', self.reviewer, self.report)
