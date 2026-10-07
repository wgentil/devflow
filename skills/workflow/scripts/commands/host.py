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
    for name in ('attach','detach','task-bind','handoff-prepare','handoff-accept','model-override','model-receipt','model-interrupt'):
        action = commands.add_parser(name)
        add_journal_options(action)
        action.add_argument('--file', required=True)
        if name in {'attach','handoff-accept'}: action.add_argument('--loaded-release', required=True)
    resolve = commands.add_parser('profile-resolve')
    resolve.add_argument('--root', required=True)
    resolve.add_argument('--binding-id', required=True)
    resolve.add_argument('--revision',type=int,required=True)
    resolve.add_argument('--stage',required=True)
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
    if parsed.host_command == 'profile-resolve':
        from workflow_lib.hosts import validate_binding
        state=read_state(Path(parsed.root))
        binding=validate_binding(state['data'],parsed.binding_id,parsed.revision)
        return _resolve_model(state['data'],binding,parsed.stage)
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
            request['destination_decision'] = _resolve_model(state['data'],target,'implementation')
            # Repeat reads immediately before committing; no cached source identity is sufficient.
            if release_descriptor(source_root) != source_release or release_descriptor() != installed:
                raise WorkflowError('RELEASE_CHANGED','Package changed during transfer; source owner unchanged.')
    if parsed.host_command == 'model-receipt':
        from workflow_lib.hosts import validate_binding
        state=read_state(Path(parsed.root))
        binding=validate_binding(state['data'],request['binding_id'],request['revision'])
        invocation_id=request['receipt'].get('invocation_id')
        stage=request['receipt'].get('stage','implementation')
        request['receipt']={**_resolve_model(state['data'],binding,stage),'invocation_id':invocation_id,'stage':stage}
    from .journal import commit
    result = commit(parsed,'domain.host.'+parsed.host_command,request)
    if parsed.host_command in {'attach','handoff-accept'}:
        from workflow_lib.host_locators import write_locator
        write_locator(Path(result['project_dir']),result['host'],result['session_id'],Path(parsed.root),result['binding_id'])
    return result


def _resolve_model(data, binding, stage):
    from workflow_lib.releases import PACKAGE_ROOT
    from workflow_lib.model_policy import resolve_profile
    policy=json.loads((PACKAGE_ROOT/'definitions/model-policy.json').read_text())
    run=data['runs'][binding['run_id']]
    override=run.get('model_overrides', [{}])[-1]
    request={**override,'host':binding['host'],'stage':stage}
    # The portable CLI has no authenticated host launch/observation API.
    return resolve_profile(policy,request,{'configure':False,'observe':False,'models':[],'efforts':[]},{},None)
