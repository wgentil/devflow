"""Shared compare-and-swap journal boundary for auxiliary commands."""
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity
from workflow_lib.store import WorkflowError, transact


def add_journal_options(parser):
    parser.add_argument('--root')
    parser.add_argument('--operation-id')
    parser.add_argument('--expected-version', type=int)


def commit(parsed, kind, request):
    if not parsed.root:
        raise WorkflowError('CONTROL_ROOT_REQUIRED', 'mutations require --root')
    if not getattr(parsed, 'operation_id_explicit', False):
        raise WorkflowError('OPERATION_ID_REQUIRED', 'mutations require --operation-id for safe retry')
    root = Path(parsed.root).expanduser().resolve()
    state = read_current(root, global_keys=(), operations=(parsed.operation_id,))
    previous = state['operations'].get(parsed.operation_id)
    event = {'kind': kind, 'payload': {'request': request}}
    if previous is not None:
        if previous['kind'] != kind or previous['payload'] != event['payload']:
            raise WorkflowError('OPERATION_CONFLICT', 'operation ID belongs to a different request')
        return {**state['data']['domain_receipts'][parsed.operation_id],
                'replayed': True, 'state_version': state['version'],
                'event_sequence': previous['sequence']}
    expected = getattr(parsed, 'expected_version', None)
    if expected is None:
        expected = state['version']
    receipt = transact(root, expected, parsed.operation_id, event)
    # A writer may have committed this ID after our preflight. Verify its scope.
    if receipt['event']['kind'] != kind or receipt['event']['payload'] != event['payload']:
        raise WorkflowError('OPERATION_CONFLICT', 'operation ID belongs to a different request')
    return {**receipt['state']['data']['domain_receipts'][parsed.operation_id],
            'replayed': receipt['replayed'], 'state_version': receipt['state']['version'],
            'event_sequence': receipt['event']['sequence']}
