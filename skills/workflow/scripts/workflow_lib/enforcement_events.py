"""Pure shared enforcement mutations for workflow runs and standalone sessions."""
from copy import deepcopy
from .store import WorkflowError


def apply_enforcement(subject: dict, action: str, record: dict) -> dict:
    from .clarifications import record_question, record_answer
    from .effect_claims import claim_effect, transition_effect
    from .finding_closure import propose_correction, validate_closure
    if subject.get('enforcement', {}).get('policy_version') != 1:
        raise WorkflowError('ENFORCEMENT_REQUIRED', 'Adopt the current enforcement contract first.')
    reducers = {'question': record_question, 'answer': record_answer, 'claim': claim_effect,
                'effect-transition': transition_effect, 'propose-fix': propose_correction}
    if action in reducers: return reducers[action](subject, record)
    updated = deepcopy(subject)
    if action == 'protect-inventory':
        from .document_units import digest
        repo_id = record.get('repo_id')
        inventory, baseline, authorization = record.get('inventory', {}), record.get('baseline', {}), record.get('authorization', {})
        if (repo_id not in subject.get('repositories', {}) or repo_id in subject.get('protected_inventories', {})
                or baseline.get('inventory') != inventory or baseline.get('inventory_hash') != digest(inventory)
                or authorization.get('approved') is not True or not authorization.get('actor_id')
                or not authorization.get('reason') or authorization.get('inventory_hash') != digest(inventory)
                or inventory.get('governing_digest') != subject.get('governing_digest')
                or authorization.get('governing_digest') != subject.get('governing_digest')):
            raise WorkflowError('PROTECTION_INVENTORY_BLOCKED', 'Exact governing inventory authorization required; existing baselines cannot be reset.')
        updated.setdefault('protected_inventories', {})[repo_id] = deepcopy(record)
        return updated
    if action == 'observe-source':
        from .document_units import digest
        if not record.get('snapshots') or record.get('source_identity') != digest(record['snapshots']):
            raise WorkflowError('SOURCE_OBSERVATION_REQUIRED', 'Bound source observation required.')
        updated['source_identity'] = record['source_identity']
        updated['source_observation'] = deepcopy(record)
        return updated
    if action == 'configure-effects':
        if subject.get('effects') or not isinstance(record.get('authorization'), dict) or record['authorization'].get('approved') is not True or not record['authorization'].get('actor_id'):
            raise WorkflowError('EFFECT_POLICY_BLOCKED', 'Explicit initial policy authorization required; existing spending cannot be reset.')
        updated['effect_policy'] = deepcopy({k:v for k,v in record.items() if k != 'authorization'})
        return updated
    if action == 'close-finding':
        closure = validate_closure(subject, record)
        target = next(f for f in updated['unresolved_findings'] if f['id'] == record['finding_id'])
        target.update(status='resolved', resolution=closure)
        return updated
    raise WorkflowError('INVALID_ENFORCEMENT_EVENT', 'Unsupported enforcement action.')
