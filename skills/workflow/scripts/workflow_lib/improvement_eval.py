"""Execute approved cases and compare candidate workflow revisions."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time

from .store import WorkflowError


def run_candidate_cases(candidate: dict, cases: list[dict], cwd: Path) -> dict:
    if not isinstance(candidate.get('artifact_hash'), str) or not candidate['artifact_hash']:
        raise WorkflowError('CANDIDATE_REQUIRED', 'candidate artifact hash required')
    rows = []
    for case in cases:
        if not case.get('approved_by'):
            raise WorkflowError('CASE_NOT_APPROVED', 'only reviewed cases can execute')
        command = case.get('command')
        if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
            raise WorkflowError('INVALID_CASE', 'case argv required')
        started = time.monotonic()
        try:
            result = subprocess.run(command, cwd=Path(cwd), capture_output=True,
                                    timeout=case.get('timeout_seconds', 60), check=False)
            observed = json.loads(result.stdout.decode("utf-8"))
            passed = result.returncode == 0 and isinstance(observed, dict) and all(
                observed.get(key) == value for key, value in case['expected'].items())
            outcome = 'passed' if passed else 'failed'
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, KeyError):
            passed, outcome = False, 'unavailable'
        rows.append({'case_id': case['case_id'], 'case_hash': case['case_hash'],
                     'scoring_version': case['scoring_version'], 'passed': passed,
                     'outcome': outcome, 'elapsed_ms': max(0, int((time.monotonic() - started) * 1000))})
    return {'artifact_hash': candidate['artifact_hash'], 'case_results': rows,
            'usage_status': 'unknown', 'usage': None}


def compare_candidate(baseline: dict, candidate: dict, cases: list[dict]) -> dict:
    expected = {row['case_id']: (row['case_hash'], row['scoring_version']) for row in cases
                if row.get('approved_by')}
    if len(expected) != len(cases):
        raise WorkflowError('CASE_NOT_APPROVED', 'all compared cases need approval')
    def validate(result):
        rows = result.get('case_results', [])
        seen = {row.get('case_id'): (row.get('case_hash'), row.get('scoring_version')) for row in rows}
        if len(rows) != len(seen) or seen != expected:
            raise WorkflowError('CASE_SET_MISMATCH', 'baseline and candidate must use the same case hashes and scoring versions')
        return {row['case_id']: row for row in rows}
    left, right = validate(baseline), validate(candidate)
    count = len(expected)
    if not count:
        raise WorkflowError('CASE_SET_EMPTY', 'approved case set required')
    left_pass = sum(row.get('passed') is True for row in left.values()) / count
    right_pass = sum(row.get('passed') is True for row in right.values()) / count
    coverage = {'baseline': sum(row.get('outcome') != 'unavailable' for row in left.values()) / count,
                'candidate': sum(row.get('outcome') != 'unavailable' for row in right.values()) / count}
    both_usage = (baseline.get('usage_status') == candidate.get('usage_status') == 'reported'
                  and isinstance(baseline.get('usage'), dict) and isinstance(candidate.get('usage'), dict))
    token_delta = None
    if both_usage:
        keys = ('input_tokens', 'cached_tokens', 'output_tokens')
        if all(type(result['usage'].get(key)) is int for result in (baseline, candidate) for key in keys):
            token_delta = {key: candidate['usage'][key] - baseline['usage'][key] for key in keys}
    return {'case_ids': sorted(expected), 'baseline_pass_rate': left_pass,
            'candidate_pass_rate': right_pass, 'quality_delta': right_pass - left_pass,
            'coverage': coverage, 'elapsed_ms': {
                'baseline': sum(row.get('elapsed_ms', 0) for row in left.values()),
                'candidate': sum(row.get('elapsed_ms', 0) for row in right.values())},
            'usage_status': 'reported' if token_delta is not None else 'unknown',
            'token_delta': token_delta, 'cost_status': 'unknown',
            'per_case': [{'case_id': identifier, 'baseline': left[identifier].get('outcome'),
                          'candidate': right[identifier].get('outcome')}
                         for identifier in sorted(expected)]}


def retrospective(traces: list[dict], feedback: list[dict]) -> dict:
    known = {row.get('run_id') for row in traces}
    groups: dict[str, list] = {}
    for row in feedback:
        if row.get('run_id') not in known:
            continue
        owner = row.get('feedback', {}).get('owner')
        if not owner:
            continue
        groups.setdefault(owner, []).append(row)
    return {'recommendations': [{'owner': owner,
             'observations': [row['feedback']['observation'] for row in rows],
             'evidence_refs': sorted({reference for row in rows for reference in
                               ('feedback:' + row['feedback_id'], 'trace:' + row['trace_hash'])})}
             for owner, rows in sorted(groups.items())]}
