"""Host-neutral Goal contracts; journal evidence remains authoritative."""

from __future__ import annotations

from .gates import gate_status


def goal_contract(run: dict) -> dict:
    stage = gate_status(run, live=False)
    work_items = [row['id'] for row in run.get('plan', {}).get('work_items', [])]
    return {'version': 1, 'run_id': run['id'],
            'outcome': 'Complete approved DevFlow run through verified delivery',
            'verification': {'work_item_ids': work_items,
                             'required_hardening_gate_ids': sorted(run.get('required_hardening_gates', [])),
                             'journal_stage': stage.get('stage'),
                             'independent_review_required': True,
                             'delivery_result_required': True},
            'constraints': {'approved_spec_hash': run.get('plan', {}).get('spec_hash'),
                            'repair_policy': run.get('repair_policy', {'enabled': False}),
                            'human_delivery_choice_required': True},
            'blocked_condition': 'Stop when proof, model, cost, repair limits, human approval, or host capability is unavailable; report the exact blocker.'}


def goal_handoff_decision(state: dict, source_binding: dict, destination_host: str) -> dict:
    from .store import WorkflowError
    if destination_host not in {'codex', 'claude'}:
        raise WorkflowError('HOST_UNSUPPORTED', 'Codex or Claude destination required')
    run = state.get('runs', {}).get(source_binding.get('run_id'))
    if not run:
        raise WorkflowError('RUN_UNAVAILABLE', 'known run required')
    from .journal_domains import digest
    contract = goal_contract(run)
    stage = gate_status(run, live=False)
    exhausted = bool(run.get('repair_stop')) or any(row.get('status') == 'claimed' for row in run.get('repair_cycles', []))
    paused = run.get('goal_user_paused') is True
    return {'status': 'blocked' if exhausted or paused or stage.get('stage') == 'blocked' else 'manual',
            'reason_code': 'REPAIR_OR_BUDGET_BLOCKED' if exhausted else 'USER_PAUSED' if paused
                           else 'CAPABILITY_UNAVAILABLE',
            'requires_new_goal': True, 'destination_host': destination_host,
            'contract': contract, 'contract_hash': digest(contract),
            'source_goal_ref_transferred': False}
