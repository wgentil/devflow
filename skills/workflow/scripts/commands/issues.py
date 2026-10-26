"""Journal-backed local issue workflows; connector dispatch is separate."""
import json
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity
from .journal import add_journal_options, commit
from workflow_lib.issues import validate_snapshot
from workflow_lib.store import WorkflowError


def register_commands(parser):
    command = parser.add_parser('issues')
    command.add_argument('operation', choices=['capture','snapshot','validate-snapshot','group','start','classify','authorize-write','enqueue','inspect'])
    command.add_argument('--input')
    add_journal_options(command)


def dispatch(parsed):
    if parsed.operation == 'inspect':
        if not parsed.root:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'inspection requires --root')
        data = read_command(Path(parsed.root), parsed, family='issues')['data']
        return {k: data.get(k, {}) for k in ('issues','snapshots','groups','issue_runs','classifications','outbox')}
    if not parsed.input:
        raise WorkflowError('INVALID_INPUT', '--input is required')
    request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
    if parsed.operation == 'validate-snapshot':
        return validate_snapshot(request['snapshot'])
    return commit(parsed, 'domain.issues.' + parsed.operation, request)
