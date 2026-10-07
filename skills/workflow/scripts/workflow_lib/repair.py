"""Read-only repair delta and next-action decisions from journaled evidence."""

from __future__ import annotations

import hashlib
import json

from .gates import gate_status


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def failure_delta(run: dict) -> dict:
    """Return stable IDs for unresolved findings and failed or missing proof."""
    findings = [row for row in run.get('unresolved_findings', [])
                if row.get('status') not in {'resolved', 'waived'}]
    finding_ids = sorted({row['id'] for row in findings if isinstance(row.get('id'), str) and row['id']})
    item_ids = {row['item_id'] for row in findings
                if isinstance(row.get('item_id'), str) and row['item_id']}
    for item_id, state in run.get('items', {}).items():
        attempts = state.get('attempts', [])
        if attempts and attempts[-1].get('result') and attempts[-1]['result'].get('outcome') != 'passed':
            item_ids.add(item_id)
    gate_ids = []
    missing_gate_ids = []
    for gate_id in run.get('required_hardening_gates', []):
        proof = run.get('hardening_proofs', {}).get(gate_id)
        if not proof or proof.get('config_hash') != run.get('hardening_config_hash'):
            gate_ids.append(gate_id)
            missing_gate_ids.append(gate_id)
        elif proof.get('passed') is not True:
            gate_ids.append(gate_id)
    delta = {'finding_ids': finding_ids, 'gate_ids': sorted(set(gate_ids)),
             'item_ids': sorted(item_ids), 'missing_gate_ids': sorted(set(missing_gate_ids))}
    return {**delta, 'digest': _digest(delta)}


def repair_decision(run: dict, now_ms: int) -> dict:
    """Describe one next repair action without claiming or launching work."""
    delta = failure_delta(run)
    policy = run.get('repair_policy', {})
    cycles = run.get('repair_cycles', [])
    max_attempts = policy.get('max_attempts', 0)
    remaining = {'attempts': max(0, max_attempts - len(cycles)),
                 'elapsed_ms': max(0, now_ms - run.get('repair_started_ms', now_ms)),
                 'estimated_cost': sum(row.get('estimated_cost', 0) for row in cycles)}
    scope = {key: delta[key] for key in ('finding_ids', 'gate_ids', 'item_ids', 'missing_gate_ids')}
    scope['implementer_actor'] = run.get('actors', {}).get('implementer')
    base = {'scope': scope, 'delta_hash': delta['digest'], 'remaining': remaining}
    if run.get('status') != 'active':
        return {**base, 'status': 'blocked', 'reason_code': 'RUN_NOT_ACTIVE'}
    if not delta['finding_ids'] and not delta['gate_ids'] and not delta['item_ids']:
        stage = gate_status(run, live=False)
        return {**base, 'status': 'complete' if stage.get('stage') == 'delivery' else 'blocked',
                'reason_code': 'ALL_CHECKS_PASS' if stage.get('stage') == 'delivery' else 'AWAITING_STAGE'}
    if not policy.get('enabled'):
        return {**base, 'status': 'blocked', 'reason_code': 'REPAIR_DISABLED'}
    if not scope['implementer_actor']:
        return {**base, 'status': 'blocked', 'reason_code': 'IMPLEMENTER_UNAVAILABLE'}
    if (not delta['finding_ids'] and not delta['item_ids']
            and set(delta['gate_ids']) == set(delta['missing_gate_ids'])):
        return {**base, 'status': 'blocked', 'reason_code': 'VERIFICATION_UNAVAILABLE'}
    return {**base, 'status': 'ready', 'reason_code': 'REPAIR_AVAILABLE'}
