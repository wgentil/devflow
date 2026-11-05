"""Explicit enforcement adoption and read-only policy diagnostics."""
import json
from pathlib import Path
from .journal import add_journal_options, commit
from workflow_lib.action_policy import subject_decision
from workflow_lib.storage_access import read_current
from workflow_lib.store import WorkflowError


def register_commands(parser):
    group = parser.add_parser('enforcement')
    actions = group.add_subparsers(dest='enforcement_command', required=True)
    for name in ('decide', 'adopt', 'question', 'answer', 'propose-fix', 'close-finding', 'configure-effects', 'claim', 'effect-transition', 'observe-source', 'protect-inventory'):
        command = actions.add_parser(name)
        add_journal_options(command)
        command.add_argument('--input', required=True)
    for name in ('session-init', 'session-event', 'session-status'):
        command = actions.add_parser(name)
        command.add_argument('--session', required=True)
        if name != 'session-status': command.add_argument('--input', required=True)
        if name == 'session-event':
            command.add_argument('--operation-id', required=True)
            command.add_argument('--expected-version', required=True, type=int)


def dispatch(parsed):
    if parsed.enforcement_command.startswith('session-'):
        from workflow_lib.review_sessions import initialize_session, read_session, transact_session
        path = Path(parsed.session)
        if parsed.enforcement_command == 'session-status': return read_session(path)
        request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
        if parsed.enforcement_command == 'session-init': return initialize_session(path, request)
        return transact_session(path, parsed.expected_version, parsed.operation_id, request)

    request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
    if parsed.enforcement_command == 'protect-inventory':
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.storage_access import operation_lookup
        prior = operation_lookup(Path(parsed.root), parsed.operation_id)
        if prior:
            previous = prior.get('payload', {}).get('request', {})
            previous_record = {k:v for k,v in previous.get('record', {}).items() if k != 'baseline'}
            current_record = {k:v for k,v in request.get('record', {}).items() if k != 'baseline'}
            if (prior.get('kind') != 'domain.enforcement.protect-inventory'
                    or previous.get('run_id') != request.get('run_id') or previous_record != current_record):
                raise WorkflowError('OPERATION_CONFLICT', 'Operation belongs to a different protection request.')
            return commit(parsed, prior['kind'], previous)
        state = read_current(Path(parsed.root), run_id=request['run_id'])
        subject = state['data']['runs'][request['run_id']]
        record = request['record']
        repo = subject['repositories'][record['repo_id']]
        request = {**request, 'record': {**record, 'baseline': snapshot_protected(Path(repo['location']), record['inventory'])}}
        parsed.expected_version = state['version']
    if parsed.enforcement_command == 'observe-source':
        from workflow_lib.enforcement_live import source_observation
        from workflow_lib.storage_access import operation_lookup
        prior = operation_lookup(Path(parsed.root), parsed.operation_id)
        if prior and prior.get('kind') == 'domain.enforcement.observe-source' and prior['payload']['request'].get('run_id') == request.get('run_id'):
            return commit(parsed, prior['kind'], prior['payload']['request'])
        state = read_current(Path(parsed.root), run_id=request['run_id'])
        subject = state['data'].get('runs', {}).get(request['run_id'])
        if not subject: raise WorkflowError('RUN_UNAVAILABLE', 'Known run required.')
        request = {'run_id': request['run_id'], 'record': source_observation(subject)}
        parsed.expected_version = state['version']
    if parsed.enforcement_command != 'decide':
        return commit(parsed, 'domain.enforcement.' + parsed.enforcement_command, request)
    if not parsed.root:
        raise WorkflowError('CONTROL_ROOT_REQUIRED', 'decision diagnostics require --root')
    state = read_current(Path(parsed.root), run_id=request['run_id'])
    run = state['data'].get('runs', {}).get(request['run_id'])
    if run is None:
        raise WorkflowError('RUN_UNAVAILABLE', 'known run required')
    return subject_decision(run, request['action'], request.get('scope', {}))
