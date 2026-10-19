"""Pure escalation eligibility and durable lineage checks; never launches work."""
from copy import deepcopy
from .document_units import digest
from .store import WorkflowError

REASONING_FAILURES = {'reasoning', 'material-ambiguity', 'unsuccessful-diagnosis'}
AUTH_SCOPE = ('lineage_id', 'task_hash', 'policy_hash', 'configuration_hash', 'host', 'stage')


def authorization_matches(authorization: dict, context: dict) -> bool:
    return (isinstance(authorization, dict) and authorization.get('approved') is True
            and isinstance(authorization.get('actor_id'), str) and bool(authorization['actor_id'].strip())
            and all(context.get(key) and authorization.get(key) == context[key] for key in AUTH_SCOPE)
            and type(authorization.get('max_escalations')) is int and 0 < authorization['max_escalations'] <= 10
            and isinstance(authorization.get('eligible_routes'), list))


def reasoning_failure(failure: dict) -> bool:
    return (isinstance(failure, dict) and failure.get('kind') in REASONING_FAILURES
            and isinstance(failure.get('evidence_refs'), list) and bool(failure['evidence_refs'])
            and all(isinstance(ref, str) and ref for ref in failure['evidence_refs'])
            and isinstance(failure.get('reason'), str) and bool(failure['reason'].strip()))


def plan_escalation(policy: dict, lineage: dict, failure: dict, authorization: dict) -> dict:
    base = {'status': 'block', 'dispatch': False, 'reason_code': 'ESCALATION_UNAVAILABLE', 'candidate': None}
    rules = policy.get('task_routing', {})
    limit, count = rules.get('max_escalations', 1), lineage.get('count', 0)
    if type(limit) is not int or not 0 <= limit <= 10 or type(count) is not int or count < 0:
        return {**base, 'reason_code': 'ESCALATION_STATE_INVALID'}
    if count >= limit: return {**base, 'reason_code': 'ESCALATION_LIMIT'}
    if not reasoning_failure(failure): return {**base, 'reason_code': 'ESCALATION_NOT_REASONING'}
    if not authorization_matches(authorization, lineage):
        return {**base, 'status': 'recommendation', 'reason_code': 'ESCALATION_AUTHORIZATION_REQUIRED'}
    if lineage.get('policy_hash') != digest(policy):
        return {**base, 'reason_code': 'ESCALATION_POLICY_CHANGED'}
    if count >= authorization['max_escalations']: return {**base, 'reason_code': 'ESCALATION_LIMIT'}
    from .model_policy import resolve_profile
    for route in rules.get('escalation_routes', []):
        if not isinstance(route, dict) or set(route) - {'pin', 'profile', 'effort'}:
            continue
        prefs = deepcopy(lineage.get('preferences', {}))
        if any(key in prefs and key in route and prefs[key] != route[key] for key in ('pin', 'profile', 'effort')):
            continue
        request = {**prefs, **route, 'host': lineage['host'], 'stage': lineage['stage']}
        decision = resolve_profile(policy, request, lineage.get('capabilities', {}), lineage.get('discovery', {}), lineage.get('prices'))
        resolved = decision.get('resolved')
        if (decision.get('status') != 'allow' or not resolved or all(resolved.get(key) == lineage.get('current', {}).get(key) for key in ('model', 'effort'))
                or {'model': resolved['model'], 'effort': resolved['effort']} not in authorization['eligible_routes']):
            continue
        return {**base, 'status': 'eligible', 'reason_code': 'AUTHORIZED_NEXT_ROUTE', 'candidate': decision,
                'escalation_index': count + 1, 'predecessor_invocation_id': lineage.get('predecessor_invocation_id'),
                'authorization_hash': digest(authorization), 'evidence_hash': digest(failure)}
    return {**base, 'reason_code': 'NO_ELIGIBLE_ESCALATION'}


def resolve_routing_retry(policy, run, facts, replacement_of, preferences, context, prices):
    """Re-resolve an existing escalated route; never spend or reset allowance."""
    from .routing_receipts import routing_lineage_id
    from .model_policy import resolve_profile
    from .task_routing import classify_task
    identifier = routing_lineage_id(facts)
    known = run.get('routing_lineages', {}).get(identifier, {})
    if not known.get('count'): return None
    prior = run.get('native_invocations', {}).get(replacement_of, {})
    if replacement_of != known.get('last_invocation_id') or prior.get('status') != 'interrupted':
        raise WorkflowError('ESCALATION_CONFLICT', 'Retry must name the last stopped lineage invocation.')
    old = prior.get('decision', {})
    selected = old.get('resolved', {})
    retained = {'pin': selected.get('model'), 'effort': selected.get('effort'), 'profile': old.get('profile')}
    if any(preferences.get(key) is not None and preferences[key] != value for key,value in retained.items()):
        raise WorkflowError('ESCALATION_CONFLICT', 'Retained route conflicts with current preferences.')
    order = policy.get('task_routing', {}).get('profile_order', [])
    floor = classify_task(policy, facts, facts['stage'])['profile']
    if floor in order and retained['profile'] in order and order.index(floor) > order.index(retained['profile']):
        raise WorkflowError('ESCALATION_CONFLICT', 'Changed task facts require a stronger fresh decision.')
    decision = resolve_profile(policy, {**preferences, **retained, 'task': facts},
        context.get('capabilities', {}), context.get('discovery', {}), prices)
    return {'decision': decision, 'escalation_index': known['count']}


def validate_lineage_start(run: dict, routing: dict, scope: dict, resolved: dict) -> dict:
    """Validate under the existing journal CAS; return the next lineage record."""
    def require(value, message):
        if not value: raise WorkflowError('ESCALATION_CONFLICT', message)
    identifier = routing['lineage_id']
    known = run.get('routing_lineages', {}).get(identifier)
    # Stable work-item/stage association prevents a retry changing its task label
    # to obtain another allowance. Non-item tasks use their explicit stable ID.
    task = routing['task_facts']
    key = digest([scope['run_id'], scope['stage'], scope.get('item_id') or task['task_id']])
    associations = run.get('routing_task_ids', {})
    require(key not in associations or associations[key] == identifier, 'Task lineage cannot reset across retries or handoff.')
    index = routing.get('escalation_index', 0)
    require(type(index) is int and index >= 0, 'Escalation index must be nonnegative.')
    if routing.get('retry_of') is not None:
        predecessor = routing['retry_of']
        prior = run.get('native_invocations', {}).get(predecessor, {})
        require(known is not None and index == known.get('count', 0), 'Retry must retain the durable escalation count.')
        require(predecessor == known.get('last_invocation_id') and prior.get('status') == 'interrupted', 'Retry requires the last stopped invocation.')
        require(prior.get('decision', {}).get('resolved') == resolved, 'Retry cannot change the escalated route.')
        return {**deepcopy(known), 'last_invocation_id': None}
    if index == 0:
        require(not known or known.get('count', 0) == 0, 'Escalation allowance cannot reset.')
        return {'lineage_id': identifier, 'count': 0, 'task_key': key, 'last_invocation_id': None}
    require(known is not None and index == known.get('count', 0) + 1, 'Escalation must consume the next durable allowance.')
    # Shipped automatic allowance is one. Larger limits need a separately
    # designed extension rather than caller metadata increasing the cap.
    require(index <= 1, 'Automatic escalation allowance exhausted.')
    predecessor = routing.get('predecessor_invocation_id')
    require(predecessor and predecessor == known.get('last_invocation_id'), 'Escalation predecessor must be the last lineage invocation.')
    prior = run.get('native_invocations', {}).get(predecessor, {})
    require(prior.get('status') in {'completed', 'interrupted'}, 'Predecessor must have stopped.')
    auth, failure = routing.get('escalation_authorization'), routing.get('escalation_evidence')
    context = {**routing, 'host': scope['host'], 'stage': scope['stage']}
    require(authorization_matches(auth, context) and index <= auth['max_escalations'], 'Fresh scoped escalation authorization required.')
    require(reasoning_failure(failure), 'Recorded reasoning evidence required.')
    require({'model': resolved.get('model'), 'effort': resolved.get('effort')} in auth['eligible_routes'], 'Selected route exceeds authorization.')
    require(prior.get('decision', {}).get('resolved') != resolved, 'Escalation must change eligible model or effort.')
    return {'lineage_id': identifier, 'count': index, 'task_key': key, 'last_invocation_id': None,
            'authorization_hash': digest(auth), 'evidence_hash': digest(failure)}
