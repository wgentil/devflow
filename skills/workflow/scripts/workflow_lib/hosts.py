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
    if kind == 'goal-bind':
        from .goals import goal_contract
        from .journal_domains import digest
        binding = validate_binding(state, req.get('binding_id'), req.get('revision'))
        require(binding['role'] == 'implementer' and binding['host'] == req.get('host')
                and binding['run_id'] == req.get('run_id'), 'Goal belongs to current implementing host and run.')
        authorization = req.get('authorization') or {}
        require(authorization.get('approved') is True and isinstance(authorization.get('actor_id'), str)
                and authorization['actor_id'].strip(), 'Explicit human Goal authorization required.', 'GOAL_AUTHORIZATION_REQUIRED')
        require(isinstance(req.get('goal_ref'), str) and req['goal_ref'].strip()
                and isinstance(req.get('capability_version'), str) and req['capability_version'].strip(),
                'Opaque host Goal reference and capability version required.')
        run = state['runs'][binding['run_id']]
        contract_hash = digest(goal_contract(run))
        require(req.get('contract_hash') == contract_hash, 'Goal contract changed; review again.', 'GOAL_CONTRACT_STALE')
        goals = run.setdefault('goal_bindings', {})
        require(binding['binding_id'] not in goals, 'This host binding already has a Goal.')
        record = {'binding_id': binding['binding_id'], 'host': binding['host'],
                  'run_id': binding['run_id'], 'goal_ref': req['goal_ref'],
                  'capability_version': req['capability_version'],
                  'release': deepcopy(binding['release']), 'contract_hash': contract_hash,
                  'authorization': deepcopy(authorization)}
        goals[binding['binding_id']] = record
        return deepcopy(record)
    if kind in {'native-start','native-finish'}:return apply_native_event(state,kind,req)
    if kind == 'legacy-adopt':
        require(req.get('adopt_legacy') is True and not any(b['run_id']==req.get('run_id') for b in state.get('host_bindings',{}).values()), 'Legacy adoption is explicit and only for pre-binding runs.')
        run=state.get('runs',{}).get(req.get('run_id'),{})
        require(not run.get('host_owner_release'), 'Known owner release cannot be bypassed by adoption.')
        req['legacy_adoption_actor']=req.get('actor_id')
        return apply_host_event(state,'attach',req)
    if kind in {'model-override' ,'model-receipt','model-interrupt'}:
        binding = validate_binding(state,req.get('binding_id'),req.get('revision'))
        run = state['runs'][binding['run_id']]
        if kind == 'model-override':require(binding['role'] == 'implementer', 'Model policy changes belong to current implementer.')
        if kind == 'model-override':
            require(req.get('mode','advisory') in {'strict','advisory'}, 'Supported routing mode required.')
            require(req.get('target_host') in {None,*HOSTS}, 'Model preference target host must be supported.')
            from .model_policy import PREFERENCE_KEYS
            require(isinstance(req.get('clear',[]),list) and all(k in PREFERENCE_KEYS for k in req.get('clear',[])), 'Clear must explicitly name model preference fields.')
            import math
            for key in ('profile','pin','effort','price_version','stage'):
                require(key not in req or isinstance(req[key],str) and bool(req[key].strip()), 'Preference strings must be nonempty; use clear for removal.')
            require('allow_unvalidated' not in req or type(req['allow_unvalidated']) is bool, 'Unvalidated permission must be boolean.')
            require('allowed_models' not in req or isinstance(req['allowed_models'],list) and all(isinstance(m,str) and m for m in req['allowed_models']), 'Model allowlist must be a list; use clear for removal.')
            require('max_cost' not in req or type(req['max_cost']) in (int,float) and math.isfinite(req['max_cost']) and req['max_cost']>=0, 'Cost cap must be finite and nonnegative; use clear for removal.')
            require('estimated_tokens' not in req or isinstance(req['estimated_tokens'],dict) and all(type(req['estimated_tokens'].get(k)) in (int,float) and math.isfinite(req['estimated_tokens'][k]) and req['estimated_tokens'][k]>=0 for k in ('input','output')), 'Token estimate needs finite nonnegative input/output values.')
            record = {**req, 'policy_revision':len(run.get('model_overrides', []))+1}
            run.setdefault('model_overrides', []).append(record)
        elif kind == 'model-receipt':
            record = deepcopy(req['receipt'])
            require(isinstance(record,dict) and isinstance(record.get('invocation_id'),str) and record['invocation_id'], 'Invocation ID required.')
            require(record.get('observed') is None and record.get('observation_source') is None, 'Portable CLI cannot assert trusted host observations.')
            require(req.get('resolution_policy_revision',len(run.get('model_overrides',[])))==len(run.get('model_overrides',[])), 'Model policy changed before receipt commit; resolve again.', 'STALE_STATE')
            record['scope'] = invocation_scope(binding,run,record.get('stage','implementation'),record)
            record['policy_revision'] = len(run.get('model_overrides', []))
            records = run.setdefault('model_receipts', {})
            require(record['invocation_id'] not in records, 'Invocation receipt is immutable.')
            records[record['invocation_id']] = deepcopy(record)
        else:
            from .model_policy import interruption
            invocation_id=req['invocation'].get('invocation_id')
            original=run.get('model_receipts',{}).get(invocation_id,{})
            require(original and all(original.get('scope',{}).get(k)==binding.get(k) for k in ('binding_id','revision','actor_id','role','run_id')), 'Interruption must belong to this binding invocation.', 'INVOCATION_SCOPE_MISMATCH')
            record = interruption(original,req['error_kind'],req.get('retry_count',0))
            records = run.setdefault('model_interruptions', [])
            require(record.get('invocation_id') in run.get('model_receipts', {}), 'Recorded invocation required before interruption.')
            records.append(record)
        return deepcopy(record)
    if kind == 'handoff-prepare': return prepare_handoff(state,req)
    if kind == 'handoff-accept':
        return accept_handoff(state,req,req['source_release'],req['destination_release'],req['destination_decision'])
    bindings = state.setdefault('host_bindings', {})
    if kind == 'attach':
        _identity(req)
        run = state.get('runs', {}).get(req['run_id'])
        require(run and run.get('status') not in {'delivered','discarded'}, 'Active registered run required.')
        require(run.get('host_protocol_version') == 1 or req.get('adopt_legacy') is True or any(b['run_id']==run['id'] for b in bindings.values()), 'Pre-binding legacy run requires explicit legacy adoption.', 'LEGACY_ADOPTION_REQUIRED')
        require(any(repo.get('location') == req['project_dir'] for repo in run.get('repositories', {}).values()), 'Project does not match run repository.')
        existing = binding_for_session(state,req['host'],req['session_id'])
        history = run.setdefault('implementer_actors', [])
        original = run.get('actors', {}).get('implementer')
        if original and original not in history: history.append(original)
        require(existing is None or req.get('refresh') is True and existing['binding_id'] == req['binding_id'], 'Session already attached; detach or explicitly refresh.')
        prior = bindings.get(req['binding_id'])
        if prior and (req.get('resume') or req.get('refresh')):require_no_native_work(run,prior['binding_id'])
        if req.get('resume'):
            require(not req.get('refresh') and prior and prior['status']=='detached' and prior['revision']==req.get('revision'), 'Resume needs exact detached binding revision.', 'STALE_BINDING')
            require(all(prior.get(k)==req.get(k) for k in ('host','session_id','actor_id','role','run_id','project_dir','package_hash','item_id')), 'Resume cannot change attachment identity or work scope.')
            old=prior['release'];new=req['release']
            require(old.get('plugin')==new.get('plugin') and old.get('host_protocol_version')==new.get('host_protocol_version') and 1 in old.get('supported_schemas',[]) and 1 in new.get('supported_schemas',[]), 'Resume upgrade requires compatible protocol and state schema.', 'RELEASE_MISMATCH')
        elif req.get('refresh'):
            current = validate_binding(state,req['binding_id'],req.get('revision'))
            require(all(current.get(k) == req.get(k) for k in ('host','session_id','actor_id','role','run_id','project_dir')), 'Refresh cannot change identity or ownership.')
        else: require(prior is None, 'Binding ID is immutable; choose a new binding ID.')
        if req['role'] == 'implementer':
            owners = [b for b in bindings.values() if b['run_id'] == run['id'] and b['role'] == 'implementer' and b['status'] == 'active']
            require(not owners or req.get('refresh') and owners[0]['binding_id'] == req['binding_id'], 'Run already has an implementation owner.')
            baseline = run.get('host_owner_release')
            if baseline and not (req.get('refresh') or req.get('resume')):
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
        record.pop('refresh',None);record.pop('resume',None)
        record['release_history'] = deepcopy(prior.get('release_history', [prior['release']]))+[req['release']] if prior else [req['release']]
        bindings[req['binding_id']] = record
        return deepcopy(record)
    binding = validate_binding(state,req.get('binding_id'),req.get('revision'))
    run = state['runs'][binding['run_id']]
    if kind == 'detach':
        require_no_native_work(run,binding['binding_id'])
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
        if req.get('invocation_id'):
            receipt=run.get('model_receipts',{}).get(req['invocation_id']) or run.get('native_invocations',{}).get(req['invocation_id'],{})
            require(receipt_matches_task(receipt,binding,req), 'Invocation receipt does not match task binding, stage, role and work scope.', 'INVOCATION_SCOPE_MISMATCH')
        key = binding['host'] + ':' + binding['session_id'] + ':' + req['task_id']
        tasks = state.setdefault('host_tasks', {})
        record = {**req,'run_id':binding['run_id'],'role':binding['role'],'actor_id':binding['actor_id'], 'host':binding['host'],'session_id':binding['session_id']}
        prior=tasks.get(key)
        if prior and prior != record:
            from .journal_domains import digest
            require(req.get('replace') is True and req.get('previous_mapping_hash') == digest(prior), 'Explicit remap must name the exact previous mapping hash.')
            require(all(prior.get(k) == record.get(k) for k in ('run_id','role','scope','item_id','binding_id')), 'Remap cannot change task ownership or work scope.')
        record.pop('replace',None);record.pop('previous_mapping_hash',None)
        tasks[key] = record
        return deepcopy(record)
    raise WorkflowError('INVALID_EVENT', f'Unknown host transition: {kind}')


def prepare_handoff(state: dict, request: dict) -> dict:
    req = deepcopy(request)
    source = validate_binding(state,req.get('binding_id'),req.get('revision'))
    require(source['role'] == 'implementer', 'Only implementer ownership can be transferred.')
    require_no_native_work(state['runs'][source['run_id']],source['binding_id'])
    require(req.get('target_host') in HOSTS and isinstance(req.get('handoff_id'),str) and req['handoff_id'], 'Handoff ID and target host required.')
    require(all(isinstance(req.get(k),str) and req[k] for k in ('target_actor_id',)), 'Target actor required.')
    envelope = {**req,'source_release':deepcopy(source['release']),'run_id':source['run_id']}
    run = state['runs'][source['run_id']]
    if run.get('goal_bindings', {}).get(source['binding_id']):
        from .goals import goal_handoff_decision
        envelope['goal_handoff'] = goal_handoff_decision(state, source, req['target_host'])
    envelopes = state.setdefault('host_handoffs', {})
    require(req['handoff_id'] not in envelopes, 'Handoff ID already prepared.')
    envelopes[req['handoff_id']] = envelope
    return deepcopy(envelope)


def accept_handoff(state: dict, envelope: dict, source_release: dict, destination_release: dict, destination_decision: dict) -> dict:
    from .releases import check_release
    prepared = state.get('host_handoffs', {}).get(envelope.get('handoff_id'))
    require(prepared and not prepared.get('accepted'), 'Prepared unaccepted handoff required.')
    source = validate_binding(state,prepared['binding_id'],prepared['revision'])
    require_no_native_work(state['runs'][source['run_id']],source['binding_id'])
    for left,right in ((prepared['source_release'],source['release']), (source['release'],source_release), (source_release,destination_release)):
        decision = check_release(left,right,1)
        if decision['status'] != 'allow':
            raise WorkflowError('RELEASE_MISMATCH',decision['message'],{'parity':decision,'unchanged_owner':source['binding_id']})
    require(destination_decision.get('policy_revision',len(state['runs'][source['run_id']].get('model_overrides',[]))) == len(state['runs'][source['run_id']].get('model_overrides',[])), 'Destination policy changed during preflight; source owner unchanged.', 'STALE_STATE')
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
    if prepared.get('goal_handoff'):
        result['goal_handoff'] = deepcopy(prepared['goal_handoff'])
    prepared['accepted'] = result['binding_id']
    prepared['destination_decision'] = deepcopy(destination_decision)
    return result


def task_stage(binding, task):
    return 'implementation' if task['scope']=='item' else 'acceptance' if binding['role']=='acceptance-reviewer' else 'review' if task['scope']=='review' else 'delivery'

def invocation_scope(binding, run, stage, receipt):
    scope={key:binding[key] for key in ('binding_id','revision','host','session_id','actor_id','role','run_id')}
    scope['stage']=stage
    if stage == 'implementation':
        require(binding['role']=='implementer', 'Implementation invocation needs implementing actor.')
        active=run.get('active_attempt')
        repair=next((row for row in run.get('repair_cycles', []) if row.get('status')=='claimed'),None)
        require(active and active.get('item_id') and active.get('token') or repair,
                'Implementation invocation needs active item attempt or claimed repair cycle.')
        if active: scope.update(item_id=active['item_id'],token=active['token'])
        else: scope['repair_cycle_id']=repair['cycle_id']
    elif stage in {'review','acceptance'}:
        require(binding['role'] != 'implementer' and (stage=='acceptance') == (binding['role']=='acceptance-reviewer'), 'Review invocation stage must match reviewer role.')
        scope.update(package_hash=binding.get('package_hash'),item_id=binding.get('item_id'))
    else:require(binding['role']=='implementer', 'This invocation stage belongs to implementing actor.')
    return scope

def receipt_matches_task(receipt, binding, task):
    scope=receipt.get('scope',{})
    if any(scope.get(key)!=binding.get(key) for key in ('binding_id','revision','host','session_id','actor_id','role','run_id')):return False
    if scope.get('stage') != task_stage(binding,task):return False
    fields=('item_id','token') if task['scope']=='item' else ('package_hash','item_id') if task['scope']=='review' else ()
    return all(scope.get(key)==task.get(key) for key in fields) and isinstance(receipt.get('policy_revision'),int)


def require_no_native_work(run, binding_id):
    require(not any(row.get('status') == 'claimed' for row in run.get('repair_cycles', [])),
            'Repair cycle is active; record or reconcile it before changing host ownership.',
            'REPAIR_LEASE_ACTIVE')
    require(not any(record.get('status')=='running' and record.get('scope',{}).get('binding_id')==binding_id for record in run.get('native_invocations',{}).values()), 'Native worker is active; wait for its result or reconcile a stopped invocation.', 'NATIVE_INVOCATION_ACTIVE')

def apply_native_event(state,kind,req):
    binding=validate_binding(state,req.get('binding_id'),req.get('revision'))
    run=state['runs'][binding['run_id']]
    records=run.setdefault('native_invocations',{})
    identifier=req.get('invocation_id')
    require(isinstance(identifier,str) and identifier, 'Native invocation ID required.')
    if kind=='native-start':
        require(identifier not in records and identifier not in run.get('model_receipts',{}), 'Invocation ID is immutable.')
        require_no_native_work(run,binding['binding_id'])
        require(req.get('policy_revision')==len(run.get('model_overrides',[])), 'Model policy changed before native dispatch.', 'STALE_STATE')
        decision=req.get('decision',{})
        require(decision.get('status') in {'allow','pending-access'} and decision.get('resolved'), 'Eligible selected native model required.')
        require(decision.get('status')!='pending-access' or decision.get('mode')=='advisory', 'Pending access cannot satisfy strict dispatch.')
        scope=invocation_scope(binding,run,req['stage'],{})
        require(req.get('expected_scope',scope)==scope, 'Attempt or review scope changed during discovery.', 'STALE_STATE')
        prior=next((r for r in reversed(list(records.values())) if r.get('scope')==scope),None)
        retry_count=0
        if prior and prior.get('status')=='interrupted':
            require(req.get('replacement_of')==prior['invocation_id'], 'Replacement must name the interrupted invocation.')
            retry_count=prior.get('retry_count',0)+1
            auth=req.get('replacement_authorization') or {}
            require(isinstance(auth,dict), 'Replacement authorization must be an object.')
            explicit=auth.get('approved') is True and isinstance(auth.get('actor_id'),str) and bool(auth['actor_id'])
            require(explicit or prior.get('retry_allowed') is True and retry_count<=2, 'Replacement needs an explicit user decision; automatic retry allowance exhausted.', 'MODEL_REPLACEMENT_REQUIRED')
        record={**req,'scope':scope,'status':'running','retry_count':retry_count}
        records[identifier]=record
        return deepcopy(record)
    record=records.get(identifier,{})
    require(record.get('status')=='running' and all(record.get('scope',{}).get(k)==binding.get(k) for k in ('binding_id','revision','actor_id','role','run_id')), 'Native finish requires this binding running invocation.')
    result=deepcopy(req.get('result',{}));require(result.get('status') in {'completed','interrupted'}, 'Native result status required.')
    receipt={**deepcopy(record['decision']),'invocation_id':identifier,'stage':record['stage'],'scope':deepcopy(record['scope']),'policy_revision':record['policy_revision'],'account_key':record.get('account_key'),
             'observed':result.get('observed'),'observation_source':result.get('observation_source'),
             'invocation_ref':result.get('invocation_ref'),'output_ref':result.get('output_ref'),'usage':result.get('usage')}
    if result['status']=='completed':
        from .model_policy import check_model_receipt
        receipt['status']='allow'
        receipt['dispatch']=True
        observed=receipt.get('observed') or {}
        resolved=receipt.get('resolved') or {}
        strict=check_model_receipt(receipt,receipt.get('mode','advisory'))
        if not observed.get('model') or observed['model']!=resolved.get('model') or observed.get('provider') and observed['provider']!=resolved.get('provider'):
            result.update(status='interrupted',error_kind='unavailable',reason_code='MODEL_SUBSTITUTED')
        elif strict['status']=='block':result.update(status='interrupted',error_kind='unavailable',reason_code=strict['reason_code'])
    if result['status']=='interrupted':
        from .model_policy import interruption
        receipt.update(status='block',reason_code=result.get('reason_code','INVOCATION_INTERRUPTED'))
        stopped=interruption(receipt,result.get('error_kind','unavailable'),record.get('retry_count',0))
        run.setdefault('model_interruptions',[]).append(stopped)
        record.update(retry_allowed=stopped['retry_allowed'],error_kind=stopped['error_kind'])
    else:receipt['reason_code']=receipt.get('eligible_reason_code',receipt.get('reason_code','NATIVE_INVOCATION_COMPLETED'))
    run.setdefault('model_receipts',{})[identifier]=receipt
    record.update(status=result['status'],result=result)
    return deepcopy(receipt)
