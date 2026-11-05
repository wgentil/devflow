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


def validate_effect_policy(policy: dict) -> None:
    _require(isinstance(policy, dict) and set(policy) - {'max_probe_attempts'} == {
        'max_attempts', 'max_estimated_cost', 'max_elapsed_ms'}, 'Explicit effect limit fields required.')
    _require(type(policy['max_attempts']) is int and policy['max_attempts'] > 0
        and _number(policy['max_estimated_cost']) and _number(policy['max_elapsed_ms'])
        and policy['max_elapsed_ms'] > 0
        and type(policy.get('max_probe_attempts', 0)) is int and policy.get('max_probe_attempts', 0) >= 0, 'Explicit finite effect limits required.')


def claim_effect(subject: dict, request: dict) -> dict:
    identifier = request.get('effect_id')
    _require(isinstance(identifier, str) and identifier.strip() and request.get('scope'), 'Unique effect identity and scope required.')
    prior = subject.get('effects', {}).get(identifier)
    if prior:
        _require(prior['request_hash'] == digest(request), 'Effect identity belongs to a different request.')
        return deepcopy(subject)
    if subject.get('review_contract_hash'):
        purpose=request.get('action_scope',{}).get('purpose')
        _require(purpose in {'review','repair','probe'} and isinstance(request.get('actor_id'),str) and request['actor_id'], 'Declare standalone worker purpose and actor.')
        if purpose=='repair':
            _require(subject.get('repair_authorization') and request['actor_id']==subject.get('actors',{}).get('implementer'), 'Explicit exact-scope repair authorization required.')
        else:_require(request['actor_id']!=subject.get('actors',{}).get('implementer'), 'Review/probe actor must be independent of repairs.')
    decision_action = ('review-report' if request.get('owner_binding', {}).get('role') in {
        'item-reviewer', 'branch-reviewer', 'acceptance-reviewer', 'pr-reviewer'} or subject.get('review_contract_hash') and request.get('action_scope',{}).get('purpose') in {'review','probe'} else 'dispatch')
    require_action(subject_decision(subject, decision_action, request.get('action_scope', {})))
    policy = subject.get('effect_policy', {})
    _require(type(policy.get('max_attempts')) is int and policy['max_attempts'] > 0
             and _number(policy.get('max_estimated_cost')) and _number(policy.get('max_elapsed_ms')),
             'Explicit finite effect limits required.')
    cost, now = request.get('estimated_cost'), request.get('now_ms')
    _require(_number(cost) and type(now) is int and now >= 0, 'Known finite cost and time required.')
    effects = subject.get('effects', {})
    kind = request.get('effect_kind', 'work')
    _require(kind in {'work', 'probe'}, 'Known effect attempt category required.')
    limit = policy.get('max_probe_attempts', 0) if kind == 'probe' else policy['max_attempts']
    _require(type(limit) is int and sum(row.get('effect_kind', 'work') == kind for row in effects.values()) < limit, kind + ' attempt limit reached.')
    _require(sum(max(row['estimated_cost'], row.get('observed_cost', 0)) for row in effects.values()) + cost <= policy['max_estimated_cost'], 'Cost reservation limit reached.')
    _require(sum(row.get('observed_cost', 0) for row in effects.values()) <= policy['max_estimated_cost'], 'Observed spending limit exceeded.')
    _require(now - subject.get('effects_started_ms', now) < policy['max_elapsed_ms'], 'Elapsed limit reached.')
    _require(not any(row['scope'] == request['scope'] and row['status'] not in {'completed', 'failed', 'reconciled'}
                     for row in effects.values()), 'Scope has an active or uncertain worker.')
    _require(request.get('source_identity') and request['source_identity'] == subject.get('source_identity'), 'Current source required.')
    updated = deepcopy(subject)
    decision = subject_decision(subject, decision_action, request.get('action_scope', {}))
    updated.setdefault('effects', {})[identifier] = {
        'effect_id': identifier, 'request_hash': digest(request), 'scope': request['scope'],
        **({'owner_pid':request['owner_pid']} if 'owner_pid' in request else {}),
        'estimated_cost': cost, 'claimed_at_ms': now, 'status': 'claimed', 'effect_kind': kind,
        **({'client_request_hash': request['client_request_hash']} if 'client_request_hash' in request else {}),
        'source_identity': request['source_identity'], 'decision': decision, 'decision_action': decision_action,
        'action_scope': deepcopy(request.get('action_scope', {})),
        'effect_policy_hash': digest(policy), 'history': [],
        **({'owner_binding': deepcopy(request['owner_binding'])} if 'owner_binding' in request else {})}
    updated.setdefault('effects_started_ms', now)
    return updated


def validate_launch_receipt(subject: dict, receipt: dict, observation: dict) -> dict:
    _require(receipt.get('status') == 'claimed' and subject.get('effects', {}).get(receipt.get('effect_id')) == receipt,
             'Current claimed effect required.')
    return _dispatch_facts(subject, receipt, observation)


def _dispatch_facts(subject: dict, receipt: dict, observation: dict) -> dict:
    decision = subject_decision(subject, receipt.get('decision_action', 'dispatch'), receipt.get('action_scope', {}))
    require_action(decision)
    now_ms = observation.get('now_ms')
    policy = subject.get('effect_policy', {})
    _require(type(now_ms) is int and now_ms >= receipt['claimed_at_ms']
             and now_ms - subject['effects_started_ms'] < policy.get('max_elapsed_ms', 0),
             'Reservation elapsed limit reached or current time unavailable.')
    _require(receipt.get('effect_policy_hash') == digest(policy), 'Effect policy changed after reservation.')
    _require(decision == receipt['decision'] and observation.get('source_identity') == receipt['source_identity']
             == subject.get('source_identity'), 'Launch inputs changed since reservation.')
    return decision


def validate_active_dispatch(subject: dict, effect_id: str, observation: dict) -> dict:
    receipt = subject.get('effects', {}).get(effect_id, {})
    _require(receipt.get('status') == 'launching', 'Current launching effect required.')
    return _dispatch_facts(subject, receipt, observation)


def transition_effect(subject: dict, request: dict) -> dict:
    effect = subject.get('effects', {}).get(request.get('effect_id'))
    _require(effect, 'Known effect required.')
    target = request.get('status')
    allowed = {'claimed': {'launching', 'failed'}, 'launching': {'running', 'uncertain', 'failed'},
               'running': {'completed', 'failed', 'uncertain'}, 'uncertain': {'reconciled'},
               'completed': set(), 'failed': set(), 'reconciled': set()}
    _require(target in allowed.get(effect['status'], set()), 'Invalid effect transition; uncertain launches require reconciliation.')
    _require(type(request.get('now_ms')) is int and request['now_ms'] >= max([effect['claimed_at_ms']] + [row['now_ms'] for row in effect.get('history', [])]), 'Valid transition time required.')
    if effect['status'] == 'launching' and target == 'failed':
        _require(request.get('dispatch_started') is False, 'Known non-dispatch observation required.')
    if target == 'launching':
        validate_launch_receipt(subject, effect, {'source_identity': subject.get('source_identity'), 'now_ms': request['now_ms']})
    if target == 'reconciled':
        proof = request.get('termination_receipt', {})
        observation = subject.get('worker_termination_observations', {}).get(request.get('termination_observation_id'))
        _require(observation and proof == observation
                 and observation.get('effect_id') == effect['effect_id']
                 and observation.get('worker_ref') == effect.get('worker_ref')
                 and observation.get('basis') == 'os-owner-stopped' and observation.get('worker_ref')
                 and observation.get('evidence_refs'),
                 'Recorded adapter termination observation required; a caller-supplied stop claim is insufficient.')
    if target in {'running', 'completed'}:
        _require(request.get('worker_ref') or effect.get('worker_ref'), 'Exact worker reference required.')
    updated = deepcopy(subject); row = updated['effects'][effect['effect_id']]
    row['history'].append({'from': effect['status'], 'to': target, 'now_ms': request['now_ms']})
    row['status'] = target
    if request.get('worker_ref'): row['worker_ref'] = request['worker_ref']
    if 'observed_cost' in request:
        _require(_number(request['observed_cost']) and request['observed_cost'] >= effect.get('observed_cost', 0), 'Finite nondecreasing observed usage cost required.')
        row['observed_cost'] = request['observed_cost']
    return updated
