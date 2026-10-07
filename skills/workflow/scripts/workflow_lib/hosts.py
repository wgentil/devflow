"""Deterministic host bindings and task scopes. Journal owns all authority."""
from copy import deepcopy
from .store import WorkflowError

ROLES = {'implementer', 'item-reviewer', 'branch-reviewer', 'acceptance-reviewer'}
HOSTS = {'claude', 'codex'}


def require(condition, message, code='HOST_CONFLICT'):
    if not condition: raise WorkflowError(code, message)


def binding_for_session(state: dict, host: str, session_id: str) -> dict | None:
    values = [b for b in state.get('host_bindings', {}).values()
              if b['host'] == host and b['session_id'] == session_id and b['status'] == 'active']
    require(len(values) <= 1, 'Session has ambiguous bindings.')
    return values[0] if values else None


def validate_binding(state: dict, binding_id: str, revision: str) -> dict:
    binding = state.get('host_bindings', {}).get(binding_id)
    require(binding and binding['status'] == 'active' and binding['revision'] == revision,
            'Binding is stale, detached or transferred; refresh attachment.', 'STALE_BINDING')
    return binding


def _identity(req):
    require(req.get('host') in HOSTS and req.get('role') in ROLES, 'Supported host and role required.')
    for field in ('binding_id','session_id','actor_id','run_id','project_dir'):
        require(isinstance(req.get(field),str) and bool(req[field].strip()), f'{field} required.')
    release = req.get('release', {})
    from .releases import check_release
    require(check_release(release, release, 1)['status'] == 'allow', 'Known release identity required.', 'RELEASE_MISMATCH')


def apply_host_event(state: dict, kind: str, request: dict) -> dict:
    req = deepcopy(request)
    if kind == 'handoff-prepare': return prepare_handoff(state,req)
    if kind == 'handoff-accept':
        return accept_handoff(state,req,req['source_release'],req['destination_release'],req['destination_decision'])
    bindings = state.setdefault('host_bindings', {})
    if kind == 'attach':
        _identity(req)
        run = state.get('runs', {}).get(req['run_id'])
        require(run and run.get('status') not in {'delivered','discarded'}, 'Active registered run required.')
        require(any(repo.get('location') == req['project_dir'] for repo in run.get('repositories', {}).values()), 'Project does not match run repository.')
        existing = binding_for_session(state,req['host'],req['session_id'])
        history = run.setdefault('implementer_actors', [])
        original = run.get('actors', {}).get('implementer')
        if original and original not in history: history.append(original)
        require(existing is None or req.get('refresh') is True and existing['binding_id'] == req['binding_id'], 'Session already attached; detach or explicitly refresh.')
        prior = bindings.get(req['binding_id'])
        if req.get('refresh'):
            current = validate_binding(state,req['binding_id'],req.get('revision'))
            require(all(current.get(k) == req.get(k) for k in ('host','session_id','actor_id','role','run_id','project_dir')), 'Refresh cannot change identity or ownership.')
        else: require(prior is None, 'Binding ID is immutable; choose a new binding ID.')
        if req['role'] == 'implementer':
            owners = [b for b in bindings.values() if b['run_id'] == run['id'] and b['role'] == 'implementer' and b['status'] == 'active']
            require(not owners or req.get('refresh') and owners[0]['binding_id'] == req['binding_id'], 'Run already has an implementation owner.')
            baseline = run.get('host_owner_release')
            if baseline and not req.get('refresh'):
                from .releases import check_release
                require(check_release(baseline,req['release'],1)['status'] == 'allow', 'Resume must match last owner release.', 'RELEASE_MISMATCH')
            if req['actor_id'] not in history: history.append(req['actor_id'])
            run['host_owner_release'] = deepcopy(req['release'])
            run.setdefault('actors', {})['implementer'] = req['actor_id']
        else:
            role = req['role'].removesuffix('-reviewer')
            package = run.get('review_packages', {}).get(req.get('package_hash'), {})
            require(package and package.get('role') == role, 'Matching review package required.')
            require(req['actor_id'] not in history, 'Every implementing actor is excluded from independent review.')
            if role == 'item': require(req.get('item_id') in run.get('items', {}), 'Planned item required.')
        record = {**req, 'revision':prior['revision']+1 if prior else 1,'status':'active'}
        record.pop('refresh',None)
        record['release_history'] = deepcopy(prior.get('release_history', [prior['release']]))+[req['release']] if prior else [req['release']]
        bindings[req['binding_id']] = record
        return deepcopy(record)
    binding = validate_binding(state,req.get('binding_id'),req.get('revision'))
    run = state['runs'][binding['run_id']]
    if kind == 'detach':
        binding['status'] = 'detached'; binding['revision'] += 1
        return deepcopy(binding)
    if kind == 'task-bind':
        require(isinstance(req.get('task_id'),str) and bool(req['task_id'].strip()), 'Host task ID required.')
        if binding['role'] == 'implementer':
            require(req.get('scope') in {'item','delivery'}, 'Implementation maps item or delivery task.')
            if req['scope'] == 'item':
                item = run.get('items', {}).get(req.get('item_id'), {})
                attempts = item.get('attempts', [])
                require(attempts and req.get('token') == attempts[-1].get('token'), 'Task requires current item attempt token.')
        else:
            require(req.get('scope') == 'review' and req.get('package_hash') == binding.get('package_hash'), 'Review task must bind attached package.')
            if binding['role'] == 'item-reviewer': require(req.get('item_id') == binding.get('item_id'), 'Review task item differs from attachment.')
        key = binding['host'] + ':' + binding['session_id'] + ':' + req['task_id']
        tasks = state.setdefault('host_tasks', {})
        record = {**req,'run_id':binding['run_id'],'role':binding['role'],'actor_id':binding['actor_id'], 'host':binding['host'],'session_id':binding['session_id']}
        require(key not in tasks or tasks[key] == record, 'Task ID already mapped to another scope.')
        tasks[key] = record
        return deepcopy(record)
    raise WorkflowError('INVALID_EVENT', f'Unknown host transition: {kind}')


def prepare_handoff(state: dict, request: dict) -> dict:
    req = deepcopy(request)
    source = validate_binding(state,req.get('binding_id'),req.get('revision'))
    require(source['role'] == 'implementer', 'Only implementer ownership can be transferred.')
    require(req.get('target_host') in HOSTS and isinstance(req.get('handoff_id'),str) and req['handoff_id'], 'Handoff ID and target host required.')
    require(all(isinstance(req.get(k),str) and req[k] for k in ('target_actor_id',)), 'Target actor required.')
    envelope = {**req,'source_release':deepcopy(source['release']),'run_id':source['run_id']}
    envelopes = state.setdefault('host_handoffs', {})
    require(req['handoff_id'] not in envelopes, 'Handoff ID already prepared.')
    envelopes[req['handoff_id']] = envelope
    return deepcopy(envelope)


def accept_handoff(state: dict, envelope: dict, source_release: dict, destination_release: dict, destination_decision: dict) -> dict:
    from .releases import check_release
    prepared = state.get('host_handoffs', {}).get(envelope.get('handoff_id'))
    require(prepared and not prepared.get('accepted'), 'Prepared unaccepted handoff required.')
    source = validate_binding(state,prepared['binding_id'],prepared['revision'])
    for left,right in ((prepared['source_release'],source['release']), (source['release'],source_release), (source_release,destination_release)):
        decision = check_release(left,right,1)
        if decision['status'] != 'allow':
            raise WorkflowError('RELEASE_MISMATCH',decision['message'],{'parity':decision,'unchanged_owner':source['binding_id']})
    require(destination_decision.get('status') == 'allow', 'Destination model profile is ineligible; source owner unchanged.', 'MODEL_POLICY_BLOCKED')
    target = deepcopy(envelope.get('destination', {}))
    _identity(target)
    require(target['host'] == prepared['target_host'] and target['actor_id'] == prepared['target_actor_id']
            and (not prepared.get('target_session_id') or target['session_id'] == prepared['target_session_id']), 'Destination identity differs from prepared target.')
    require(target['run_id'] == source['run_id'] and target['project_dir'] == source['project_dir'] and target['role'] == 'implementer', 'Destination run/project/role mismatch.')
    require(check_release(target['release'],destination_release,1)['status'] == 'allow', 'Destination release differs from preflight.')
    require(target['binding_id'] not in state['host_bindings'] and binding_for_session(state,target['host'],target['session_id']) is None, 'Destination already attached.')
    source['status'] = 'transferred'; source['revision'] += 1
    target['release'] = deepcopy(destination_release)
    result = apply_host_event(state,'attach',target)
    prepared['accepted'] = result['binding_id']
    prepared['destination_decision'] = deepcopy(destination_decision)
    return result
