"""Bound review inputs: pure logical bindings plus separately observed file facts."""
from pathlib import Path
from copy import deepcopy
from .document_units import digest
from .clarifications import clarification_binding, relevant_questions
from .test_inputs import capture_input_bindings
from .store import WorkflowError


def review_bindings(subject: dict, role: str, item_id: str | None = None, *, live: bool = False) -> dict:
    selected = [i for i in subject.get('plan', {}).get('work_items', []) if item_id is None or i['id'] == item_id]
    proofs, observed = {}, {}
    for item in selected:
        attempts = subject.get('items', {}).get(item['id'], {}).get('attempts', [])
        if not attempts: continue
        candidates = [p for p in subject.get('verification_proofs', {}).values()
            if p.get('item_id') == item['id'] and p.get('token') == attempts[-1].get('token')
            and p.get('phase') == 'GREEN' and p.get('passed') is True and p.get('fresh') is not False]
        if not candidates: continue
        proof = candidates[-1]
        contract = proof.get('integrity', {}).get('contract', {})
        proofs[proof['id']] = {'item_id': item['id'], 'token': proof.get('token'),
            'contract_hash': digest(contract), 'source_identity': proof.get('source_identity'),
            'stdout_ref': proof.get('stdout_ref'), 'stderr_ref': proof.get('stderr_ref')}
        expected = contract.get('input_bindings', {})
        if live:
            try:
                repo = subject['repositories'][proof['repo_id']]['location']
                observed[proof['id']] = capture_input_bindings(Path(repo), list(contract.get('input_hashes', {})))
            except (KeyError, OSError, ValueError, WorkflowError):
                observed[proof['id']] = {'unavailable': True}
        else: observed[proof['id']] = expected
    scope = {'item_id': item_id} if item_id is not None else {}
    return {'logical': {'policy_hash': digest(subject.get('enforcement', {})), 'role': role,
        'item_id': item_id, 'clarifications': clarification_binding(subject, scope),
        'question_answers': deepcopy(relevant_questions(subject, scope)), 'proofs': proofs},
        'observed_inputs': observed}


def review_bindings_current(subject: dict, package: dict, *, live: bool) -> bool:
    binding = package.get('enforcement_bindings')
    if not isinstance(binding, dict): return False
    current = review_bindings(subject, package.get('role'), package.get('item_id'), live=live)
    return binding == current if live else binding.get('logical') == current['logical']
