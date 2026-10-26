"""Journal-backed migration plans, evidence, and delivery ordering."""
import json
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity
from .journal import add_journal_options, commit
from workflow_lib.migrations import validate_increments, review_specification
from workflow_lib.store import WorkflowError


def register_commands(parser):
    command = parser.add_parser('migrate')
    command.add_argument('operation', choices=['validate','store','review-spec','record-parity','bind','delivered','inspect','verify-pilot'])
    command.add_argument('--input')
    add_journal_options(command)


def dispatch(parsed):
    if parsed.operation == 'inspect':
        if not parsed.root:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'inspection requires --root')
        return read_command(Path(parsed.root), parsed, family='migrate')['data'].get('migration', {})
    if not parsed.input:
        raise WorkflowError('INVALID_INPUT', '--input is required')
    request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
    if parsed.operation == 'validate':
        return validate_increments(request['increments'], request['parity'])
    if parsed.operation == 'review-spec':
        return review_specification(request['spec'], request['source_index'])
    if parsed.operation == 'verify-pilot':
        return verify_pilot_command(parsed, request)
    return commit(parsed, 'domain.migrate.' + parsed.operation, request)


def verify_pilot_command(parsed, request):
    from workflow_lib.journal_domains import digest
    from workflow_lib.evidence import repository_fingerprint
    from workflow_lib.parity_runner import verify_pilot
    if not parsed.root or not parsed.operation_id_explicit:
        raise WorkflowError('OPERATION_ID_REQUIRED', 'pilot execution requires --root and --operation-id')
    root = Path(parsed.root)
    state = read_command(root, parsed, family='migrate', request=request)
    prior = state['operations'].get(parsed.operation_id)
    if prior:
        if prior['kind'] != 'domain.migrate.pilot-record' or prior['payload']['request'].get('execution') != request:
            raise WorkflowError('OPERATION_CONFLICT', 'pilot operation ID belongs to another request')
        return {**state['data']['domain_receipts'][parsed.operation_id], 'replayed': True}
    if parsed.operation_id + ':start' in state['operations']:
        raise WorkflowError('EXECUTION_INTERRUPTED', 'pilot execution was reserved; reconcile before a new execution')
    run = state['data'].get('runs', {}).get(request.get('run_id'), {})
    repo = state['data'].get('repositories', {}).get(request.get('repo_id'), {})
    attempts = run.get('items', {}).get(request.get('item_id'), {}).get('attempts', [])
    if not repo.get('location') or not attempts:
        raise WorkflowError('PILOT_SCOPE_INVALID', 'registered repository and current item attempt required')
    location = Path(repo['location'])
    fingerprint = repository_fingerprint(location)
    original_id = parsed.operation_id
    parsed.operation_id = original_id + ':start'
    parsed.expected_version = state['version'] if parsed.expected_version is None else parsed.expected_version
    started = commit(parsed, 'domain.migrate.pilot-start', {
        'execution_id': original_id, 'run_id': request['run_id'],
        'increment_id': request['increment_id'], 'criterion_id': request['criterion_id'],
        'item_id': request['item_id'], 'repo_id': request['repo_id'],
        'token': attempts[-1]['token'], 'migration_hash': state['data']['migration']['hash'],
        'pilot_hash': digest(request['pilot']), 'repository_fingerprint': fingerprint})
    if started['replayed']:
        raise WorkflowError('EXECUTION_INTERRUPTED', 'pilot execution was already reserved')
    result = verify_pilot(request['pilot'], location, request.get('timeout_seconds', 60))
    if repository_fingerprint(location) != fingerprint:
        result.update(passed=False, failure='REPOSITORY_CHANGED')
    proof = {**result, 'run_id': request['run_id'], 'increment_id': request['increment_id'],
             'criterion_id': request['criterion_id'], 'item_id': request['item_id'],
             'repo_id': request['repo_id'], 'token': attempts[-1]['token'],
             'pilot_hash': digest(request['pilot']), 'migration_hash': state['data']['migration']['hash'],
             'repository_fingerprint': fingerprint}
    proof['proof_id'] = digest(proof)
    parsed.operation_id = original_id
    parsed.expected_version = read_command(root, parsed, family='migrate', request=request)['version']
    return commit(parsed, 'domain.migrate.pilot-record', {'execution_id': original_id,
                  'run_id': request['run_id'], 'proof': proof, 'execution': request})
