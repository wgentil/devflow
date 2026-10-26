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
    for name in ('attach','detach','task-bind','handoff-prepare','handoff-accept','model-override','model-receipt','model-interrupt','legacy-adopt','goal-bind'):
        action = commands.add_parser(name)
        add_journal_options(action)
        action.add_argument('--file', required=True)
        if name in {'attach','handoff-accept','legacy-adopt'}: action.add_argument('--loaded-release', required=True)
    preparation = commands.add_parser('delegation-prepare')
    preparation.add_argument('--root', required=True)
    preparation.add_argument('--file', required=True)
    for name in ('model-discover','model-probe'):
        action=commands.add_parser(name)
        action.add_argument('--root',required=True)
        action.add_argument('--binding-id',required=True)
        action.add_argument('--revision',type=int,required=True)
        action.add_argument('--stage',default='implementation')
        action.add_argument('--refresh',action='store_true')
    for name in ('model-run','model-reconcile'):
        native=commands.add_parser(name)
        native.add_argument('--root',required=True)
        native.add_argument('--operation-id',required=True)
        native.add_argument('--file',required=True)
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
    goal_status = commands.add_parser('goal-status')
    goal_status.add_argument('--root', required=True)
    goal_status.add_argument('--binding-id', required=True)
    brief = commands.add_parser('brief')
    brief.add_argument('--root', required=True)
    brief.add_argument('--binding-id', required=True)
    brief.add_argument('--revision', required=True, type=int)
    brief.add_argument('--max-bytes', type=int, default=20000)
    brief.add_argument('--representation', choices=('markdown', 'json'), default='markdown')
    brief.add_argument('--output-mode', choices=('full', 'refs'), default='full')
    brief.add_argument('--consumer-id')
    checkpoint_options = brief.add_mutually_exclusive_group()
    checkpoint_options.add_argument('--since-checkpoint')
    checkpoint_options.add_argument('--full-context', action='store_true')


def dispatch(parsed):
    if getattr(parsed,'host_command',None) in {'handoff-prepare','handoff-accept'}:
        from workflow_lib.storage_pins import reserve
        with reserve(Path(parsed.root),'host-transfer'):return _dispatch(parsed)
    return _dispatch(parsed)


def _dispatch(parsed):
    if parsed.host_command == 'delegation-prepare':
        from workflow_lib.interactive_routing import prepare_delegation
        request = json.loads(Path(parsed.file).read_text(encoding='utf-8'))
        if not isinstance(request, dict):raise WorkflowError('NATIVE_INPUT_REQUIRED', 'Delegation request must be an object.')
        return prepare_delegation(Path(parsed.root), request)
    if parsed.host_command == 'hook-evaluate':
        from workflow_lib.host_hook import evaluate
        return evaluate(parsed.project_dir,parsed.session_id,parsed.event,parsed.task_id)
    if parsed.host_command == 'init':
        from workflow_lib.bootstrap import initialize_project
        return initialize_project(Path(parsed.project_dir), Path(parsed.root) if parsed.root else None,
                                  parsed.operation_id if parsed.operation_id_explicit else '', parsed.expected_version)
    from workflow_lib.store import WorkflowError
    from workflow_lib.host_projection import read_host
    from workflow_lib.hosts import binding_for_session
    if parsed.host_command == 'brief':
        from workflow_lib.hosts import validate_binding
        from workflow_lib.host_completion import host_brief
        from workflow_lib.context_preparation import read_context_state
        authoritative=read_context_state(Path(parsed.root),binding_id=parsed.binding_id);data=authoritative['data']
        binding = validate_binding(data, parsed.binding_id, parsed.revision)
        view = host_brief(data, binding, control_root=Path(parsed.root), max_bytes=parsed.max_bytes,
                          representation=parsed.representation, output_mode=parsed.output_mode,authoritative_state=authoritative)
        from workflow_lib.context_checkpoints import checkpoint_read
        return checkpoint_read(Path(parsed.root), view, {'consumer_id': parsed.consumer_id or binding['session_id'],
            'run_id': binding['run_id'], 'binding_id': binding['binding_id'], 'session_id': binding['session_id'],
            'revision': binding['revision'], 'role': binding['role'], 'stage': view['stage'],
            'task_ids': [item['id'] for item in view['work_items']]},
            since=parsed.since_checkpoint, full=parsed.full_context)
    if parsed.host_command in {'model-run','model-reconcile'}:
        if not parsed.root or not parsed.operation_id_explicit:raise WorkflowError('OPERATION_ID_REQUIRED','Native invocation needs control root and explicit operation ID.')
        from workflow_lib.native_runtime import invoke, reconcile
        request=json.loads(Path(parsed.file).read_text(encoding='utf-8'))
        if not isinstance(request,dict):raise WorkflowError('NATIVE_INPUT_REQUIRED','Native request must be an object.')
        return (invoke if parsed.host_command=='model-run' else reconcile)(Path(parsed.root),request,parsed.operation_id)
    if parsed.host_command in {'model-discover','model-probe'}:
        from workflow_lib.hosts import validate_binding
        from workflow_lib.releases import check_release, release_descriptor
        state=read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'));binding=validate_binding(state['data'],parsed.binding_id,parsed.revision)
        parity=check_release(binding['release'],release_descriptor(),1)
        if parity['status']!='allow':raise WorkflowError('RELEASE_MISMATCH',parity['message'])
        from workflow_lib.native_runtime import discover, probe
        if parsed.host_command=='model-probe':return probe(Path(parsed.root),binding,parsed.stage,parsed.refresh)
        return discover(Path(parsed.root),binding,parsed.refresh)
    if parsed.host_command == 'check':
        from workflow_lib.host_completion import check_completion
        state=read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))
        binding=state['data'].get('host_bindings',{}).get(parsed.binding_id)
        if not binding: raise WorkflowError('BINDING_REQUIRED','Known binding required.')
        from workflow_lib.releases import release_descriptor
        return check_completion(state['data'],binding,parsed.task_id,installed_release=release_descriptor(),control_root=Path(parsed.root))
    if parsed.host_command == 'status':
        state = read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))
        binding = binding_for_session(state['data'],parsed.host,parsed.session_id)
        from workflow_lib.host_completion import host_brief
        from workflow_lib.journal_domains import digest
        mappings=[{**task,'mapping_hash':digest(task)} for task in state['data'].get('host_tasks',{}).values()
                  if binding and task['host']==binding['host'] and task['session_id']==binding['session_id']]
        return {'binding':binding,'brief':host_brief(state['data'],binding) if binding else None,'task_mappings':mappings,'state_version':state['version']}
    if parsed.host_command == 'goal-status':
        state = read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))['data']
        binding = state.get('host_bindings', {}).get(parsed.binding_id)
        if not binding: raise WorkflowError('BINDING_REQUIRED', 'known binding required')
        from workflow_lib.goals import goal_contract
        from workflow_lib.journal_domains import digest
        run = state['runs'][binding['run_id']]
        contract = goal_contract(run)
        return {'binding': run.get('goal_bindings', {}).get(binding['binding_id']),
                'contract': contract, 'contract_hash': digest(contract),
                'capability': 'manual-host-goal-lifecycle'}
    if parsed.host_command == 'profile-resolve':
        from workflow_lib.hosts import validate_binding
        state=read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))
        binding=validate_binding(state['data'],parsed.binding_id,parsed.revision)
        return _resolve_model(state['data'],binding,parsed.stage,parsed.root)
    request = json.loads(Path(parsed.file).read_text(encoding='utf-8'))
    if not isinstance(request,dict):raise ValueError('host request must be an object')
    from workflow_lib.journal_domains import digest
    client={'kind':parsed.host_command,'request':request}
    if getattr(parsed,'loaded_release',None):client['loaded_release']=json.loads(Path(parsed.loaded_release).read_text(encoding='utf-8'))
    client_hash=digest(client)
    if getattr(parsed,'operation_id_explicit',False) and parsed.root:
        prior_state=read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))
        previous=prior_state['operations'].get(parsed.operation_id)
        if previous:
            if previous['kind'] != 'domain.host.'+parsed.host_command or previous['payload'].get('request',{}).get('client_request_hash') != client_hash:
                raise WorkflowError('OPERATION_CONFLICT','Operation ID belongs to a different host request.')
            # A committed response is read-only: its original precondition may now be stale.
            from .journal import commit
            result=commit(parsed,previous['kind'],previous['payload']['request'])
            if parsed.host_command in {'attach','handoff-accept','legacy-adopt'}:
                current=prior_state['data'].get('host_bindings',{}).get(result.get('binding_id'),{})
                if current.get('status')=='active' and current.get('revision')==result.get('revision'):
                    from workflow_lib.host_locators import write_locator
                    write_locator(Path(current['project_dir']),current['host'],current['session_id'],Path(parsed.root),current['binding_id'])
                    _repair_task_index(prior_state['data'],current,Path(parsed.root))
                    _repair_retired_task_indexes(prior_state['data'],current,Path(parsed.root))
            if parsed.host_command == 'task-bind':
                _repair_task_index(prior_state['data'],result,Path(parsed.root))
            return result
    # Committed retry lookup and request-hash validation above are read-only;
    # live specification preflight applies only to a new handoff operation.
    if parsed.host_command in {'handoff-prepare', 'handoff-accept'} and parsed.root:
        gate_state = read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))
        if gate_state['data'].get('spec_pair'):
            from workflow_lib.repo_input_gate import require_current_inputs
            data = gate_state['data']
            binding = data.get('host_bindings', {}).get(request.get('binding_id'), {})
            envelope = data.get('host_handoffs', {}).get(request.get('handoff_id'), {})
            run_id = binding.get('run_id') or envelope.get('run_id')
            require_current_inputs(Path(parsed.root), gate_state, 'handoff', run_id)
    request['client_request_hash']=client_hash

    if parsed.host_command in {'attach','handoff-accept','legacy-adopt'}:
        from workflow_lib.bootstrap import discover_project
        from workflow_lib.releases import release_descriptor, check_release
        installed = release_descriptor()
        loaded = json.loads(Path(parsed.loaded_release).read_text(encoding='utf-8'))
        decision = check_release(loaded,installed,1)
        if decision['status'] != 'allow': raise WorkflowError('RELEASE_MISMATCH',decision['message'],decision)
        target = request if parsed.host_command in {'attach','legacy-adopt'} else request['destination']
        target['project_dir'] = str(discover_project(Path(target['project_dir'])))
        target['release'] = installed
        from workflow_lib.releases import PACKAGE_ROOT
        target['package_root'] = str(PACKAGE_ROOT)
        if parsed.host_command == 'handoff-accept':
            state = read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))
            prepared = state['data'].get('host_handoffs', {}).get(request['handoff_id'], {})
            source = state['data'].get('host_bindings', {}).get(prepared.get('binding_id'), {})
            if not source.get('package_root'): raise WorkflowError('SOURCE_RELEASE_UNKNOWN','Source attachment must record its installed package root.')
            source_root = Path(source['package_root'])
            source_release = release_descriptor(source_root)
            request['source_release'] = source_release
            request['destination_release'] = installed
            from workflow_lib.hosts import _identity, require
            _identity(target)
            require(target['host']==prepared.get('target_host') and target['actor_id']==prepared.get('target_actor_id') and target['run_id']==source.get('run_id') and target['project_dir']==source.get('project_dir') and target['role']=='implementer' and (not prepared.get('target_session_id') or target['session_id']==prepared['target_session_id']), 'Destination differs from prepared target.')
            from workflow_lib.native_runtime import handoff_preflight
            request['destination_decision'] = handoff_preflight(Path(parsed.root),state['data'],target)
            # Repeat reads immediately before committing; no cached source identity is sufficient.
            if release_descriptor(source_root) != source_release or release_descriptor() != installed:
                raise WorkflowError('RELEASE_CHANGED','Package changed during transfer; source owner unchanged.')
    if request.get('binding_id') and parsed.host_command not in {'attach','legacy-adopt'}:
        from workflow_lib.hosts import validate_binding
        from workflow_lib.releases import release_descriptor, check_release
        state=read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))
        bound=validate_binding(state['data'],request['binding_id'],request.get('revision'))
        parity=check_release(bound['release'],release_descriptor(),1)
        if parity['status'] != 'allow':raise WorkflowError('RELEASE_MISMATCH',parity['message'],parity)

    if parsed.host_command == 'model-receipt':
        from workflow_lib.hosts import validate_binding
        state=read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))
        binding=validate_binding(state['data'],request['binding_id'],request['revision'])
        invocation_id=request['receipt'].get('invocation_id')
        stage=request['receipt'].get('stage','implementation')
        request['resolution_policy_revision']=len(state['data']['runs'][binding['run_id']].get('model_overrides',[]))
        request['receipt']={**_resolve_model(state['data'],binding,stage,parsed.root),'invocation_id':invocation_id,'stage':stage}
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
        current_data=read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))['data']
        _repair_task_index(current_data,result,Path(parsed.root))
        _repair_retired_task_indexes(current_data,result,Path(parsed.root))
    if parsed.host_command == 'task-bind':
        _repair_task_index(read_host(Path(parsed.root),binding_id=getattr(parsed,'binding_id',None),host=getattr(parsed,'host',None),session_id=getattr(parsed,'session_id',None),operation_id=getattr(parsed,'operation_id',None),request=locals().get('request'))['data'],result,Path(parsed.root))
    return result


def _resolve_model(data, binding, stage, root=None):
    from workflow_lib.model_policy import resolve_host_profile
    return resolve_host_profile(data,binding,stage,root)


def _repair_task_index(data, result, root):
    from workflow_lib.host_locators import write_task_index
    binding=data.get('host_bindings',{}).get(result['binding_id'],{})
    if binding.get('status')!='active' or binding.get('revision')!=result.get('revision'):return
    tasks=[t['task_id'] for t in data.get('host_tasks',{}).values() if t.get('binding_id')==binding['binding_id'] and t['host']==binding['host'] and t['session_id']==binding['session_id']]
    write_task_index(Path(binding['project_dir']),binding['host'],binding['session_id'],root,tasks)


def _repair_retired_task_indexes(data, current, root):
    from workflow_lib.host_locators import read_locator, write_task_index
    from workflow_lib.store import WorkflowError
    # Attachment and exact retries repair stale project hints from retired
    # session metadata without expanding any retired run or review payload.
    from workflow_lib.storage_format import detect_layout
    statuses={key:run.get('status') for key,run in data.get('runs',{}).items()}
    bindings=dict(data.get('host_bindings',{}))
    if detect_layout(root)['layout']=='v2':
        from workflow_lib import sqlite_store as sql
        from workflow_lib.storage_scopes import ReadScope,EntityQuery
        with sql.connection(root) as conn:
            retired=sql._read_view(conn,root,ReadScope(global_keys=(),queries=(EntityQuery('host_bindings',
                (('host',current['host']),('session_id',current['session_id']),('status','detached'))),)))[0]
            bindings.update(retired['data'].get('host_bindings',{}))
            for binding in bindings.values():
                row=conn.execute('SELECT status FROM entities WHERE space=? AND key=?',
                    (sql._space(('runs',)),binding['run_id'])).fetchone()
                if row is not None:statuses[binding['run_id']]=row[0]
    for binding in bindings.values():
        if (binding['binding_id'] == current['binding_id'] or binding['host'] != current['host']
                or binding['session_id'] != current['session_id'] or binding['status'] != 'detached'
                or binding['project_dir'] == current['project_dir']
                or statuses.get(binding['run_id']) not in {'delivered','discarded'}):
            continue
        project=Path(binding['project_dir'])
        if not project.is_dir():continue
        try:locator=read_locator(project,binding['host'],binding['session_id'])
        except WorkflowError:continue
        if locator and locator['binding_id']==binding['binding_id'] and Path(locator['control_root']).resolve()==Path(root).resolve():
            write_task_index(project,binding['host'],binding['session_id'],root,[])
