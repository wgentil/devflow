"""Recorded issue-start policy contracts; fixed historical defaults, no I/O."""
from copy import deepcopy
from .store import WorkflowError

# Frozen v0.3.18 contracts: changing live defaults must not change replay.
V0318 = {'schema_version': 1,
    'enforcement': {'protocol': 'devflow.python-enforcement/v1', 'policy_version': 1},
    'review_policy': {'protocol': 'devflow.adversarial-review/v1', 'schema_version': 1,
        'revision': 1, 'substantive_perspectives': ['code', 'test'],
        'risk_perspectives': ['architecture', 'security'], 'substantive_profile': 'deep-reasoning',
        'substantive_effort': 'high', 'lightweight_profile': 'fast-analysis',
        'selection_order': 'configured-entry-order'}}


def current_run_contract():
    from .review_policy import new_review_policy
    return {'schema_version': 1, 'enforcement': deepcopy(V0318['enforcement']),
            'review_policy': new_review_policy()}


def validate_run_contract(value):
    # Canonical comparison also distinguishes bool from integer schema versions.
    import json
    try:
        valid = json.dumps(value, sort_keys=True, allow_nan=False) == json.dumps(V0318, sort_keys=True)
    except (TypeError, ValueError): valid = False
    if not valid:
        raise WorkflowError('ISSUE_RUN_CONTRACT_INVALID', 'Supported exact recorded issue-run contract required.')
    return deepcopy(value)


def historical_issue_run(data, run_id, plan, contract):
    from .runs import historical_run_base
    run = historical_run_base(data, run_id, plan)
    if contract is not None:
        run.update({k: v for k, v in validate_run_contract(contract).items() if k != 'schema_version'})
    return run


# Historical selection is supplied by the caller, never inferred by the reducer.
from contextvars import ContextVar
from contextlib import contextmanager
UNSELECTED = object()
RECOVERED_CONTRACT = ContextVar('devflow_issue_recovered_contract', default=UNSELECTED)
REPLAY_SELECTIONS = ContextVar('devflow_issue_replay_selections', default={})


@contextmanager
def replay_policy_context(selections):
    token = REPLAY_SELECTIONS.set(selections)
    try: yield
    finally: REPLAY_SELECTIONS.reset(token)


def selected_contract(request):
    if 'run_contract' in request:
        return validate_run_contract(request['run_contract'])
    selected = RECOVERED_CONTRACT.get()
    if selected is UNSELECTED:
        raise WorkflowError('ISSUE_POLICY_SELECTION_REQUIRED',
            'Unstamped issue build requires an explicit per-run replay recovery choice.')
    return selected


@contextmanager
def issue_event_context(event):
    from .document_units import digest
    if event.get('kind') != 'domain.issues.start':
        yield; return
    payload = event.get('payload')
    request = payload.get('request') if isinstance(payload, dict) else None
    if not isinstance(request, dict):
        raise WorkflowError('INVALID_EVENT', 'Issue-start request must be an object.')
    if request.get('intent') != 'build' or 'run_contract' in request:
        yield; return
    choice = REPLAY_SELECTIONS.get().get(digest(event))
    if choice not in ('legacy', 'v0.3.18'):
        raise WorkflowError('ISSUE_POLICY_SELECTION_REQUIRED',
            'Inspect issue replay recovery and explicitly select this run policy.',
            {'sequence': event.get('sequence'), 'operation_id': event.get('operation_id'), 'event_digest': digest(event)})
    token = RECOVERED_CONTRACT.set(None if choice == 'legacy' else deepcopy(V0318))
    try: yield
    finally: RECOVERED_CONTRACT.reset(token)
