"""Pure, versioned action authorization. No live observations during replay."""
from copy import deepcopy
import json
from .document_units import digest
from .store import WorkflowError

ACTIONS = frozenset({'attempt', 'dispatch', 'proof', 'finding', 'completion', 'delivery', 'review-report'})


def evaluate_action(action: str, scope: dict, context: dict) -> dict:
    if not isinstance(scope, dict) or not isinstance(context, dict):
        raise WorkflowError('INVALID_ACTION_CONTEXT', 'Object scope and context required.')
    required = context.get('required_evidence', [])
    if (not isinstance(required, list) or any(not isinstance(i, str) or not i for i in required)
            or not isinstance(context.get('evidence', {}), dict)):
        raise WorkflowError('INVALID_ACTION_CONTEXT', 'Evidence IDs and facts must be structured.')
    try:
        raw = json.dumps({'action': action, 'scope': scope, 'context': context}, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise WorkflowError('INVALID_ACTION_CONTEXT', 'Finite JSON context required.') from exc
    if len(raw.encode('utf-8')) > 262144:
        raise WorkflowError('ACTION_CONTEXT_LIMIT', 'Scope the action context below 256 KiB.')
    binding = digest({'action': action, 'scope': scope, 'context': context})
    result = {'schema_version': 1, 'action': action, 'scope': deepcopy(scope),
              'policy_version': context.get('policy_version'),
              'state_version': context.get('state_version'), 'context_hash': binding,
              'status': 'allow', 'reason_codes': [], 'blocker_ids': [], 'recovery': []}
    if context.get('policy_version') is None:
        return {**result, 'status': 'not-applicable'}
    reasons, blockers = [], []
    if type(context.get('policy_version')) is not int or context['policy_version'] != 1:
        reasons.append('UNSUPPORTED_POLICY')
    if action not in ACTIONS:
        reasons.append('UNSUPPORTED_ACTION')
    evidence = context.get('evidence', {})
    for identifier in context.get('required_evidence', []):
        if evidence.get(identifier) is not True:
            blockers.append(identifier)
    if blockers:
        reasons.append('REQUIRED_EVIDENCE_MISSING')
    if reasons:
        result.update(status='block', reason_codes=reasons, blocker_ids=blockers[:100],
                      omitted_blocker_count=max(0, len(blockers)-100),
                      recovery=['Supply current required evidence or resolve the reported policy/action error.'])
    return result


def require_action(decision: dict) -> None:
    if decision.get('status') not in {'allow', 'not-applicable'}:
        raise WorkflowError('ACTION_BLOCKED', ', '.join(decision.get('reason_codes', [])))


def adopt_enforcement(run: dict, authorization: dict) -> dict:
    if (authorization.get('approved') is not True or not authorization.get('actor_id')
            or authorization.get('run_id') != run.get('id')
            or authorization.get('state_version') != run.get('state_version')):
        raise WorkflowError('ENFORCEMENT_AUTHORIZATION_REQUIRED', 'Approve the exact current run version.')
    if run.get('active_attempt') or any(row.get('status') in {'running', 'claimed', 'uncertain'}
            for row in list(run.get('native_invocations', {}).values()) + run.get('repair_cycles', [])):
        raise WorkflowError('WORKER_ACTIVE', 'Stop and reconcile active work before adoption.')
    updated = deepcopy(run)
    updated['enforcement'] = {'policy_version': 1, 'authorization': deepcopy(authorization)}
    for collection in ('verification_proofs', 'verifier_proofs', 'hardening_proofs'):
        for proof in updated.get(collection, {}).values():
            proof['fresh'] = False
            proof['passed'] = False
    for reviews in updated.get('reviews', {}).values():
        for review in reviews:
            review['fresh'] = False
    for acceptance in updated.get('acceptances', []):
        acceptance['fresh'] = False
    updated['state_version'] = run.get('state_version', 0) + 1
    return updated


def subject_decision(subject: dict, action: str, scope: dict) -> dict:
    policy = subject.get('enforcement')
    if not isinstance(policy, dict) or policy.get('policy_version') is None:
        return evaluate_action(action, scope, {'policy_version': None})
    from .clarifications import clarification_blockers
    blockers = clarification_blockers(subject, scope) if action != 'review-report' else []
    return evaluate_action(action, scope, {
        'policy_version': subject.get('enforcement', {}).get('policy_version'),
        'state_version': subject.get('state_version'),
        'policy_hash': digest(subject.get('enforcement', {})),
        'questions_hash': digest(subject.get('clarifications', {})),
        'source_identity': subject.get('source_identity'),
        'spec_hash': subject.get('plan', {}).get('spec_hash'),
        'required_evidence': [row['id'] for row in blockers], 'evidence': {}})
