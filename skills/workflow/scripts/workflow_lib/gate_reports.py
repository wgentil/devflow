"""Small, host-neutral contracts for configured hardening reports."""

from __future__ import annotations

import hashlib
import json

MAX_REPORT_BYTES = 1_048_576


def normalize_contract(config: dict) -> dict:
    """Return the configured contract, preserving legacy exit-status gates."""
    if not isinstance(config, dict):
        raise ValueError('gate configuration must be an object')
    value = config.get('contract', {'kind': 'exit-status'})
    if not isinstance(value, dict):
        raise ValueError('gate contract must be an object')
    kind = value.get('kind')
    if kind == 'exit-status' and set(value) == {'kind'}:
        return {'kind': kind}
    if kind == 'json-report' and type(value.get('version')) is int and value['version'] == 1 and set(value) == {'kind', 'version'}:
        return {'kind': kind, 'version': 1}
    raise ValueError('unsupported gate report contract')


def parse_gate_report(contract: dict, stdout: str, stderr: str, exit_code: int) -> dict:
    """Validate a captured result before it can become passing gate evidence."""
    try:
        selected = normalize_contract({'contract': contract})
    except ValueError:
        return {'passed': False, 'failure': 'REPORT_SCHEMA_INVALID'}
    if exit_code != 0:
        return {'passed': False, 'failure': 'GATE_FAILED'}
    if selected['kind'] == 'exit-status':
        return {'passed': True, 'failure': None, 'contract': selected}
    body = stdout.strip()
    if not body:
        return {'passed': False, 'failure': 'REPORT_MISSING', 'contract': selected}
    if len(stdout.encode('utf-8')) > MAX_REPORT_BYTES:
        return {'passed': False, 'failure': 'REPORT_INVALID', 'contract': selected}
    try:
        report = json.loads(body)
    except json.JSONDecodeError:
        return {'passed': False, 'failure': 'REPORT_INVALID', 'contract': selected}
    findings = report.get('findings') if isinstance(report, dict) else None
    if not isinstance(findings, list) or any(
        not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'].strip()
        for item in findings
    ):
        return {'passed': False, 'failure': 'REPORT_SCHEMA_INVALID', 'contract': selected}
    return {
        'passed': not findings,
        'failure': 'GATE_FINDINGS' if findings else None,
        'contract': selected,
        'report_hash': hashlib.sha256(stdout.encode('utf-8')).hexdigest(),
        'finding_count': len(findings),
        'finding_ids': sorted(item['id'] for item in findings),
    }
