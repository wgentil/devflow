"""Explicit workflow-only reviewer consent; never suitability validation."""
from copy import deepcopy

from .document_units import digest
from .review_policy import PERSPECTIVES, bounded, require_review_policy
from .store import WorkflowError

ROLES = {'item', 'branch', 'acceptance', 'pr'}
BASIS = 'human-authorized-observed/v1'


def need(condition, message):
    if not condition:
        raise WorkflowError('REVIEW_AUTHORIZATION_BLOCKED', message)


def _subject(subject):
    need(isinstance(subject, dict) and subject.get('id') and not subject.get('review_contract_hash')
         and subject.get('plan', {}).get('spec_hash') and subject.get('status') == 'active',
         'An active workflow run with approved specification is required.')
    require_review_policy(subject)


def _human(subject, record):
    actor = record.get('actor_id')
    forbidden = set(subject.get('implementer_actors', [])) | {subject.get('actors', {}).get('implementer')}
    forbidden.update(r.get('actor_id') for rows in subject.get('reviews', {}).values() for r in rows)
    provenance = record.get('provenance')
    need(isinstance(actor, str) and actor.strip() and actor not in forbidden
         and isinstance(provenance, dict) and provenance.get('kind') == 'user-message'
         and isinstance(provenance.get('ref'), str) and provenance['ref'].strip(),
         'Actual human approval with user-message provenance is required; agents cannot authorize themselves.')


def propose_authorization(subject: dict, selection: dict) -> dict:
    _subject(subject)
    bounded(selection)
    need(isinstance(selection, dict) and set(selection) ==
         {'host', 'provider', 'model', 'profile', 'effort', 'roles', 'perspectives'},
         'Declare the exact host/provider/model, deep profile/high effort and review scopes only.')
    roles, perspectives = selection['roles'], selection['perspectives']
    need(selection['host'] in {'codex', 'claude'}
         and selection['provider'] == {'codex': 'openai', 'claude': 'anthropic'}.get(selection['host'])
         and isinstance(selection['model'], str) and selection['model'].strip()
         and selection['profile'] == 'deep-reasoning' and selection['effort'] == 'high',
         'One exact provider/model at deep-reasoning/high is required.')
    need(isinstance(roles, list) and roles and all(isinstance(r, str) and r in ROLES for r in roles)
         and len(set(roles)) == len(roles) and isinstance(perspectives, list)
         and all(isinstance(p, str) and p in PERSPECTIVES for p in perspectives)
         and len(set(perspectives)) == len(perspectives)
         and (set(roles) == {'acceptance'} or perspectives), 'Explicit supported review roles and perspectives required.')
    body = {'schema_version': 1, 'run_id': subject['id'], 'spec_hash': subject['plan']['spec_hash'],
            'review_policy_hash': digest(subject['review_policy']), 'selection': deepcopy(selection),
            'suitability': 'unvalidated', 'restrictions_hash': digest({
                'model_overrides': subject.get('model_overrides', []), 'effect_policy': subject.get('effect_policy')})}
    return {**body, 'proposal_hash': digest(body)}


def _proposal_current(subject, proposal):
    _subject(subject)
    need(isinstance(proposal, dict) and set(proposal) == {'schema_version', 'run_id', 'spec_hash',
         'review_policy_hash', 'selection', 'suitability', 'restrictions_hash', 'proposal_hash'},
         'Known exact authorization proposal schema required.')
    need(proposal['schema_version'] == 1 and type(proposal['schema_version']) is int
         and proposal['suitability'] == 'unvalidated' and proposal['run_id'] == subject['id']
         and proposal['spec_hash'] == subject['plan']['spec_hash']
         and proposal['review_policy_hash'] == digest(subject['review_policy'])
         and proposal['proposal_hash'] == digest({k: v for k, v in proposal.items() if k != 'proposal_hash'}),
         'Authorization hash, run, specification or review policy changed.')
    # Revalidate the selection without expiring consent on ordinary restriction/source changes.
    propose_authorization(subject, proposal['selection'])


def record_authorization(subject: dict, record: dict) -> dict:
    bounded(record)
    need(isinstance(record, dict) and set(record) == {'proposal', 'confirmed_hash', 'actor_id', 'provenance'},
         'Exact proposal and actual human confirmation required.')
    _proposal_current(subject, record['proposal'])
    _human(subject, record)
    key = record['proposal']['proposal_hash']
    need(record['confirmed_hash'] == key, 'Human confirmation must bind the exact proposal hash.')
    need(key not in subject.get('review_model_revocations', {}), 'Revoked consent cannot be restored by retry.')
    prior = subject.get('review_model_authorizations', {}).get(key)
    need(prior is None or prior == record, 'Authorization identity is immutable.')
    updated = deepcopy(subject)
    updated.setdefault('review_model_authorizations', {})[key] = deepcopy(record)
    return updated


def revoke_authorization(subject: dict, record: dict) -> dict:
    _subject(subject)
    bounded(record)
    need(isinstance(record, dict) and set(record) == {'authorization_hash', 'actor_id', 'reason', 'provenance'},
         'Name one exact authorization and the human revocation reason.')
    _human(subject, record)
    key = record['authorization_hash']
    need(isinstance(key, str) and key in subject.get('review_model_authorizations', {})
         and isinstance(record['reason'], str) and record['reason'].strip(), 'Known authorization and reason required.')
    prior = subject.get('review_model_revocations', {}).get(key)
    need(prior is None or prior == record, 'Revocation identity is immutable.')
    updated = deepcopy(subject)
    updated.setdefault('review_model_revocations', {})[key] = deepcopy(record)
    return updated


def current_authorization(subject: dict, authorization_hash: str, scope: dict) -> dict:
    need(isinstance(authorization_hash, str) and authorization_hash
         and isinstance(scope, dict), 'Explicit authorization and review scope required.')
    record = subject.get('review_model_authorizations', {}).get(authorization_hash)
    need(isinstance(record, dict) and authorization_hash not in subject.get('review_model_revocations', {}),
         'Authorization is missing or revoked.')
    _proposal_current(subject, record.get('proposal'))
    _human(subject, record)
    need(record.get('confirmed_hash') == authorization_hash == record['proposal']['proposal_hash'],
         'Recorded consent does not bind this authorization.')
    selected = record['proposal']['selection']
    need(scope.get('role') in selected['roles']
         and (scope['role'] == 'acceptance' or scope.get('perspective') in selected['perspectives']),
         'Authorization does not cover this role or perspective.')
    for key in ('host', 'provider', 'model', 'profile', 'effort'):
        need(key not in scope or scope[key] == selected[key], 'Authorization does not cover selected ' + key + '.')
    return deepcopy(record)


def resolve_authorized_review(subject, request, scope, capabilities, discovery, prices,
                              authorization_hash, policy):
    """Reuse restriction checks, then require actual observable native capability."""
    try:
        need(isinstance(request, dict) and isinstance(scope, dict)
             and request.get('stage') in {'review', 'acceptance'}
             and (request['stage'] == 'acceptance') == (scope.get('role') == 'acceptance'),
             'Authorization selects workflow reviewer execution only.')
        consent = current_authorization(subject, authorization_hash, scope)
        selected = consent['proposal']['selection']
        need(request.get('host') == selected['host']
             and request.get('pin', selected['model']) == selected['model']
             and request.get('profile', 'deep-reasoning') == 'deep-reasoning'
             and request.get('effort', 'high') == 'high', 'Requested settings conflict with exact consent.')
        from .model_policy import resolve_profile
        decision = resolve_profile(policy, {**request, 'mode': 'advisory', 'pin': selected['model'],
            'allow_unvalidated': True, 'profile': 'deep-reasoning', 'effort': 'high'}, capabilities, discovery, prices)
        need(decision.get('status') == 'allow' and decision.get('dispatch') is True
             and capabilities.get('configure') is True and capabilities.get('observe') is True
             and decision.get('resolved') == {k: selected[k] for k in ('provider', 'model', 'effort')},
             'Selected reviewer must be available, permitted, configurable and observable within existing limits.')
        return {**decision, 'mode': 'strict', 'capability_validated': False, 'validation_ref': None,
                'reason_code': 'HUMAN_AUTHORIZED_OBSERVABLE_REVIEW', 'suitability': 'unvalidated',
                'review_authorization_hash': authorization_hash,
                'eligibility': {'schema_version': 1, 'basis': BASIS, 'authorization_hash': authorization_hash},
                'model_revision': discovery.get('model_revisions', {}).get(selected['model'])}
    except (WorkflowError, TypeError, ValueError, KeyError, AttributeError) as exc:
        return {'status': 'block', 'dispatch': False, 'reason_code': 'REVIEW_AUTHORIZATION_BLOCKED', 'message': str(exc)}


def authorization_scope(binding, stage):
    role = binding.get('role', '').removesuffix('-reviewer')
    need(role in ROLES and stage in {'review', 'acceptance'}
         and (stage == 'acceptance') == (role == 'acceptance'), 'Authorization is restricted to workflow review roles.')
    return {'role': role, 'host': binding.get('host'),
            **({'perspective': binding['perspective']} if role != 'acceptance' and binding.get('perspective') else {})}


def validate_authorized_decision(subject, decision, scope):
    key = decision.get('review_authorization_hash')
    record = current_authorization(subject, key, scope)
    selected = record['proposal']['selection']
    need(decision.get('eligibility') == {'schema_version': 1, 'basis': BASIS, 'authorization_hash': key}
         and decision.get('capability_validated') is False and decision.get('suitability') == 'unvalidated'
         and decision.get('validation_ref') is None and decision.get('profile') == 'deep-reasoning'
         and decision.get('mode') == 'strict'
         and decision.get('resolved') == {k: selected[k] for k in ('provider', 'model', 'effort')},
         'Only the exact disclosed human-authorized eligibility basis is permitted.')
    return record


def validate_authorized_receipt(subject, receipt, scope):
    validate_authorized_decision(subject, receipt, scope)
    from .model_policy import check_model_receipt
    need(receipt.get('status') == 'allow' and receipt.get('dispatch') is True
         and receipt.get('transport_completed') is True
         and check_model_receipt(receipt, 'strict')['status'] == 'allow'
         and receipt.get('observed', {}).get('provider') == receipt['resolved']['provider'],
         'A completed native invocation with trusted exact settings is required.')
    invocation = subject.get('native_invocations', {}).get(receipt.get('invocation_id'), {})
    native_result = invocation.get('result', {})
    receipt_scope = receipt.get('scope', {})
    need(invocation.get('status') == 'completed'
         and receipt_scope.get('role') == scope['role'] + '-reviewer'
         and (scope['role'] == 'acceptance' or receipt_scope.get('perspective') == scope.get('perspective'))
         and receipt.get('policy_revision') == len(subject.get('model_overrides', []))
         and invocation.get('decision', {}).get('eligibility') == receipt['eligibility']
         and invocation.get('decision', {}).get('review_authorization_hash') == receipt['review_authorization_hash']
         and invocation.get('decision', {}).get('resolved') == receipt['resolved']
         and invocation.get('scope') == receipt.get('scope')
         and all(native_result.get(k) == receipt.get(k) for k in
                 ('observed', 'observation_source', 'invocation_ref', 'output_ref', 'review_input_validation', 'review_report_hash'))
         and bool(receipt.get('invocation_ref')) and bool(receipt.get('output_ref')),
         'Portable or mismatched receipts cannot assert native execution provenance.')
    return {'status': 'allow', 'eligibility': deepcopy(receipt['eligibility']),
            'suitability': 'unvalidated', 'model_revision': receipt.get('model_revision')}
