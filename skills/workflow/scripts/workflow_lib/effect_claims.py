"""Pure effect reservation transitions, committed by the caller's transaction."""
from copy import deepcopy
import math
from .document_units import digest
from .action_policy import require_action, subject_decision
from .store import WorkflowError


def _require(ok, message):
    if not ok: raise WorkflowError('EFFECT_BLOCKED', message)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def claim_effect(subject: dict, request: dict) -> dict:
    identifier = request.get('effect_id')
    _require(isinstance(identifier, str) and identifier.strip() and request.get('scope'), 'Unique effect identity and scope required.')
    prior = subject.get('effects', {}).get(identifier)
    if prior:
        _require(prior['request_hash'] == digest(request), 'Effect identity belongs to a different request.')
        return deepcopy(subject)
    require_action(subject_decision(subject, 'dispatch', request.get('action_scope', {})))
    policy = subject.get('effect_policy', {})
    _require(type(policy.get('max_attempts')) is int and policy['max_attempts'] > 0
             and _number(policy.get('max_estimated_cost')) and _number(policy.get('max_elapsed_ms')),
             'Explicit finite effect limits required.')
    cost, now = request.get('estimated_cost'), request.get('now_ms')
    _require(_number(cost) and type(now) is int and now >= 0, 'Known finite cost and time required.')
    effects = subject.get('effects', {})
    _require(len(effects) < policy['max_attempts'], 'Attempt limit reached.')
    _require(sum(row['estimated_cost'] for row in effects.values()) + cost <= policy['max_estimated_cost'], 'Cost reservation limit reached.')
    _require(sum(row.get('observed_cost', 0) for row in effects.values()) <= policy['max_estimated_cost'], 'Observed spending limit exceeded.')
    _require(now - subject.get('effects_started_ms', now) < policy['max_elapsed_ms'], 'Elapsed limit reached.')
    _require(not any(row['scope'] == request['scope'] and row['status'] not in {'completed', 'failed', 'reconciled'}
                     for row in effects.values()), 'Scope has an active or uncertain worker.')
    _require(request.get('source_identity') and request['source_identity'] == subject.get('source_identity'), 'Current source required.')
    updated = deepcopy(subject)
    decision = subject_decision(subject, 'dispatch', request.get('action_scope', {}))
    updated.setdefault('effects', {})[identifier] = {
        'effect_id': identifier, 'request_hash': digest(request), 'scope': request['scope'],
        'estimated_cost': cost, 'claimed_at_ms': now, 'status': 'claimed',
        'source_identity': request['source_identity'], 'decision': decision,
        'action_scope': deepcopy(request.get('action_scope', {})), 'history': []}
    updated.setdefault('effects_started_ms', now)
    return updated


def validate_launch_receipt(subject: dict, receipt: dict, observation: dict) -> dict:
    _require(receipt.get('status') == 'claimed' and subject.get('effects', {}).get(receipt.get('effect_id')) == receipt,
             'Current claimed effect required.')
    decision = subject_decision(subject, 'dispatch', receipt.get('action_scope', {}))
    require_action(decision)
    _require(decision == receipt['decision'] and observation.get('source_identity') == receipt['source_identity']
             == subject.get('source_identity'), 'Launch inputs changed since reservation.')
    return decision


def transition_effect(subject: dict, request: dict) -> dict:
    effect = subject.get('effects', {}).get(request.get('effect_id'))
    _require(effect, 'Known effect required.')
    target = request.get('status')
    allowed = {'claimed': {'launching', 'failed'}, 'launching': {'running', 'uncertain'},
               'running': {'completed', 'failed', 'uncertain'}, 'uncertain': {'reconciled'},
               'completed': set(), 'failed': set(), 'reconciled': set()}
    _require(target in allowed.get(effect['status'], set()), 'Invalid effect transition; uncertain launches require reconciliation.')
    _require(type(request.get('now_ms')) is int and request['now_ms'] >= effect['claimed_at_ms'], 'Valid transition time required.')
    if target == 'launching':
        validate_launch_receipt(subject, effect, {'source_identity': subject.get('source_identity')})
    if target == 'reconciled':
        proof = request.get('termination_receipt', {})
        _require(proof.get('effect_id') == effect['effect_id'] and proof.get('worker_ref') == effect.get('worker_ref')
                 and proof.get('basis') == 'os-owner-stopped' and proof.get('worker_ref'), 'Actual worker termination evidence required.')
    if target in {'running', 'completed'}:
        _require(request.get('worker_ref') or effect.get('worker_ref'), 'Exact worker reference required.')
    updated = deepcopy(subject); row = updated['effects'][effect['effect_id']]
    row['history'].append({'from': effect['status'], 'to': target, 'now_ms': request['now_ms']})
    row['status'] = target
    if request.get('worker_ref'): row['worker_ref'] = request['worker_ref']
    if 'observed_cost' in request:
        _require(_number(request['observed_cost']), 'Finite observed usage cost required.')
        row['observed_cost'] = request['observed_cost']
    return updated
