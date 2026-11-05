"""Live reservation adapter; journal replay remains pure and never dispatches."""
from pathlib import Path
import math
import os
import time
from .store import WorkflowError, transact
from .storage_access import read_current, operation_lookup
from .enforcement_live import source_observation


def binding_owner(binding: dict) -> dict:
    return {key: binding[key] for key in ('binding_id', 'revision', 'actor_id', 'role',
        'run_id', 'package_hash', 'item_id') if key in binding}


def reserve_dispatch(root: Path, run_id: str, effect_id: str, exclusive_scope: str,
                     estimated_cost: float | None, operation_id: str, action_scope: dict, *, owner_binding: dict | None = None, effect_kind: str = 'work', client_request_hash: str | None = None) -> dict:
    root = Path(root)
    claim_id = operation_id + ':enforcement-claim'
    if operation_lookup(root, claim_id):
        raise WorkflowError('EFFECT_ALREADY_CLAIMED', 'Inspect the recorded claim; replay never launches a replacement.')
    if type(estimated_cost) not in (int, float) or not math.isfinite(estimated_cost) or estimated_cost < 0:
        raise WorkflowError('PRICE_UNKNOWN', 'Known finite reservation cost required before dispatch.')
    state = read_current(root, run_id=run_id)
    subject = state['data'].get('runs', {}).get(run_id)
    if not subject: raise WorkflowError('RUN_UNAVAILABLE', 'Known run required.')
    if effect_id in subject.get('effects', {}):
        raise WorkflowError('EFFECT_ALREADY_CLAIMED', 'Effect identity already has a reservation; reconcile before replacement.')
    observation = source_observation(subject)
    request = {'run_id': run_id, 'record': {'effect_id': effect_id, 'scope': exclusive_scope,
        'estimated_cost': estimated_cost, 'owner_pid':os.getpid(), 'now_ms': int(time.time()*1000),
        'action_scope': action_scope, 'effect_kind': effect_kind, **observation,
        **({'client_request_hash': client_request_hash} if client_request_hash is not None else {}),
        **({'owner_binding': binding_owner(owner_binding)} if owner_binding is not None else {})}}
    response = transact(root, state['version'], claim_id,
        {'kind': 'domain.enforcement.claim', 'payload': {'request': request}})
    return response['state']['data']['runs'][run_id]['effects'][effect_id]
