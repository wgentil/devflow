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
