import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.model_validation import evaluate_model, promotion_decision


class ModelValidationTests(unittest.TestCase):
    def cases(self):
        return [{'case_id': stage, 'case_hash': 'hash-' + stage,
                 'scoring_version': 1, 'stage': stage, 'approved_by': 'human'}
                for stage in ('specification', 'coding', 'debugging', 'review')]

    def results(self, cases):
        return [{'case_id': row['case_id'], 'case_hash': row['case_hash'],
                 'scoring_version': 1, 'passed': True, 'model_revision': 'rev-1',
                 'host': 'codex', 'model_id': 'm', 'host_version': '1.2.3'} for row in cases]

    def policy(self):
        return {'version': '2', 'thresholds': {stage: {'min_cases': 1,
                'min_pass_rate': 1.0} for stage in
                ('specification', 'coding', 'debugging', 'review')}}

    def test_access_only_stays_candidate(self):
        report = evaluate_model('codex', 'm', '1.2.3', [], [])
        self.assertEqual(promotion_decision(report, self.policy())['status'], 'candidate')

    def test_coding_only_does_not_cover_other_stages(self):
        cases = self.cases()[:1]
        report = evaluate_model('codex', 'm', '1.2.3', cases, self.results(cases))
        self.assertEqual(promotion_decision(report, self.policy())['status'], 'candidate')

    def test_failed_threshold_blocks(self):
        cases = self.cases(); results = self.results(cases)
        results[0]['passed'] = False
        report = evaluate_model('codex', 'm', '1.2.3', cases, results)
        self.assertEqual(promotion_decision(report, self.policy())['status'], 'blocked')

    def test_changed_model_revision_needs_fresh_evidence(self):
        cases = self.cases(); results = self.results(cases)
        results[0]['model_revision'] = 'rev-2'
        report = evaluate_model('codex', 'm', '1.2.3', cases, results)
        self.assertEqual(promotion_decision(report, self.policy())['status'], 'blocked')

    def test_complete_reviewed_coverage_is_eligible(self):
        cases = self.cases()
        report = evaluate_model('codex', 'm', '1.2.3', cases, self.results(cases))
        decision = promotion_decision(report, self.policy())
        self.assertEqual(decision['status'], 'eligible')
        self.assertEqual(len(decision['case_hashes']), 4)
        self.assertEqual(decision['report_hash'], report['report_hash'])

    def test_illustrative_example_parses_and_evaluates(self):
        example = json.loads((Path(__file__).resolve().parents[1] /
                              'docs/examples/model-suitability.json').read_text())
        report = evaluate_model(example['host'], example['model_id'],
                                example['host_version'], example['cases'], example['results'])
        self.assertEqual(promotion_decision(report, self.policy())['status'], 'eligible')

    def test_rehashed_forged_score_is_rejected(self):
        from workflow_lib.model_validation import _digest
        cases = self.cases()
        report = evaluate_model('codex', 'm', '1.2.3', cases, self.results(cases))
        report['stages']['review']['pass_rate'] = 0.0
        report['report_hash'] = _digest({key: value for key, value in report.items()
                                         if key != 'report_hash'})
        self.assertEqual(promotion_decision(report, self.policy())['reason_code'], 'SCORE_MISMATCH')

    def test_rehashed_result_for_different_case_is_rejected(self):
        from workflow_lib.model_validation import _digest
        cases = self.cases()
        report = evaluate_model('codex', 'm', '1.2.3', cases, self.results(cases))
        report['case_results'][0]['case_hash'] = 'other-case'
        report['report_hash'] = _digest({key: value for key, value in report.items()
                                         if key != 'report_hash'})
        self.assertEqual(promotion_decision(report, self.policy())['reason_code'],
                         'CASE_EVIDENCE_INVALID')


if __name__ == '__main__': unittest.main()
