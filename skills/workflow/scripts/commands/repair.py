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
    for name in ('run', 'recover'):
        action = commands.add_parser(name)
        scope = action.add_mutually_exclusive_group(required=True)
        scope.add_argument('--root')
        scope.add_argument('--session')
        action.add_argument('--run-id')
        action.add_argument('--input', required=True)
        action.add_argument('--operation-id', required=True)
        if name == 'run':
            action.add_argument('--max-actions', type=int, required=True)
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
    if parsed.repair_command in {'run', 'recover'}:
        from workflow_lib.review_driver import run_orchestration, recover_orchestration
        request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
        if not isinstance(request, dict):
            raise WorkflowError('REVIEW_DRIVER_BLOCKED', 'A scoped object request is required.')
        session = bool(parsed.session)
        if session and parsed.run_id or not session and not parsed.run_id:
            raise WorkflowError('REVIEW_DRIVER_BLOCKED', 'Select a standalone session or a root with its actual run ID.')
        selection = {'session': True} if session else {'run_id': parsed.run_id}
        if any(request.get(k, v) != v for k, v in selection.items()) or ('run_id' in request if session else 'session' in request):
            raise WorkflowError('REVIEW_DRIVER_BLOCKED', 'Request scope differs from CLI selection.')
        request.update(selection)
        location = Path(parsed.session if session else parsed.root).expanduser().resolve()
        if parsed.repair_command == 'recover':
            return recover_orchestration(location, request, parsed.operation_id)
        return run_orchestration(location, request, parsed.operation_id, parsed.max_actions)
    if not parsed.root:
        raise WorkflowError('CONTROL_ROOT_REQUIRED', 'repair requires --root')
    root = Path(parsed.root)
    if parsed.repair_command == 'configure':
        policy = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
        return commit(parsed, 'domain.repair.configure', {'run_id': parsed.run_id, 'policy': policy})
    if parsed.repair_command == 'next':
        state=read_current(root,run_id=parsed.run_id)
        if state['data'].get('runs',{}).get(parsed.run_id,{}).get('review_orchestration'):
            return {'kind':'blocked','reason_code':'ORCHESTRATION_RUN_REQUIRED','next_action':'Use the explicit bounded repair run driver; legacy next remains one-shot.'}
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
