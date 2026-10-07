"""Configured gate execution with durable attempt and result records."""
import json
from pathlib import Path
from uuid import uuid4
from .journal import add_journal_options, commit
from workflow_lib.hardening import verify_gate, repository_schedule
from workflow_lib.evidence import repository_fingerprint
from workflow_lib.gate_reports import normalize_contract
from workflow_lib.journal_domains import digest
from workflow_lib.store import read_state, WorkflowError


def register_commands(parser):
    command = parser.add_parser('harden')
    command.add_argument('operation', choices=['configure','gate','schedule'])
    command.add_argument('--input', required=True)
    add_journal_options(command)


def dispatch(parsed):
    request = json.loads(Path(parsed.input).read_text())
    if parsed.operation == 'schedule':
        return repository_schedule(request['plan'], request['repositories'])
    if parsed.operation == 'configure':
        request['gates'] = {identifier: {**config, 'contract': normalize_contract(config)}
                            for identifier, config in request['gates'].items()}
        return commit(parsed, 'domain.harden.configure', request)
    if not parsed.root or not parsed.operation_id_explicit:
        raise WorkflowError('OPERATION_ID_REQUIRED', 'gate execution requires --root and --operation-id')
    state = read_state(Path(parsed.root))
    previous = state['operations'].get(parsed.operation_id)
    if previous is not None:
        stored = previous['payload'].get('request', {})
        if previous['kind'] != 'domain.harden.record' or stored.get('execution') != request:
            raise WorkflowError('OPERATION_CONFLICT', 'gate operation ID belongs to another request')
        return {**state['data']['domain_receipts'][parsed.operation_id], 'replayed': True, 'state_version': state['version']}
    start_id = parsed.operation_id + ':start'
    if start_id in state['operations']:
        raise WorkflowError('EXECUTION_INTERRUPTED', 'gate execution was interrupted; use a new operation ID for fresh evidence')
    run = state['data'].get('runs', {}).get(request.get('run_id'), {})
    config = run.get('hardening_config', {}).get(request.get('gate_id'))
    if config is None:
        raise WorkflowError('GATE_NOT_CONFIGURED', 'record the gate configuration before running it')
    repo = Path(state['data']['repositories'][config['repo_id']]['location'])
    contract = normalize_contract(config)
    contract_hash = digest(contract)
    fingerprint = repository_fingerprint(repo)
    token = uuid4().hex
    original_id = parsed.operation_id
    parsed.operation_id = start_id
    parsed.expected_version = state['version'] if parsed.expected_version is None else parsed.expected_version
    started = commit(parsed, 'domain.harden.started', {'run_id': request['run_id'], 'gate_id': request['gate_id'],
                    'token': token, 'config_hash': run['hardening_config_hash'], 'contract_hash': contract_hash,
                    'repository_fingerprint': fingerprint})
    if started['replayed']:
        raise WorkflowError('EXECUTION_INTERRUPTED', 'another process reserved this gate execution')
    proof = verify_gate(repo, request['run_id'], request['gate_id'], config['command'], contract)
    proof['argv'] = config['command']
    proof['contract_hash'] = contract_hash
    if proof['passed'] and repository_fingerprint(repo) != fingerprint:
        proof.update(passed=False, failure='STALE_CONFIGURATION')
    parsed.operation_id = original_id
    # No live data is re-read during journal recovery; execution happened above.
    parsed.expected_version = read_state(Path(parsed.root))['version']
    return commit(parsed, 'domain.harden.record', {'run_id': request['run_id'], 'gate_id': request['gate_id'],
                  'token': token, 'config_hash': run['hardening_config_hash'], 'proof': proof, 'execution': request})
