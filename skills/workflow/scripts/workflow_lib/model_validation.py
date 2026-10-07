"""Representative reviewed-case evidence for model suitability promotion."""

from __future__ import annotations

import hashlib
import json

STAGES = ('specification', 'coding', 'debugging', 'review')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def evaluate_model(host: str, model_id: str, host_version: str,
                   cases: list[dict], results: list[dict]) -> dict:
    expected = {row.get('case_id'): row for row in cases if row.get('approved_by')
                and row.get('stage') in STAGES and row.get('case_hash')}
    actual = {row.get('case_id'): row for row in results}
    issues = []
    if len(expected) != len(cases) or len(actual) != len(results):
        issues.append('CASE_SET_INVALID')
    revisions = {row.get('model_revision') for row in results if row.get('model_revision')}
    if len(revisions) > 1:
        issues.append('MODEL_REVISION_CHANGED')
    for case_id, result in actual.items():
        case = expected.get(case_id)
        if (not case or result.get('case_hash') != case.get('case_hash')
                or result.get('scoring_version') != case.get('scoring_version')
                or result.get('host') != host or result.get('model_id') != model_id
                or result.get('host_version') != host_version):
            issues.append('EVIDENCE_SCOPE_MISMATCH')
    stages = {}
    for stage in STAGES:
        selected = [row for row in expected.values() if row['stage'] == stage]
        observed = [actual[row['case_id']] for row in selected if row['case_id'] in actual]
        stages[stage] = {'case_count': len(selected), 'observed_count': len(observed),
                         'passed_count': sum(row.get('passed') is True for row in observed),
                         'pass_rate': sum(row.get('passed') is True for row in observed) / len(selected)
                                      if selected else None,
                         'coverage': len(observed) / len(selected) if selected else 0}
    body = {'version': 1, 'host': host, 'model_id': model_id,
            'host_version': host_version, 'model_revision': next(iter(revisions)) if len(revisions) == 1 else None,
            'case_hashes': sorted(row['case_hash'] for row in expected.values()),
            'case_inputs': [{'case_id': identifier, 'case_hash': row['case_hash'],
                             'scoring_version': row['scoring_version'], 'stage': row['stage'],
                             'approved_by': row['approved_by']}
                            for identifier, row in sorted(expected.items())],
            'case_results': [{'case_id': identifier, 'case_hash': row.get('case_hash'),
                              'passed': row.get('passed') is True,
                              'result_hash': _digest(row)} for identifier, row in sorted(actual.items())],
            'stages': stages, 'issues': sorted(set(issues))}
    return {**body, 'report_hash': _digest(body)}


def promotion_decision(report: dict, policy: dict) -> dict:
    base = {'status': 'candidate', 'report_hash': report.get('report_hash'),
            'case_hashes': report.get('case_hashes', []), 'policy_version': policy.get('version')}
    unsigned = {key: value for key, value in report.items() if key != 'report_hash'}
    if report.get('report_hash') != _digest(unsigned):
        return {**base, 'status': 'blocked', 'reason_code': 'REPORT_HASH_INVALID'}
    if report.get('issues'):
        return {**base, 'status': 'blocked', 'reason_code': report['issues'][0]}
    cases = report.get('case_inputs', [])
    results = report.get('case_results', [])
    if (not isinstance(cases, list) or not isinstance(results, list)
            or sorted(row.get('case_hash') for row in cases) != report.get('case_hashes')
            or len({row.get('case_id') for row in cases}) != len(cases)
            or len({row.get('case_id') for row in results}) != len(results)
            or any(not row.get('approved_by') or row.get('stage') not in STAGES for row in cases)):
        return {**base, 'status': 'blocked', 'reason_code': 'CASE_EVIDENCE_INVALID'}
    observed = {row['case_id']: row for row in results}
    expected = {row['case_id']: row for row in cases}
    if (set(observed) - set(expected)
            or any(row.get('case_hash') != expected[case_id].get('case_hash')
                   or not row.get('result_hash')
                   for case_id, row in observed.items())):
        return {**base, 'status': 'blocked', 'reason_code': 'CASE_EVIDENCE_INVALID'}
    for stage in STAGES:
        selected = [row for row in cases if row['stage'] == stage]
        matched = [observed[row['case_id']] for row in selected if row['case_id'] in observed]
        expected_score = {'case_count': len(selected), 'observed_count': len(matched),
                          'passed_count': sum(row.get('passed') is True for row in matched),
                          'pass_rate': sum(row.get('passed') is True for row in matched) / len(selected)
                                       if selected else None,
                          'coverage': len(matched) / len(selected) if selected else 0}
        if report.get('stages', {}).get(stage) != expected_score:
            return {**base, 'status': 'blocked', 'reason_code': 'SCORE_MISMATCH'}
    if not report.get('model_revision') or not report.get('host_version'):
        return {**base, 'reason_code': 'REVISION_EVIDENCE_MISSING'}
    thresholds = policy.get('thresholds', {})
    if set(thresholds) != set(STAGES) or not isinstance(policy.get('version'), str):
        return {**base, 'status': 'blocked', 'reason_code': 'VALIDATION_POLICY_INVALID'}
    for stage in STAGES:
        limit = thresholds[stage]
        if (type(limit.get('min_cases')) is not int or limit['min_cases'] < 1
                or type(limit.get('min_pass_rate')) not in (int, float)
                or not 0 < limit['min_pass_rate'] <= 1):
            return {**base, 'status': 'blocked', 'reason_code': 'VALIDATION_POLICY_INVALID'}
        score = report.get('stages', {}).get(stage, {})
        if score.get('case_count', 0) < limit['min_cases'] or score.get('coverage', 0) < 1:
            return {**base, 'reason_code': 'STAGE_COVERAGE_MISSING', 'stage': stage}
        if score.get('pass_rate', 0) < limit['min_pass_rate']:
            return {**base, 'status': 'blocked', 'reason_code': 'THRESHOLD_FAILED', 'stage': stage}
    return {**base, 'status': 'eligible', 'reason_code': 'REPRESENTATIVE_EVAL_PASSED'}
