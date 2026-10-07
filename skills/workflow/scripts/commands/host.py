"""Explicit host/session coordination commands."""
import json
from pathlib import Path
from .journal import add_journal_options


def register_commands(parser):
    group = parser.add_parser('host')
    commands = group.add_subparsers(dest='host_command', required=True)
    init = commands.add_parser('init')
    add_journal_options(init)
    init.add_argument('--project-dir', required=True)
    for name in ('attach','detach','task-bind','handoff-prepare','handoff-accept'):
        action = commands.add_parser(name)
        add_journal_options(action)
        action.add_argument('--file', required=True)
        if name in {'attach','handoff-accept'}: action.add_argument('--loaded-release', required=True)
    status = commands.add_parser('status')
    status.add_argument('--root', required=True)
    status.add_argument('--host', choices=('claude','codex'), required=True)
    status.add_argument('--session-id', required=True)


def dispatch(parsed):
    if parsed.host_command == 'init':
        from workflow_lib.bootstrap import initialize_project
        return initialize_project(Path(parsed.project_dir), Path(parsed.root) if parsed.root else None,
                                  parsed.operation_id if parsed.operation_id_explicit else '', parsed.expected_version)
    from workflow_lib.store import read_state, WorkflowError
    from workflow_lib.hosts import binding_for_session
    if parsed.host_command == 'status':
        state = read_state(Path(parsed.root))
        binding = binding_for_session(state['data'],parsed.host,parsed.session_id)
        return {'binding':binding,'state_version':state['version']}
    request = json.loads(Path(parsed.file).read_text())
    if parsed.host_command in {'attach','handoff-accept'}:
        from workflow_lib.bootstrap import discover_project
        from workflow_lib.releases import release_descriptor, check_release
        installed = release_descriptor()
        loaded = json.loads(Path(parsed.loaded_release).read_text())
        decision = check_release(loaded,installed,1)
        if decision['status'] != 'allow': raise WorkflowError('RELEASE_MISMATCH',decision['message'],decision)
        target = request if parsed.host_command == 'attach' else request['destination']
        target['project_dir'] = str(discover_project(Path(target['project_dir'])))
        target['release'] = installed
        from workflow_lib.releases import PACKAGE_ROOT
        target['package_root'] = str(PACKAGE_ROOT)
        if parsed.host_command == 'handoff-accept':
            state = read_state(Path(parsed.root))
            prepared = state['data'].get('host_handoffs', {}).get(request['handoff_id'], {})
            source = state['data'].get('host_bindings', {}).get(prepared.get('binding_id'), {})
            if not source.get('package_root'): raise WorkflowError('SOURCE_RELEASE_UNKNOWN','Source attachment must record its installed package root.')
            source_root = Path(source['package_root'])
            source_release = release_descriptor(source_root)
            request['source_release'] = source_release
            request['destination_release'] = installed
            request['destination_decision'] = {'status':'block','reason_code':'MODEL_POLICY_UNRESOLVED'}
            # Repeat reads immediately before committing; no cached source identity is sufficient.
            if release_descriptor(source_root) != source_release or release_descriptor() != installed:
                raise WorkflowError('RELEASE_CHANGED','Package changed during transfer; source owner unchanged.')
    from .journal import commit
    result = commit(parsed,'domain.host.'+parsed.host_command,request)
    if parsed.host_command in {'attach','handoff-accept'}:
        from workflow_lib.host_locators import write_locator
        write_locator(Path(result['project_dir']),result['host'],result['session_id'],Path(parsed.root),result['binding_id'])
    return result
