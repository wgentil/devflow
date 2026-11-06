"""Versioned adversarial-review requirements. Pure policy, never dispatch or live I/O."""
from copy import deepcopy
import json
from .action_policy import adopt_enforcement, enforcement_version
from .clarifications import clarification_binding
from .document_units import digest
from .store import WorkflowError

PROTOCOL = 'devflow.adversarial-review/v1'
PERSPECTIVES = ('code', 'test', 'architecture', 'security')
ARCHITECTURE = frozenset({'boundaries', 'interfaces', 'data-model', 'migration', 'cross-component',
                          'dependencies', 'operational-design'})
SECURITY = frozenset({'trust-boundary', 'permissions', 'authentication', 'sensitive-data',
                     'secrets', 'external-input', 'dependencies', 'execution-surface'})


def _require(condition, message, code='REVIEW_POLICY_BLOCKED'):
    if not condition:
        raise WorkflowError(code, message)


def bounded(value):
    try:
        raw = json.dumps(value, allow_nan=False, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise WorkflowError('REVIEW_RECORD_INVALID', 'Finite structured review facts required.') from exc
    _require(len(raw.encode('utf-8')) <= 262144, 'Scope review facts below 256 KiB.', 'REVIEW_RECORD_LIMIT')


def new_review_policy() -> dict:
    return {'protocol': PROTOCOL, 'schema_version': 1, 'revision': 1,
            'substantive_perspectives': ['code', 'test'],
            'risk_perspectives': ['architecture', 'security'],
            'substantive_profile': 'deep-reasoning', 'substantive_effort': 'high',
            'lightweight_profile': 'fast-analysis', 'selection_order': 'configured-entry-order'}


def review_version(subject: dict):
    policy = subject.get('review_policy')
    if not isinstance(policy, dict):
        return None
    protocol = policy.get('protocol')
    if protocol == PROTOCOL:
        version = policy.get('schema_version')
        return version if type(version) is int else 'unsupported-policy'
    if isinstance(protocol, str) and protocol.startswith('devflow.adversarial-review/'):
        return 'unsupported:' + protocol
    return None


def require_review_policy(subject: dict):
    policy = subject.get('review_policy', {})
    _require(review_version(subject) == 1, 'Select the supported adversarial-review contract.')
    expected = new_review_policy()
    _require(all(policy.get(k) == v for k, v in expected.items() if k != 'revision')
             and type(policy.get('revision')) is int and policy['revision'] > 0,
             'Review policy cannot drop required perspectives or model controls.')
    bounded(policy)


def review_bindings(subject: dict, scope: dict) -> dict:
    bounded(scope)
    _require(isinstance(scope, dict), 'Review scope must be an object.')
    from .implementation_contracts import contract_binding
    return {'source_identity': subject.get('source_identity'), 'scope_hash': digest(scope),
            'policy_hash': digest(subject.get('review_policy', {})),
            'authority_hash': subject.get('review_contract_hash') or subject.get('plan', {}).get('spec_hash'),
            'plan_hash': digest(subject.get('plan', {})),
            'contract_hash': contract_binding(subject,scope),
            'questions_hash': clarification_binding(subject, {'item_id': scope['item_id']} if scope.get('item_id') else {})}


def _citation(value):
    return (isinstance(value, list) and bool(value)
            and all(isinstance(ref, str) and ref.strip() for ref in value))


def review_requirements(subject: dict, scope: dict, risk: dict) -> dict:
    bounded({'scope': scope, 'risk': risk})
    version = review_version(subject)
    base = {'schema_version': 1, 'scope': deepcopy(scope), 'required_perspectives': [],
            'exemptions': {}, 'lightweight': False, 'requires_confirmation': True}
    if version is None:
        return {**base, 'status': 'not-applicable', 'risk_status': 'legacy'}
    try:
        require_review_policy(subject)
    except WorkflowError as exc:
        return {**base, 'status': 'block', 'reason_code': exc.code, 'risk_status': 'unknown'}
    bindings = review_bindings(subject, scope)
    current = (isinstance(risk, dict) and type(risk.get('schema_version')) is int and risk['schema_version'] == 1
               and bindings.get('source_identity') and risk.get('bindings') == bindings
               and risk.get('classification') in {'substantive', 'lightweight'}
               and _citation(risk.get('scope_evidence_refs'))
               and isinstance(risk.get('triggers'), list)
               and all(isinstance(t, str) and t in ARCHITECTURE | SECURITY for t in risk['triggers']))
    required = set(PERSPECTIVES)
    exemptions = {}
    lightweight = False
    if current:
        triggers = set(risk['triggers'])
        assessments = risk.get('perspectives', {})
        if not isinstance(assessments, dict):
            assessments = {}
        candidate_light = risk['classification'] == 'lightweight' and not triggers
        for perspective in PERSPECTIVES:
            row = assessments.get(perspective, {})
            forced = (perspective in {'code', 'test'} and not candidate_light
                      or perspective == 'architecture' and bool(triggers & ARCHITECTURE)
                      or perspective == 'security' and bool(triggers & SECURITY))
            exempt = (not forced and isinstance(row, dict) and row.get('applicability') == 'not-applicable'
                      and isinstance(row.get('reason'), str) and row['reason'].strip()
                      and _citation(row.get('evidence_refs')))
            if exempt:
                required.remove(perspective)
                exemptions[perspective] = deepcopy(row)
        lightweight = candidate_light and not required
        if not lightweight:
            required.update({'code', 'test'})
            for p in ('code', 'test'):
                exemptions.pop(p, None)
    escalation_refs=[]
    for row in subject.get('review_risk_escalations',[]):
        if isinstance(row,dict) and row.get('scope')==scope and row.get('bindings')==bindings:
            extra=row.get('required_perspectives')
            if not isinstance(extra,list) or not extra or any(p not in PERSPECTIVES for p in extra):extra=list(PERSPECTIVES)
            required.update(extra);required.update({'code','test'});lightweight=False
            for p in required:exemptions.pop(p,None)
            escalation_refs.append(row.get('review_id'))
    if scope.get('role') == 'acceptance':
        required = set()
        exemptions = {}
        lightweight = False
    result = {**base, 'status': 'allow', 'bindings': bindings,
              'risk_status': 'current' if current else 'unknown',
              'required_perspectives': [p for p in PERSPECTIVES if p in required],
              'exemptions': exemptions, 'lightweight': lightweight,'escalation_refs':escalation_refs}
    result['assessment_hash'] = digest({'result': result, 'risk': risk})
    return result


def record_risk(subject: dict, scope: dict, risk: dict) -> dict:
    require_review_policy(subject)
    _require(subject.get('status') == 'active', 'Risk requires an active scope.')
    assessment = review_requirements(subject, scope, risk)
    _require(assessment['status'] == 'allow', 'Current policy required for risk assessment.')
    updated = deepcopy(subject)
    updated.setdefault('risk_assessments', {})[digest(scope)] = {'risk': deepcopy(risk), 'assessment': assessment}
    return updated


def adopt_review_policy(subject: dict, authorization: dict) -> dict:
    _require(review_version(subject) is None, 'Review contracts cannot be reset or silently migrated.')
    _require(subject.get('status') == 'active' and authorization.get('approved') is True
             and isinstance(authorization.get('actor_id'), str) and authorization['actor_id'].strip()
             and authorization.get('run_id') == subject.get('id')
             and authorization.get('state_version') == subject.get('state_version')
             and authorization.get('provenance', {}).get('kind') == 'user-message'
             and authorization['provenance'].get('ref'), 'Approve the exact active scope with actual user-message provenance.')
    _require(not subject.get('active_attempt'), 'Finish the active attempt before review adoption.')
    collections = [('effects', {'completed','failed','reconciled'}),
                   ('active_executions', {'completed','failed','reconciled'}),
                   ('executions', {'completed','failed','reconciled'}),
                   ('native_invocations', {'completed','failed','interrupted'}),
                   ('repair_cycles', {'recorded','aborted'})]
    for name, terminal in collections:
        rows = subject.get(name, [] if name == 'repair_cycles' else {})
        rows = rows if isinstance(rows, list) else rows.values() if isinstance(rows, dict) else [None]
        _require(all(isinstance(row, dict) and row.get('status') in terminal for row in rows),
                 'Finish and reconcile every active or uncertain worker before review adoption.')
    selected = enforcement_version(subject)
    _require(selected in {None, 1}, 'Migrate unsupported enforcement explicitly before review adoption.')
    updated = adopt_enforcement(subject, authorization) if selected is None else deepcopy(subject)
    updated['review_policy'] = {**new_review_policy(), 'authorization': deepcopy(authorization)}
    for rows in updated.get('reviews', {}).values():
        for review in rows:
            review['fresh'] = False
    for acceptance in updated.get('acceptances', []):
        acceptance['fresh'] = False
    for proof in updated.get('verifier_proofs', {}).values():
        proof['semantic_status'] = 'pending-review'
        proof.pop('semantic_review_id', None)
        proof.pop('semantic_approval', None)
    updated.pop('risk_assessments', None)
    if selected is not None:
        updated['state_version'] = subject.get('state_version', 0) + 1
    return updated
