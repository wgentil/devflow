"""Pure shared enforcement mutations for workflow runs and standalone sessions."""

from .action_policy import enforcement_version
from copy import deepcopy
from .store import WorkflowError


def apply_enforcement(subject: dict, action: str, record: dict) -> dict:
    from .clarifications import record_question, record_answer
    from .effect_claims import claim_effect, transition_effect
    from .finding_closure import propose_correction, validate_closure
    if enforcement_version(subject) != 1:
        raise WorkflowError('ENFORCEMENT_REQUIRED', 'Adopt the current enforcement contract first.')
    if subject.get('status') in {'complete', 'delivered', 'discarded'}:
        raise WorkflowError('SCOPE_TERMINAL', 'Terminal scopes cannot authorize new mutations.')
    if action in {'implementation-contract','fix-rationale'}:
        from .implementation_contracts import record_implementation_contract, record_fix_rationale
        return (record_implementation_contract if action=='implementation-contract' else record_fix_rationale)(subject,record)
    if action == 'review-risk':
        from .review_policy import record_risk
        return record_risk(subject,record['scope'],record['risk'])
    if action in {'tool-claim','tool-finish','tool-reconcile'}:
        from .tool_execution import reduce_tool
        return reduce_tool(subject,action,record)
    if action in {'execution-claim','execution-finish','execution-reconcile','session-proof','session-package','session-review','session-complete','authorize-session-repair'}:
        from .session_evidence import reduce_session
        return reduce_session(subject, action, record)
    reducers = {'question': record_question, 'answer': record_answer, 'claim': claim_effect,
                'effect-transition': transition_effect, 'propose-fix': propose_correction}
    if action == 'claim' and record.get('snapshots') is not None:
        from .document_units import digest
        if not record.get('snapshots') or record.get('source_identity') != digest(record['snapshots']):
            raise WorkflowError('SOURCE_OBSERVATION_REQUIRED', 'Reservation source observation mismatch.')
        observed = deepcopy(subject)
        observed['source_identity'] = record['source_identity']
        observed['source_observation'] = {'snapshots': deepcopy(record['snapshots']), 'source_identity': record['source_identity']}
        return claim_effect(observed, record)
    if action == 'effect-transition':
        effect = subject.get('effects', {}).get(record.get('effect_id'), {})
        if effect.get('owner_binding') and record.get('status') not in {'uncertain', 'reconciled'}:
            safe_abort = (effect.get('status') == 'claimed' and record.get('status') == 'failed'
                and record.get('effect_id') not in subject.get('native_invocations', {}))
            if not safe_abort:
                raise WorkflowError('TRANSPORT_RECEIPT_REQUIRED', 'Bound worker completion is recorded by its transport adapter; generic transitions cannot assert it.')
    if subject.get('review_contract_hash') and action=='propose-fix' and not subject.get('repair_authorization'):
        raise WorkflowError('REPAIR_AUTHORIZATION_REQUIRED','Review-only sessions cannot propose agent repairs.')
    if action in reducers: return reducers[action](subject, record)
    updated = deepcopy(subject)
    if action == 'probe-transition':
        effect = subject.get('effects', {}).get(record.get('effect_id'), {})
        if effect.get('effect_kind') != 'probe':
            raise WorkflowError('EFFECT_BLOCKED', 'Probe transitions cannot modify work claims.')
        updated = transition_effect(subject, record)
        if 'result' in record:
            updated['effects'][record['effect_id']]['result'] = deepcopy(record['result'])
        return updated
    if action == 'amend-review-contract':
        from .document_units import digest
        contract = subject.get('review_contract')
        authorization = record.get('authorization', {})
        if not isinstance(contract, dict) or not subject.get('review_contract_hash'):
            raise WorkflowError('SESSION_CONTRACT_REQUIRED', 'Standalone review contract required; workflow specifications use their amendment rules.')
        request = record.get('review_contract')
        if not isinstance(request, dict):
            raise WorkflowError('SESSION_CONTRACT_BLOCKED', 'Explicit replacement review request required.')
        replacement = {'scope': deepcopy(contract['scope']), 'request': deepcopy(request)}
        replacement_hash = digest(replacement)
        if (record.get('previous_contract_hash') != subject['review_contract_hash']
                or replacement_hash == subject['review_contract_hash']
                or authorization.get('approved') is not True or not authorization.get('actor_id')
                or authorization.get('contract_hash') != replacement_hash or not authorization.get('reason')
                or authorization.get('provenance', {}).get('kind') != 'user-message'
                or not authorization.get('provenance', {}).get('ref')):
            raise WorkflowError('SESSION_CONTRACT_BLOCKED', 'Actual user approval must bind the exact replacement contract and current predecessor.')
        updated.setdefault('review_contract_history', []).append({'contract': deepcopy(contract),
            'contract_hash': subject['review_contract_hash'], 'authorization': deepcopy(authorization)})
        updated['review_contract'] = replacement
        updated['review_contract_hash'] = replacement_hash
        updated['contract_approval'] = {'content_hash': replacement_hash, 'authorization': deepcopy(authorization)}
        for proof in updated.get('verification_proofs', {}).values(): proof['fresh'] = False
        for collection in ('verifier_proofs', 'hardening_proofs'):
            for proof in updated.get(collection, {}).values(): proof.update(fresh=False, passed=False)
        for rows in updated.get('reviews', {}).values():
            for review in rows: review['fresh'] = False
        for acceptance in updated.get('acceptances', []): acceptance['fresh'] = False
        updated['enforcement_revision'] = subject.get('enforcement_revision', 0) + 1
        return updated
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
    if action == 'propose-protected-change':
        from .document_units import digest
        observation = record.get('observation', {})
        baseline = subject.get('protected_inventories', {}).get(record.get('repo_id'), {}).get('baseline')
        if (not baseline or observation.get('before') != baseline
                or observation.get('baseline_hash') != digest(baseline)
                or observation.get('observation_hash') != digest({k:v for k,v in observation.items() if k != 'observation_hash'})
                or not (observation.get('changed_paths') or observation.get('inventory_changed'))):
            raise WorkflowError('PROTECTED_CHANGE_BLOCKED', 'Exact retained protected-change observation required.')
        updated.setdefault('protected_change_proposals', {})[observation['observation_hash']] = deepcopy(record)
        return updated
    if action == 'approve-protected-change':
        proposal = subject.get('protected_change_proposals', {}).get(record.get('observation_hash'), {})
        if (not proposal or record.get('repo_id') != proposal.get('repo_id')
                or record.get('approved') is not True or not record.get('actor_id') or not record.get('reason')
                or record.get('provenance', {}).get('kind') != 'user-message'
                or not record.get('provenance', {}).get('ref')):
            raise WorkflowError('PROTECTED_CHANGE_BLOCKED', 'Actual user approval of the exact retained proposal required.')
        updated.setdefault('protected_authorizations', []).append(deepcopy(record))
        return updated
    if action == 'observe-source':
        from .document_units import digest
        if not record.get('snapshots') or record.get('source_identity') != digest(record['snapshots']):
            raise WorkflowError('SOURCE_OBSERVATION_REQUIRED', 'Bound source observation required.')
        updated['source_identity'] = record['source_identity']
        updated['source_observation'] = deepcopy(record)
        return updated
    if action == 'extend-effects':
        from .document_units import digest
        from .effect_claims import validate_effect_policy
        policy, authorization = record.get('policy'), record.get('authorization', {})
        validate_effect_policy(policy)
        previous = subject.get('effect_policy', {})
        if (record.get('previous_policy_hash') != digest(previous)
                or authorization.get('approved') is not True or not authorization.get('actor_id')
                or not authorization.get('reason')
                or authorization.get('provenance', {}).get('kind') != 'user-message'
                or not authorization.get('provenance', {}).get('ref')
                or any(row.get('status') not in {'completed', 'failed', 'reconciled'}
                       for row in subject.get('effects', {}).values())
                or set(previous) - {'max_probe_attempts'} != set(policy) - {'max_probe_attempts'}
                or any(policy.get(key, 0) < previous.get(key, 0) for key in set(previous) | set(policy))
                or policy == previous):
            raise WorkflowError('EFFECT_POLICY_BLOCKED', 'Approve an exact monotonic extension after workers are reconciled; spending and clock cannot reset.')
        updated.setdefault('effect_policy_extensions', []).append(deepcopy(record))
        updated['effect_policy'] = deepcopy(policy)
        return updated
    if action == 'configure-effects':
        if subject.get('effects') or not isinstance(record.get('authorization'), dict) or record['authorization'].get('approved') is not True or not record['authorization'].get('actor_id'):
            raise WorkflowError('EFFECT_POLICY_BLOCKED', 'Explicit initial policy authorization required; existing spending cannot be reset.')
        from .effect_claims import validate_effect_policy
        policy = {k:v for k,v in record.items() if k != 'authorization'}
        validate_effect_policy(policy)
        updated['effect_policy'] = deepcopy(policy)
        return updated
    if action == 'close-finding':
        closure = validate_closure(subject, record)
        target = next(f for f in updated['unresolved_findings'] if f['id'] == record['finding_id'])
        target.update(status='resolved', resolution=closure)
        return updated
    raise WorkflowError('INVALID_ENFORCEMENT_EVENT', 'Unsupported enforcement action.')
