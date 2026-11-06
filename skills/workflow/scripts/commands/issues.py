"""Journal-backed local issue workflows; connector dispatch is separate."""
import json
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity
from .journal import add_journal_options, commit
from workflow_lib.issues import validate_snapshot
from workflow_lib.store import WorkflowError


def register_commands(parser):
    command = parser.add_parser('issues')
    command.add_argument('operation', choices=['capture','snapshot','validate-snapshot','group','start','classify','authorize-write','enqueue','inspect','replay-recovery-inspect','replay-recovery-validate','replay-recovery-apply'])
    command.add_argument('--input')
    add_journal_options(command)


def dispatch(parsed):
    if parsed.operation.startswith('replay-recovery-'):
        from workflow_lib.issue_replay_recovery import (inspect_replay_recovery,
            validate_replay_recovery, apply_replay_recovery)
        if not parsed.root:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'Recovery requires an explicit root.')
        if parsed.operation == 'replay-recovery-inspect':
            return inspect_replay_recovery(Path(parsed.root))
        if not parsed.input or not getattr(parsed, 'operation_id_explicit', False):
            raise WorkflowError('OPERATION_ID_REQUIRED', 'Recovery requires input and explicit operation ID.')
        request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
        if not isinstance(request, dict):
            raise WorkflowError('INVALID_INPUT', 'Issue request must be an object.')
        if request.get('operation_id') != parsed.operation_id:
            raise WorkflowError('OPERATION_CONFLICT', 'Recovery input and command operation IDs must match.')
        action = validate_replay_recovery if parsed.operation == 'replay-recovery-validate' else apply_replay_recovery
        return action(Path(parsed.root), request)
    if parsed.operation == 'inspect':
        if not parsed.root:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'inspection requires --root')
        data = read_command(Path(parsed.root), parsed, family='issues')['data']
        return {k: data.get(k, {}) for k in ('issues','snapshots','groups','issue_runs','classifications','outbox')}
    if not parsed.input:
        raise WorkflowError('INVALID_INPUT', '--input is required')
    request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
    if not isinstance(request, dict):
        raise WorkflowError('INVALID_INPUT', 'Issue request must be an object.')
    if parsed.operation == 'validate-snapshot':
        return validate_snapshot(request['snapshot'])
    if parsed.operation == 'start' and request.get('intent') == 'build':
        from workflow_lib.issue_run_contracts import current_run_contract
        if not parsed.root or not getattr(parsed, 'operation_id_explicit', False):
            raise WorkflowError('OPERATION_ID_REQUIRED', 'Root and explicit operation ID required.')
        previous = operation_lookup(Path(parsed.root), parsed.operation_id)
        if previous is not None:
            recorded = previous['payload'].get('request', {})
            comparison = dict(recorded)
            if 'run_contract' not in request: comparison.pop('run_contract', None)
            if previous['kind'] != 'domain.issues.start' or comparison != request:
                raise WorkflowError('OPERATION_CONFLICT', 'Issue-start operation belongs to another request.')
            request = recorded
        else:
            contract = current_run_contract()
            if 'run_contract' in request and request['run_contract'] != contract:
                raise WorkflowError('ISSUE_RUN_CONTRACT_INVALID', 'New issue starts require current policy.')
            request = {**request, 'run_contract': contract}
    return commit(parsed, 'domain.issues.' + parsed.operation, request)
