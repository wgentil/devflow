"""Explicit, one-shot native repair dispatch and configured gate replay."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from .repair import failure_delta, repair_decision
from .host_projection import read_host
from .storage_pins import reservation
from .store import WorkflowError, transact
from .native_runtime import invoke


def _preflight_worker(root: Path, data: dict, binding: dict) -> dict:
    from .native_runtime import discover, resolve, candidate_intent
    from .hosts import validate_binding
    from .releases import release_descriptor, check_release
    current = validate_binding(data, binding['binding_id'], binding['revision'])
    parity = check_release(current['release'], release_descriptor(), 1)
    if parity['status'] != 'allow':
        return {'status': 'block', 'reason_code': 'RELEASE_MISMATCH'}
    from .native_models import NativeError
    try:
        context = discover(root, current)
        decision = resolve(data, current, 'implementation', context)
        if not decision.get('resolved'):
            decision = candidate_intent(data, current, 'implementation', context)
        return decision
    except NativeError as exc:
        return {'status': 'block', 'reason_code': exc.code}


def _event(root: Path, operation_id: str, action: str, request: dict) -> dict:
    state = read_host(root,request=request,operation_id=operation_id)
    event = {'kind': 'domain.repair.' + action, 'payload': {'request': request}}
    prior = state['operations'].get(operation_id)
    if prior and (prior['kind'] != event['kind'] or prior['payload'] != event['payload']):
        raise WorkflowError('OPERATION_CONFLICT', 'repair operation ID belongs to another request')
    result = transact(root, state['version'], operation_id, event)
    return result['state']['data']['domain_receipts'][operation_id]


def _run_gate(root: Path, run_id: str, gate_id: str, operation_id: str) -> dict:
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as stream:
        json.dump({'run_id': run_id, 'gate_id': gate_id}, stream)
        path = Path(stream.name)
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'run.py'),
                                 'harden', 'gate', '--root', str(root), '--input', str(path),
                                 '--operation-id', operation_id], capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise WorkflowError('REPAIR_VERIFICATION_FAILED', result.stderr or result.stdout)
        return json.loads(result.stdout)
    finally:
        path.unlink(missing_ok=True)


def _abort(root: Path, run_id: str, cycle_id: str, reason_code: str, worker_ref: str | None) -> dict:
    cycle = _event(root, cycle_id + ':abort', 'abort',
                   {'run_id': run_id, 'cycle_id': cycle_id, 'reason_code': reason_code,
                    'completed_at_ms': int(time.time() * 1000), 'worker_ref': worker_ref})
    return {'status': 'blocked', 'reason_code': reason_code, 'cycle': cycle,
            'remaining_failures': cycle['remaining_failures']}


@reservation('repair-dispatch')
def run_repair(root: Path, run_id: str, operation_id: str, estimated_cost: float | None = None) -> dict:
    """Run one claimed cycle. A replay never launches another worker."""
    root = Path(root)
    state = read_host(root,run_id=run_id,operation_id=operation_id+':claim')
    run = state['data'].get('runs', {}).get(run_id)
    if not run:
        raise WorkflowError('RUN_UNAVAILABLE', 'known repair run required')
    claim_id = operation_id + ':claim'
    if claim_id in state['operations']:
        cycle = next(row for row in run.get('repair_cycles', []) if row['cycle_id'] == operation_id)
        return {'status': 'blocked', 'reason_code': 'REPAIR_ALREADY_CLAIMED',
                'cycle': cycle, 'replayed': True}
    now_ms = int(time.time() * 1000)
    decision = repair_decision(run, now_ms)
    if decision['status'] != 'ready':
        return decision
    if not decision['scope']['gate_ids']:
        return {**decision, 'status': 'blocked', 'reason_code': 'MANUAL_VERIFICATION_REQUIRED'}
    if estimated_cost is None:
        return {**decision, 'status': 'blocked', 'reason_code': 'PRICE_UNKNOWN'}
    if type(estimated_cost) not in (int, float) or estimated_cost < 0:
        raise WorkflowError('INVALID_REPAIR_COST', 'known nonnegative estimate required')
    if decision['remaining']['estimated_cost'] + estimated_cost > run['repair_policy']['max_estimated_cost']:
        return {**decision, 'status': 'blocked', 'reason_code': 'SPEND_LIMIT'}
    bindings = [binding for binding in state['data'].get('host_bindings', {}).values()
                if binding.get('run_id') == run_id and binding.get('role') == 'implementer'
                and binding.get('status') == 'active' and binding.get('actor_id') == decision['scope']['implementer_actor']]
    if len(bindings) != 1:
        return {**decision, 'status': 'blocked', 'reason_code': 'IMPLEMENTER_UNAVAILABLE'}
    binding = bindings[0]
    if run.get('active_attempt') and decision['scope']['item_ids'] and run['active_attempt']['item_id'] not in decision['scope']['item_ids']:
        return {**decision, 'status': 'blocked', 'reason_code': 'ATTEMPT_SCOPE_MISMATCH'}
    eligibility = _preflight_worker(root, state['data'], binding)
    if eligibility['status'] not in {'allow', 'pending-access'} or not eligibility.get('resolved'):
        return {**decision, 'status': 'blocked',
                'reason_code': eligibility.get('reason_code', 'MODEL_UNAVAILABLE')}
    claim = _event(root, claim_id, 'claim', {'run_id': run_id, 'cycle_id': operation_id,
                    'delta_hash': decision['delta_hash'], 'claimed_at_ms': now_ms,
                    'estimated_cost': estimated_cost})
    prompt = ('Repair only these journaled failures: ' + json.dumps(claim['scope'], sort_keys=True)
              + '. Preserve approved specification and locked tests. Return changed files and rationale; '
                'configured verification and independent review will determine success.')
    request = {'binding_id': binding['binding_id'], 'revision': binding['revision'],
               'invocation_id': operation_id + ':worker', 'stage': 'implementation',
               'access': 'workspace-write', 'prompt': prompt}
    try:
        worker = invoke(root, request, operation_id + ':native')
    except Exception:
        # A running native invocation must retain its lease until reconciliation.
        if any(row.get('status') == 'running' for row in
               read_host(root,run_id=run_id)['data']['runs'][run_id].get('native_invocations', {}).values()):
            raise
        return _abort(root, run_id, operation_id, 'WORKER_UNAVAILABLE', request['invocation_id'])
    if worker.get('status') != 'allow':
        reason = worker.get('reason_code', 'WORKER_UNAVAILABLE')
        return {**_abort(root, run_id, operation_id, reason, request['invocation_id']), 'worker': worker}
    proofs = []
    try:
        for gate_id in claim['scope']['gate_ids']:
            proofs.append(_run_gate(root, run_id, gate_id, operation_id + ':gate:' + gate_id))
    except Exception:
        return _abort(root, run_id, operation_id, 'REPAIR_VERIFICATION_FAILED', request['invocation_id'])
    current = read_host(root,run_id=run_id)['data']['runs'][run_id]
    delta = failure_delta(current)
    record = _event(root, operation_id + ':record', 'record',
                    {'run_id': run_id, 'cycle_id': operation_id,
                     'output_delta_hash': delta['digest'], 'completed_at_ms': int(time.time() * 1000),
                     'remaining_failures': delta, 'worker_ref': request['invocation_id'],
                     'proof_refs': [row.get('proof_id') for row in proofs if row.get('proof_id')]})
    return {'status': 'recorded', 'cycle': record, 'remaining_failures': delta}
