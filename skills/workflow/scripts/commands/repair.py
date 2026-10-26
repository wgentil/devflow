"""Explicit bounded repair commands."""

import json
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity

from .journal import add_journal_options, commit
from workflow_lib.repair import repair_decision
from workflow_lib.repair_runtime import run_repair
from workflow_lib.store import WorkflowError


def register_commands(parser):
    group = parser.add_parser('repair')
    commands = group.add_subparsers(dest='repair_command', required=True)
    for name in ('configure', 'next', 'status', 'stop'):
        action = commands.add_parser(name)
        add_journal_options(action)
        action.add_argument('--run-id', required=True)
        if name == 'configure':
            action.add_argument('--input', required=True)
        if name == 'next':
            action.add_argument('--estimated-cost', type=float)
        if name == 'stop':
            action.add_argument('--reason-code', required=True)
            action.add_argument('--confirm-stopped-by')


def dispatch(parsed):
    if not parsed.root:
        raise WorkflowError('CONTROL_ROOT_REQUIRED', 'repair requires --root')
    root = Path(parsed.root)
    if parsed.repair_command == 'configure':
        policy = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
        return commit(parsed, 'domain.repair.configure', {'run_id': parsed.run_id, 'policy': policy})
    if parsed.repair_command == 'next':
        if not parsed.operation_id_explicit:
            raise WorkflowError('OPERATION_ID_REQUIRED', 'repair dispatch requires --operation-id')
        return run_repair(root, parsed.run_id, parsed.operation_id, parsed.estimated_cost)
    if parsed.repair_command == 'stop':
        request = {'run_id': parsed.run_id, 'reason_code': parsed.reason_code}
        if parsed.confirm_stopped_by:
            request['worker_stop_confirmation'] = {'approved': True,
                                                    'actor_id': parsed.confirm_stopped_by}
        return commit(parsed, 'domain.repair.stop', request)
    state = read_command(root, parsed, family='repair')
    run = state['data'].get('runs', {}).get(parsed.run_id)
    if not run:
        raise WorkflowError('RUN_UNAVAILABLE', 'known repair run required')
    import time
    return repair_decision(run, int(time.time() * 1000))
