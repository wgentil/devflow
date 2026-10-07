"""Journal-backed migration plans, evidence, and delivery ordering."""
import json
from pathlib import Path
from .journal import add_journal_options, commit
from workflow_lib.migrations import validate_increments, review_specification
from workflow_lib.store import read_state, WorkflowError


def register_commands(parser):
    command = parser.add_parser('migrate')
    command.add_argument('operation', choices=['validate','store','review-spec','record-parity','bind','delivered','inspect'])
    command.add_argument('--input')
    add_journal_options(command)


def dispatch(parsed):
    if parsed.operation == 'inspect':
        if not parsed.root:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'inspection requires --root')
        return read_state(Path(parsed.root))['data'].get('migration', {})
    if not parsed.input:
        raise WorkflowError('INVALID_INPUT', '--input is required')
    request = json.loads(Path(parsed.input).read_text())
    if parsed.operation == 'validate':
        return validate_increments(request['increments'], request['parity'])
    if parsed.operation == 'review-spec':
        return review_specification(request['spec'], request['source_index'])
    return commit(parsed, 'domain.migrate.' + parsed.operation, request)
