"""Allowlisted, opt-in run summaries for workflow improvement."""

from __future__ import annotations

from .store import WorkflowError


def project_run_trace(state: dict, run_id: str, include_usage: bool) -> dict:
    data = state.get('data', state)
    run = data.get('runs', {}).get(run_id)
    if not run:
        raise WorkflowError('RUN_UNAVAILABLE', 'known run required')
    if run.get('improvement_trace_enabled') is not True:
        raise WorkflowError('TRACE_OPT_IN_REQUIRED', 'this run has not opted into improvement traces')
    from .gates import gate_status
    stage = gate_status(run, live=False)
    observations = []
    for invocation_id, row in sorted(run.get('model_receipts', {}).items()):
        observed = row.get('observed') or {}
        observations.append({'invocation_id': invocation_id,
                             'model': observed.get('model'), 'effort': observed.get('effort'),
                             'provider': observed.get('provider'),
                             'status': row.get('status')})
    gates = [{'gate_id': gate_id, 'passed': proof.get('passed') is True,
              'failure_code': proof.get('failure')}
             for gate_id, proof in sorted(run.get('hardening_proofs', {}).items())]
    deltas = [{'cycle_id': row.get('cycle_id'), 'status': row.get('status'),
               'input_delta_hash': row.get('input_delta_hash'),
               'output_delta_hash': row.get('output_delta_hash')}
              for row in run.get('repair_cycles', [])]
    usage_status = 'omitted'
    usage = None
    if include_usage:
        events = [row for row in data.get('usage', {}).get('events', [])
                  if (row.get('binding') or {}).get('run_id') == run_id]
        if events:
            usage_status = 'reported'
            usage = {'input_tokens': sum(row.get('input_tokens', 0) for row in events),
                     'cached_tokens': sum(row.get('cached_tokens', 0) for row in events),
                     'output_tokens': sum(row.get('output_tokens', 0) for row in events),
                     'event_count': len(events)}
        else:
            usage_status = 'unknown'
    return {'version': 1, 'run_id': run_id, 'stage': stage.get('stage'),
            'status': run.get('status'), 'finding_ids': sorted({row.get('id') for row in
            run.get('unresolved_findings', []) if isinstance(row.get('id'), str)}),
            'gate_results': gates, 'repair_deltas': deltas,
            'model_observations': observations, 'usage_status': usage_status,
            'usage': usage, 'elapsed_ms': run.get('elapsed_ms')}
