import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.improvement_eval import run_candidate_cases, compare_candidate, retrospective
from workflow_lib.store import WorkflowError


class ImprovementEvalTests(unittest.TestCase):
    def case(self):
        return {'case_id': 'c', 'case_hash': 'h', 'scoring_version': 1,
                'approved_by': 'human', 'command': [sys.executable, '-c',
                'import json; print(json.dumps({"status":"pass"}))'],
                'expected': {'status': 'pass'}, 'timeout_seconds': 10}

    def result(self, passed=True, scoring_version=1, usage=None):
        return {'artifact_hash': 'a', 'case_results': [{'case_id': 'c', 'case_hash': 'h',
                'scoring_version': scoring_version, 'passed': passed,
                'elapsed_ms': 10}], 'usage_status': 'reported' if usage else 'unknown',
                'usage': usage}

    def test_case_set_and_score_version_mismatch(self):
        with self.assertRaises(WorkflowError):
            compare_candidate(self.result(), {'case_results': []}, [self.case()])
        with self.assertRaises(WorkflowError):
            compare_candidate(self.result(), self.result(scoring_version=2), [self.case()])

    def test_missing_usage_never_claims_savings(self):
        report = compare_candidate(self.result(False), self.result(True), [self.case()])
        self.assertEqual(report['cost_status'], 'unknown')
        self.assertEqual(report['quality_delta'], 1.0)

    def test_quality_regression_is_visible(self):
        report = compare_candidate(self.result(True), self.result(False), [self.case()])
        self.assertEqual(report['quality_delta'], -1.0)

    def test_candidate_command_actual_result(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_candidate_cases({'artifact_hash': 'a'}, [self.case()], Path(directory))
        self.assertTrue(result['case_results'][0]['passed'])
        self.assertGreaterEqual(result['case_results'][0]['elapsed_ms'], 0)

    def test_retrospective_cites_observation_owner(self):
        report = retrospective([{'run_id': 'r'}], [{'feedback_id': 'f', 'run_id': 'r',
            'trace_hash': 't', 'feedback': {'owner': 'validator', 'observation': 'missed gate'}}])
        self.assertEqual(report['recommendations'][0]['owner'], 'validator')
        self.assertEqual(report['recommendations'][0]['evidence_refs'], ['feedback:f', 'trace:t'])


if __name__ == '__main__': unittest.main()
