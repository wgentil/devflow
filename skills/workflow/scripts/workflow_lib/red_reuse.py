"""Content-bound source RED eligibility; never executes or imports proof claims."""
from copy import deepcopy
from .document_units import digest
from .store import WorkflowError


def verification_contract(run: dict, item: dict, repo_id: str, test_hashes: dict,
                          target_ids: list[str], argv: list[str], report_format: str) -> dict:
    return {'schema_version': 1, 'spec_hash': run.get('plan', {}).get('spec_hash'),
            'plan_hash': digest(run.get('plan', {})), 'governing_digest': run.get('governing_digest'),
            'item_hash': digest(item), 'repo_id': repo_id, 'test_hashes': deepcopy(test_hashes),
            'target_ids': sorted(set(target_ids)), 'argv': list(argv), 'report_format': report_format}


def select_red_source(data: dict, run_id: str, item_id: str, contract: dict,
                      proof_id: str, source_run_id: str | None = None) -> dict:
    def require(ok, reason):
        if not ok: raise WorkflowError('RED_REUSE_MISMATCH', reason)
    source_id = source_run_id or run_id
    run = data.get('runs', {}).get(source_id, {})
    proof = run.get('verification_proofs', {}).get(proof_id, {})
    require(proof.get('id') == proof_id and proof.get('run_id') == source_id
            and proof.get('item_id') == item_id and proof.get('kind') == 'code'
            and proof.get('phase') == 'RED' and proof.get('passed') is True
            and type(proof.get('exit_code')) is int and proof['exit_code'] != 0,
            'Source must be a recorded passing RED proof for this item.')
    require(isinstance(contract, dict) and proof.get('verification_contract') == contract
            and proof.get('contract_hash') == digest(contract),
            'RED contract differs or legacy provenance is incomplete; tests, targets, plan, governing inputs and verifier must match.')
    item = next((item for item in run.get('plan', {}).get('work_items', []) if item['id'] == item_id), None)
    require(item is not None and verification_contract(run,item,proof.get('repo_id'),proof.get('test_hashes',{}),
            contract.get('target_ids',[]),proof.get('argv',[]),contract.get('report_format')) == contract,
            'Source run/item provenance no longer matches recorded RED.')
    require(source_id == run_id or bool(contract.get('spec_hash')), 'Cross-run reuse requires canonical specification identity.')
    outcomes = proof.get('target_outcomes') or {}
    targets = contract.get('target_ids', [])
    require(bool(targets) and all(target in outcomes for target in targets)
            and any(outcomes[target] == 'failed' for target in targets),
            'RED must include all requested targets and a genuine target failure.')
    return {'run_id': source_id, 'proof_id': proof_id, 'token': proof['token'], 'contract_hash': digest(contract)}
