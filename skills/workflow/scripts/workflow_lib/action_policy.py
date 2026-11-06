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
    if run.get('status') in {'complete', 'delivered', 'discarded'}:
        raise WorkflowError('SCOPE_TERMINAL', 'Terminal scopes cannot adopt a new contract.')
    if (authorization.get('approved') is not True or not authorization.get('actor_id')
            or authorization.get('run_id') != run.get('id')
            or authorization.get('state_version') != run.get('state_version')):
        raise WorkflowError('ENFORCEMENT_AUTHORIZATION_REQUIRED', 'Approve the exact current run version.')
    selected = enforcement_version(run)
    if selected is not None:
        raise WorkflowError('ENFORCEMENT_ALREADY_SELECTED', 'Existing contracts require an explicit migration; adoption cannot downgrade or reset them.')
    if any(row.get('status') not in {'completed', 'failed', 'reconciled'}
           for row in run.get('effects', {}).values()):
        raise WorkflowError('WORKER_ACTIVE', 'Reconcile active or uncertain effect reservations before adoption.')
    if run.get('active_attempt') or any(row.get('status') in {'running', 'claimed', 'launching', 'uncertain'}
            for row in list(run.get('native_invocations', {}).values()) + run.get('repair_cycles', [])):
        raise WorkflowError('WORKER_ACTIVE', 'Stop and reconcile active work before adoption.')
    updated = deepcopy(run)
    updated['enforcement'] = {'protocol':'devflow.python-enforcement/v1', 'policy_version': 1, 'authorization': deepcopy(authorization)}
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


def enforcement_version(subject: dict):
    policy = subject.get('enforcement')
    if not isinstance(policy, dict): return None
    protocol = policy.get('protocol')
    if protocol == 'devflow.python-enforcement/v1':
        value = policy.get('policy_version')
        return value if type(value) is int else 'unsupported-policy'
    if isinstance(protocol, str) and protocol.startswith('devflow.python-enforcement/'):
        return 'unsupported:' + protocol
    return None


def subject_decision(subject: dict, action: str, scope: dict) -> dict:
    selected = enforcement_version(subject)
    from .review_policy import review_version, require_review_policy
    review_selected = review_version(subject)
    review_context = {}
    if review_selected is not None:
        try:
            require_review_policy(subject)
            if selected != 1:
                raise WorkflowError('REVIEW_POLICY_BLOCKED', 'Shared enforcement required for selected review policy.')
        except WorkflowError:
            return evaluate_action(action, scope, {'policy_version':'unsupported-review-policy'})
        review_context = {'review_policy_hash':digest(subject['review_policy']),
                          'risk_hash':digest({'assessments':subject.get('risk_assessments', {}),'escalations':subject.get('review_risk_escalations',[])}),
                          'implementation_contract_hash':digest(subject.get('implementation_contracts', {}))}
    if review_selected is not None and action=='dispatch':
        review_context.update(finding_index_hash=digest(subject.get('finding_index',{})),
                              fix_rationale_hash=digest(subject.get('fix_rationales',{})))
    if selected is None:
        return evaluate_action(action, scope, {'policy_version': None})
    from .clarifications import clarification_blockers, clarification_binding
    blockers = clarification_blockers(subject, scope) if action != 'review-report' else []
    implementation = None
    if review_selected is not None and action == 'dispatch':
        from .implementation_contracts import implementation_prerequisites, rationale_current
        implementation = implementation_prerequisites(subject,scope)
        if scope.get('purpose')=='repair':
            missing=[f for f in scope.get('finding_ids',[]) if not rationale_current(subject,f)]
            if not scope.get('finding_ids') or missing:
                implementation={**implementation,'status':'block',
                    'reason_codes':implementation['reason_codes']+['FIX_RATIONALE_REQUIRED']}
        blockers.extend({'id':'contract:'+code,'version':1,'reason_code':code}
                        for code in implementation['reason_codes'])
    if action in {'completion', 'delivery','finding'}:
        active = {**subject.get('effects',{}),**{'tool:'+k:v for k,v in subject.get('active_executions',{}).items()}, **{'execution:'+k:v for k,v in subject.get('executions',{}).items()}}
        for identifier, effect in active.items():
            if effect.get('status') not in {'completed', 'failed', 'reconciled'}:
                item_id = effect.get('action_scope', {}).get('item_id')
                synthetic = {'id': 'effect:' + identifier, 'version': 1, 'status': 'pending',
                             'scope': [item_id] if item_id else None}
                affected = clarification_blockers({**subject, 'clarifications': {synthetic['id']: synthetic}}, scope)
                blockers.extend(affected)

    decision = evaluate_action(action, scope, {
        **review_context,
        'policy_version': selected,
        'state_version': subject.get('state_version'),
        'policy_hash': digest(subject.get('enforcement', {})),
        'questions_hash': clarification_binding(subject, scope),
        'source_identity': subject.get('source_identity'),
        'spec_hash': subject.get('plan', {}).get('spec_hash'),
        **({'review_contract_hash': subject['review_contract_hash']} if subject.get('review_contract_hash') else {}),
        'required_evidence': [row['id'] for row in blockers], 'evidence': {}})
    if implementation and implementation['status']=='block':decision['implementation_prerequisites']=implementation
    return decision


def validate_authority_patch(data: dict, kind: str, payload: dict) -> None:
    if data.get('enforcement_guard') != {'protocol': 'devflow.python-enforcement/v1', 'schema_version': 1}: return
    reserved = {'runs', 'host_bindings', 'host_tasks', 'domain_receipts', 'enforcement_guard',
                'spec', 'spec_pair', 'approval', 'spec_approval_invalidated', 'plan', 'plan_validation',
                'context', 'context_hash', 'resolved_context', 'resolved_context_source_hash',
                'repositories', 'governing_input_receipt', 'governing_reassessment_required',
                'model_policy', 'routing_policy', 'document_approvals', 'document_proposals'}
    allowed = {
        'context.layer.set': {'context', 'context_hash', 'resolved_context'},
        'context.resolved': {'resolved_context', 'resolved_context_source_hash'},
        'context.resolution.recorded': {'resolved_context', 'resolved_context_source_hash'},
        'repo.registered': {'repositories'}, 'spec.stored': {'spec', 'spec_pair'},
        'spec.approved': {'approval', 'spec_approval_invalidated'},
        'plan.validated': {'plan', 'plan_validation'}, 'document.approved': {'approval'},
    }.get(kind, set())
    if kind=='context.layer.set' and payload.get('resolved_context') is not None:
        raise WorkflowError('ENFORCEMENT_TRANSITION_REQUIRED','Context edits may revoke resolution, never assert resolved authority.')
    if (set(payload) & reserved) - allowed:
        raise WorkflowError('ENFORCEMENT_TRANSITION_REQUIRED', 'Use the validated transition; generic patches cannot replace enforcement authority or history.')
