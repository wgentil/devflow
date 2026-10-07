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
    for name in ('attach','detach','task-bind','handoff-prepare','handoff-accept','model-override','model-receipt','model-interrupt','legacy-adopt'):
        action = commands.add_parser(name)
        add_journal_options(action)
        action.add_argument('--file', required=True)
        if name in {'attach','handoff-accept','legacy-adopt'}: action.add_argument('--loaded-release', required=True)
    resolve = commands.add_parser('profile-resolve')
    resolve.add_argument('--root', required=True)
    resolve.add_argument('--binding-id', required=True)
    resolve.add_argument('--revision',type=int,required=True)
    resolve.add_argument('--stage',required=True)
    hook=commands.add_parser('hook-evaluate')
    hook.add_argument('--project-dir',required=True)
    hook.add_argument('--session-id',required=True)
    hook.add_argument('--event',choices=('SessionStart','UserPromptSubmit','TaskCompleted','Stop'),required=True)
    hook.add_argument('--task-id')
    check=commands.add_parser('check')
    check.add_argument('--root', required=True)
    check.add_argument('--binding-id', required=True)
    check.add_argument('--task-id', required=True)
    status = commands.add_parser('status')
    status.add_argument('--root', required=True)
    status.add_argument('--host', choices=('claude','codex'), required=True)
    status.add_argument('--session-id', required=True)


def dispatch(parsed):
    if parsed.host_command == 'hook-evaluate':
        from workflow_lib.host_hook import evaluate
        return evaluate(parsed.project_dir,parsed.session_id,parsed.event,parsed.task_id)
    if parsed.host_command == 'init':
        from workflow_lib.bootstrap import initialize_project
        return initialize_project(Path(parsed.project_dir), Path(parsed.root) if parsed.root else None,
                                  parsed.operation_id if parsed.operation_id_explicit else '', parsed.expected_version)
    from workflow_lib.store import read_state, WorkflowError
    from workflow_lib.hosts import binding_for_session
    if parsed.host_command == 'check':
        from workflow_lib.host_completion import check_completion
        state=read_state(Path(parsed.root))
        binding=state['data'].get('host_bindings',{}).get(parsed.binding_id)
        if not binding: raise WorkflowError('BINDING_REQUIRED','Known binding required.')
        from workflow_lib.releases import release_descriptor
        return check_completion(state['data'],binding,parsed.task_id,installed_release=release_descriptor())
    if parsed.host_command == 'status':
        state = read_state(Path(parsed.root))
        binding = binding_for_session(state['data'],parsed.host,parsed.session_id)
        from workflow_lib.host_completion import host_brief
        from workflow_lib.journal_domains import digest
        mappings=[{**task,'mapping_hash':digest(task)} for task in state['data'].get('host_tasks',{}).values()
                  if binding and task['host']==binding['host'] and task['session_id']==binding['session_id']]
        return {'binding':binding,'brief':host_brief(state['data'],binding) if binding else None,'task_mappings':mappings,'state_version':state['version']}
    if parsed.host_command == 'profile-resolve':
        from workflow_lib.hosts import validate_binding
        state=read_state(Path(parsed.root))
        binding=validate_binding(state['data'],parsed.binding_id,parsed.revision)
        return _resolve_model(state['data'],binding,parsed.stage)
    request = json.loads(Path(parsed.file).read_text())
    if not isinstance(request,dict):raise ValueError('host request must be an object')
    if parsed.host_command in {'attach','handoff-accept','legacy-adopt'}:
        from workflow_lib.bootstrap import discover_project
        from workflow_lib.releases import release_descriptor, check_release
        installed = release_descriptor()
        loaded = json.loads(Path(parsed.loaded_release).read_text())
        decision = check_release(loaded,installed,1)
        if decision['status'] != 'allow': raise WorkflowError('RELEASE_MISMATCH',decision['message'],decision)
        target = request if parsed.host_command in {'attach','legacy-adopt'} else request['destination']
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
    if request.get('binding_id') and parsed.host_command not in {'attach','legacy-adopt'}:
        from workflow_lib.hosts import validate_binding
        from workflow_lib.releases import release_descriptor, check_release
        state=read_state(Path(parsed.root))
        bound=validate_binding(state['data'],request['binding_id'],request.get('revision'))
        parity=check_release(bound['release'],release_descriptor(),1)
        if parity['status'] != 'allow':raise WorkflowError('RELEASE_MISMATCH',parity['message'],parity)

    if parsed.host_command == 'model-receipt':
        from workflow_lib.hosts import validate_binding
        state=read_state(Path(parsed.root))
        binding=validate_binding(state['data'],request['binding_id'],request['revision'])
        invocation_id=request['receipt'].get('invocation_id')
        stage=request['receipt'].get('stage','implementation')
        request['receipt']={**_resolve_model(state['data'],binding,stage),'invocation_id':invocation_id,'stage':stage}
    from .journal import commit
    from workflow_lib.store import LIVE_TRANSFER, HOST_CONTEXT
    binding_token=None
    if request.get('binding_id') and parsed.host_command not in {'attach','legacy-adopt'}:
        binding_token=HOST_CONTEXT.set({'binding_id':bound['binding_id'],'revision':bound['revision'],'release':bound['release']})
    preflight_token=None
    if parsed.host_command == 'handoff-accept':
        def check_installed():
            if release_descriptor(source_root) != source_release or release_descriptor() != installed:
                raise WorkflowError('RELEASE_CHANGED','Package changed before locked transfer; source owner unchanged.')
        preflight_token=LIVE_TRANSFER.set(check_installed)
    try:result = commit(parsed,'domain.host.'+parsed.host_command,request)
    finally:
        if preflight_token is not None:LIVE_TRANSFER.reset(preflight_token)
        if binding_token is not None:HOST_CONTEXT.reset(binding_token)
    if parsed.host_command in {'attach','handoff-accept','legacy-adopt'}:
        from workflow_lib.host_locators import write_locator
        write_locator(Path(result['project_dir']),result['host'],result['session_id'],Path(parsed.root),result['binding_id'])
    if parsed.host_command == 'task-bind':
        from workflow_lib.host_locators import write_task_index
        state=read_state(Path(parsed.root))['data']
        binding=state['host_bindings'][result['binding_id']]
        tasks=[t['task_id'] for t in state.get('host_tasks',{}).values() if t['host']==binding['host'] and t['session_id']==binding['session_id']]
        write_task_index(Path(binding['project_dir']),binding['host'],binding['session_id'],Path(parsed.root),tasks)
    return result


def _resolve_model(data, binding, stage):
    from workflow_lib.releases import PACKAGE_ROOT
    from workflow_lib.model_policy import resolve_profile
    policy=json.loads((PACKAGE_ROOT/'definitions/model-policy.json').read_text())
    run=data['runs'][binding['run_id']]
    override=next((entry for entry in reversed(run.get('model_overrides', [])) if entry.get('stage') in {None,stage}), {})
    request={**override,'host':binding['host'],'stage':stage}
    # The portable CLI has no authenticated host launch/observation API.
    return resolve_profile(policy,request,{'configure':False,'observe':False,'models':[],'efforts':[]},{},None)
