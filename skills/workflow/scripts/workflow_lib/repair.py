"""Read-only repair delta and next-action decisions from journaled evidence."""

from __future__ import annotations

import hashlib
import json

from .gates import gate_status


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def failure_delta(run: dict) -> dict:
    """Return stable IDs for unresolved findings and failed or missing proof."""
    from .review_policy import review_version
    disposed={'resolved','waived','rejected','deferred'} if review_version(run) is not None else {'resolved','waived'}
    findings = [row for row in run.get('unresolved_findings', []) if row.get('status') not in disposed]
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
    if run.get('review_orchestration'):
        from .review_orchestration import orchestration_next
        return orchestration_next(run,now_ms)
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
    from .action_policy import subject_decision
    scopes = [{'item_id': item_id} for item_id in scope['item_ids']] or [{}]
    decisions = [subject_decision(run, 'dispatch', item_scope) for item_scope in scopes]
    blocked = next((d for d in decisions if d['status'] == 'block'), None)
    if blocked:
        from .clarifications import current_questions
        return {**base, 'status': 'blocked', 'reason_code': 'ACTION_BLOCKED', 'policy_decision': blocked,
            'questions':[q for q in current_questions(run,{}) if q.get('id') in blocked.get('blocker_ids',[])]}
    if run.get('status') != 'active':
        return {**base, 'status': 'blocked', 'reason_code': 'RUN_NOT_ACTIVE'}
    if not delta['finding_ids'] and not delta['gate_ids'] and not delta['item_ids']:
        stage = gate_status(run, live=False)
        return {**base, 'status': 'complete' if stage.get('stage') == 'delivery' else 'blocked',
                'reason_code': 'ALL_CHECKS_PASS' if stage.get('stage') == 'delivery' else 'AWAITING_STAGE'}
    if run.get('repair_stop'):
        return {**base, 'status': 'blocked', 'reason_code': run['repair_stop']['reason_code']}
    if not policy.get('enabled'):
        return {**base, 'status': 'blocked', 'reason_code': 'REPAIR_DISABLED'}
    if run.get('repair_human_decision_required'):
        return {**base, 'status': 'blocked', 'reason_code': 'HUMAN_DECISION'}
    if any(row.get('status') == 'claimed' for row in cycles):
        return {**base, 'status': 'blocked', 'reason_code': 'REPAIR_LEASE_ACTIVE'}
    if len(cycles) >= max_attempts:
        return {**base, 'status': 'blocked', 'reason_code': 'ATTEMPT_LIMIT'}
    if remaining['elapsed_ms'] >= policy.get('max_elapsed_ms', 0):
        return {**base, 'status': 'blocked', 'reason_code': 'TIME_LIMIT'}
    if remaining['estimated_cost'] >= policy.get('max_estimated_cost', 0):
        return {**base, 'status': 'blocked', 'reason_code': 'SPEND_LIMIT'}
    window = policy.get('no_progress_window', 2)
    recent = cycles[-window:]
    if len(recent) == window and all(row.get('status') == 'recorded'
            and row.get('input_delta_hash') == row.get('output_delta_hash') == delta['digest']
            for row in recent):
        return {**base, 'status': 'blocked', 'reason_code': 'NO_PROGRESS'}
    if not scope['implementer_actor']:
        return {**base, 'status': 'blocked', 'reason_code': 'IMPLEMENTER_UNAVAILABLE'}
    if (not delta['finding_ids'] and not delta['item_ids']
            and set(delta['gate_ids']) == set(delta['missing_gate_ids'])):
        return {**base, 'status': 'blocked', 'reason_code': 'VERIFICATION_UNAVAILABLE'}
    return {**base, 'status': 'ready', 'reason_code': 'REPAIR_AVAILABLE'}
