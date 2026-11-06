"""Prepare delegation; execute only through an explicitly supplied host adapter.

The CLI has no bridge. JSON input cannot create one or supply trusted host facts.
"""
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import os
import time
from pathlib import Path

from .document_units import digest
from .host_route_controls import assess_route_controls
from .host_models import delegated_configuration
from .hosts import validate_binding, invocation_scope
from .host_completion import host_brief
from .model_policy import resolve_profile
from .native_runtime import policy, preferences, prices, invocation_context, _native_lease, _commit
from .routing_receipts import routing_lineage_id, worker_task_prompt, project_worker_result
from .releases import check_release, release_descriptor
from .store import WorkflowError, HOST_CONTEXT
from .action_policy import enforcement_version
from .host_projection import read_host
from .storage_pins import reservation
from .task_routing import normalize_task_facts
from .evidence import _blob


@reservation('interactive-dispatch')
def prepare_delegation(root: Path, request: dict, host_context: dict | None = None,*,preparation_consumer=None) -> dict:
    root = Path(root).resolve()
    data = read_host(root,request=request)['data']
    binding = validate_binding(data, request.get('binding_id'), request.get('revision'))
    parity = check_release(binding['release'], release_descriptor(), 1)
    if parity['status'] != 'allow': raise WorkflowError('RELEASE_MISMATCH', parity['message'])
    stage = request.get('stage')
    if stage not in policy()['stages']: raise WorkflowError('PROFILE_UNAVAILABLE', 'Known stage required.')
    identifier, prompt = request.get('invocation_id'), request.get('prompt')
    if not isinstance(identifier, str) or not identifier or not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > 65536:
        raise WorkflowError('NATIVE_INPUT_REQUIRED', 'Invocation identity and bounded prompt required.')
    access = request.get('access', 'read-only')
    if access not in {'read-only', 'workspace-write'} or access == 'workspace-write' and (binding['role'] != 'implementer' or stage != 'implementation'):
        raise WorkflowError('NATIVE_ACCESS_DENIED', 'Write access is restricted to authorized implementation work.')
    run = data['runs'][binding['run_id']]
    scope = invocation_scope(binding, run, stage, {})
    facts = normalize_task_facts(request.get('task'), scope)
    path = request.get('execution_path', 'interactive-nonfork')
    if path not in {'interactive-nonfork', 'interactive-fork'}:
        raise WorkflowError('INTERACTIVE_PATH_INVALID', 'Interactive execution path required.')
    full_view = host_brief(data, binding, control_root=root, max_bytes=request.get('context_max_bytes', 20000), stage_override=stage,preparation_consumer=preparation_consumer)
    if scope.get('perspective'):
        from .adversarial_reviews import specialist_prompt
        prompt=specialist_prompt(prompt,interactive=True)
    worker_input = invocation_context(binding, stage, full_view, worker_task_prompt(prompt, facts, scope), request.get('context_max_bytes', 20000))
    context = deepcopy(host_context or {})
    pref = preferences(data, binding, stage)
    from .review_policy import review_version
    specialist=review_version(run)==1 and stage=='review'
    if specialist:
        from .review_dispatch import specialist_scope,resolve_workflow_review
        if request.get('perspective')!=specialist_scope(run,binding)['perspective']:
            raise WorkflowError('REVIEW_MODEL_BLOCKED','Exact attached specialist perspective required.')
        decision=resolve_workflow_review(data,binding,context,policy(),diagnostic=request.get('diagnostic') is True)
    else:
        decision = resolve_profile(policy(), {**pref, 'task': facts}, context.get('capabilities', {}),
                                   context.get('discovery', {}), prices(data, pref))
    retry = None
    if not specialist and request.get('replacement_of') and not request.get('predecessor_invocation_id'):
        from .routing_escalation import resolve_routing_retry
        retry = resolve_routing_retry(policy(),run,facts,request['replacement_of'],pref,context,prices(data,pref))
        if retry is not None: decision = retry['decision']
    resolved = decision.get('resolved') or {}
    evidence = deepcopy(context.get('controls') or {})
    evidence['spawn'] = {key: resolved.get(key) for key in ('model', 'effort')}
    controls = assess_route_controls(binding['host'], path, resolved, evidence)
    snapshot_consistent = (bool(context.get('account_key')) and context['account_key'] == evidence.get('account_key')
        and bool(context.get('discovery', {}).get('host_version'))
        and context['discovery']['host_version'] == evidence.get('host_version')
        and context.get('capabilities', {}).get('model_efforts') == evidence.get('model_efforts'))
    escalation = None
    if not specialist and request.get('predecessor_invocation_id') and evidence.get('configuration_hash'):
        from .routing_escalation import plan_escalation
        lineage_id = routing_lineage_id(facts)
        predecessor = run.get('native_invocations', {}).get(request['predecessor_invocation_id'], {})
        lineage = {**run.get('routing_lineages', {}).get(lineage_id, {}), 'lineage_id':lineage_id,
            'task_hash':digest(facts),'policy_hash':digest(policy()),'configuration_hash':evidence['configuration_hash'],
            'host':binding['host'],'stage':stage,'current':predecessor.get('decision',{}).get('resolved'),
            'predecessor_invocation_id':request['predecessor_invocation_id'],'preferences':pref,
            'capabilities':context.get('capabilities',{}),'discovery':context.get('discovery',{}),'prices':prices(data,pref)}
        escalation = plan_escalation(policy(),lineage,request.get('escalation_evidence',{}),request.get('escalation_authorization',{}))
        if escalation['status'] == 'eligible':
            decision=escalation['candidate'];resolved=decision['resolved']
            evidence['spawn']={key:resolved.get(key) for key in ('model','effort')}
            controls=assess_route_controls(binding['host'],path,resolved,evidence)
        else:
            decision={**decision,'status':'block','dispatch':False,'reason_code':escalation['reason_code']}
    routing = {**decision.get('routing', {}), 'routing_schema_version': 1,
        'task_facts': facts, 'task_hash': digest(facts), 'policy_hash': digest(policy()),
        'lineage_id': routing_lineage_id(facts), 'scope_hash': digest(scope), 'execution_path': path,
        'controls': controls, 'configuration_hash': evidence.get('configuration_hash'),
        'classification_origin': facts['origin'], 'reasons': decision.get('routing', {}).get('reasons', [])}
    if escalation and escalation['status']=='eligible':
        routing.update(escalation_index=escalation['escalation_index'],
            predecessor_invocation_id=request['predecessor_invocation_id'],
            escalation_authorization=request['escalation_authorization'],escalation_evidence=request['escalation_evidence'])
    if retry is not None:
        routing.update(escalation_index=retry['escalation_index'],retry_of=request['replacement_of'])
    decision = {**decision, 'routing': routing}
    ready = snapshot_consistent and decision.get('status') == 'allow' and bool(resolved) and controls['status'] == 'compatible'
    launch = delegated_configuration(decision, binding['host'], binding['actor_id']) if ready else None
    if launch:
        launch.update(access=access, allow_delegation=False)
    known_payload = measure_delegation_payload({'configuration_text':worker_input['configuration_text'],'launch':launch},
        worker_input['prompt'], request.get('preloaded_units', []))
    if request.get('preloaded_units'):
        raise WorkflowError('CONTEXT_PRELOAD_REJECTED', 'The full task view already owns required skills; additional preloads are unavailable.')
    if known_payload['known_payload_bytes'] > request.get('context_max_bytes',20000):
        raise WorkflowError('CONTEXT_BUDGET_EXCEEDED', 'Known delegation payload exceeds its budget; rescope the task.',
            {'known_payload':known_payload,'artifact_id':full_view.get('task_view',{}).get('artifact_id')})
    decision['routing']['known_payload'] = known_payload
    return {'status': 'not-dispatched', 'dispatch': False, 'known_payload':known_payload, 'reason_code': 'READY' if ready else 'INTERACTIVE_CONTROLS_UNAVAILABLE',
            'binding_id': binding['binding_id'], 'revision': binding['revision'], 'invocation_id': identifier,
            'snapshot_hash': digest(context), 'scope': scope, 'policy_revision': len(run.get('model_overrides', [])), 'decision': decision,
            'worker_input': worker_input, 'launch': launch, 'access': access,
            'context_coverage': deepcopy(full_view.get('task_view', {}).get('coverage', {})),
            'context_artifact_id': full_view.get('task_view', {}).get('artifact_id'),
            'limitations': ['Preparation is not execution or trusted observation. Hidden host context is outside measured coverage.']}


@reservation('interactive-dispatch')
def dispatch_delegation(root: Path, request: dict, operation_id: str, bridge=None) -> dict:
    root = Path(root).resolve()
    if bridge is None: return prepare_delegation(root, request)
    data = read_host(root,request=request)['data']
    binding = validate_binding(data, request.get('binding_id'), request.get('revision'))
    identifier = request.get('invocation_id')
    request_hash = digest(request)
    lease = root / 'native-invocations' / hashlib.sha256((binding['run_id'] + ':' + str(identifier)).encode()).hexdigest()
    lease.parent.mkdir(parents=True, exist_ok=True)
    with _native_lease(lease),ExitStack() as preparation_pins:
        preparations=[]
        def retain(prepared):
            preparations.append(prepared);preparation_pins.callback(prepared.release)
        data = read_host(root,request=request)['data']
        prior = data['runs'][binding['run_id']].get('native_invocations', {}).get(identifier)
        cached=data['runs'][binding['run_id']].get('model_receipts',{}).get(identifier,{})
        if not prior and cached.get('dispatch') is False and cached.get('request_hash'):
            if cached['request_hash']!=request_hash or cached.get('operation_id')!=operation_id:raise WorkflowError('OPERATION_CONFLICT','Preflight identity belongs to another exact request.')
            return {**cached,'status':cached.get('preflight_status',cached['status']),'replayed':True}
        if prior:
            if prior.get('request_hash') != request_hash or prior.get('operation_id') != operation_id:
                raise WorkflowError('OPERATION_CONFLICT', 'Invocation belongs to another request.')
            if prior['status'] == 'running':
                raise WorkflowError('NATIVE_INVOCATION_ACTIVE', 'Interactive worker is running or needs stopped-worker reconciliation.')
            return {**data['runs'][binding['run_id']]['model_receipts'][identifier], 'replayed': True}
        enforcement_effect = None
        run = data['runs'][binding['run_id']]
        if enforcement_version(run) is not None:
            from .effect_dispatch import reserve_dispatch
            action_scope = {'item_id': run['active_attempt']['item_id']} if run.get('active_attempt') and request.get('stage') == 'implementation' else ({'item_id': binding['item_id']} if binding.get('item_id') else {})
            exclusive_scope = 'implementation' if request.get('stage') == 'implementation' else 'review:' + binding['role'] + ':' + str(binding.get('package_hash', ''))
            token = HOST_CONTEXT.set({'binding_id': binding['binding_id'], 'revision': binding['revision'], 'release': binding['release']})
            try:
                enforcement_effect = reserve_dispatch(root, binding['run_id'], identifier, exclusive_scope,
                    request.get('estimated_cost'), operation_id, action_scope, owner_binding=binding)
            finally: HOST_CONTEXT.reset(token)
        def abort_preflight(failure):
            if enforcement_effect is None:return failure
            current=read_host(root,request=request)['data']['runs'][binding['run_id']]
            if identifier in current.get('native_invocations',{}):return failure
            details={**failure.get('decision',{}),'reason_code':failure.get('reason_code','INTERACTIVE_PREFLIGHT_FAILED'),
                'preflight_status':'not-dispatched',**{k:failure[k] for k in ('message','known_payload') if k in failure}}
            receipt=_commit(root,operation_id+':native-abort','native-abort',{
                'binding_id':binding['binding_id'],'revision':binding['revision'],'invocation_id':identifier,
                'stage':request['stage'],'now_ms':int(time.time()*1000),'request_hash':request_hash,
                'operation_id':operation_id,'failure':details},binding)
            return {**receipt,'status':'not-dispatched'}
        try:
            # Only an in-process embedding adapter can supply these facts. The
            # portable CLI never imports bridge names or trusts serialized context.
            prepared = prepare_delegation(root, request, bridge.capabilities(),preparation_consumer=retain)
            if prepared['reason_code'] != 'READY': return abort_preflight(prepared)
            fresh = prepare_delegation(root, request, bridge.capabilities(),preparation_consumer=retain)
            if (fresh['reason_code'] != 'READY' or fresh['decision']['routing']['controls']['evidence_hash'] != prepared['decision']['routing']['controls']['evidence_hash']
                    or fresh['snapshot_hash'] != prepared['snapshot_hash'] or fresh['scope'] != prepared['scope'] or fresh['decision']['routing']['task_hash'] != prepared['decision']['routing']['task_hash']
                    or fresh['policy_revision'] != prepared['policy_revision']):
                return abort_preflight({**fresh, 'reason_code': 'ROUTING_CONFIGURATION_CHANGED'})
            start = {'binding_id': binding['binding_id'], 'revision': binding['revision'], 'invocation_id': identifier,
                'stage': request['stage'], 'decision': fresh['decision'], 'request_hash': request_hash,
                'operation_id': operation_id, 'policy_revision': fresh['policy_revision'], 'expected_scope': fresh['scope'],
                'launcher_pid': os.getpid(), 'replacement_of': request.get('replacement_of'),
                'replacement_authorization': request.get('replacement_authorization')}
            if fresh['scope'].get('perspective'):start['diagnostic']=request.get('diagnostic') is True
            if fresh['decision']['routing'].get('escalation_index') and not fresh['decision']['routing'].get('retry_of'):
                predecessor=request['predecessor_invocation_id']
                if request.get('replacement_of',predecessor)!=predecessor:
                    return abort_preflight({**fresh,'reason_code':'ESCALATION_PREDECESSOR_MISMATCH'})
                auth=request['escalation_authorization']
                start.update(replacement_of=predecessor,replacement_authorization={'approved':auth['approved'],'actor_id':auth['actor_id']})
            if enforcement_effect is not None:
                start['enforcement_effect_id'] = identifier
                start['enforcement_transition_ms'] = int(time.time()*1000)
            _commit(root, operation_id + ':native-start', 'native-start', start, binding,prepared=preparations[-1] if preparations else None)
        except Exception as exc:
            abort_preflight({'reason_code':getattr(exc,'code','INTERACTIVE_PREFLIGHT_FAILED'),'message':str(exc)})
            raise
        spawned=False;review_package=None;input_before=None
        try:
            if enforcement_effect is not None:
                from .effect_claims import validate_active_dispatch
                from .enforcement_live import source_observation
                current = read_host(root, request=request)['data']['runs'][binding['run_id']]
                validate_active_dispatch(current, identifier, {**source_observation(current), 'now_ms': int(time.time()*1000)})
            from .review_policy import review_version
            if review_version(run)==1 and binding.get('package_hash'):
                from .stored_records import require_package
                from .adversarial_reviews import verify_review_input
                review_package=require_package(current.get('review_packages',{}).get(binding['package_hash']))
                input_before=verify_review_input(root,review_package)
            spawned=True
            handle = bridge.spawn(fresh)
            result = bridge.collect(handle)
            if not isinstance(result, dict): raise ValueError('Malformed interactive result')
        except Exception as exc:
            if spawned:
                # A failed spawn/collect does not prove that a remote worker stopped.
                return {'status': 'block', 'dispatch': True, 'reason_code': 'INTERACTIVE_RECONCILE_REQUIRED',
                        'invocation_id': identifier, 'message': 'Confirm the worker stopped before reconciling or launching a replacement.'}
            result={'status':'interrupted','dispatch':False,'error_kind':'unavailable',
                'reason_code':getattr(exc,'code','INTERACTIVE_PREFLIGHT_FAILED')}

        result['transport_completed'] = result.get('status') == 'completed' and bool(result.get('invocation_ref'))
        if review_package and spawned:
            try:result['review_input_validation']={'before':input_before,'after':verify_review_input(root,review_package)}
            except WorkflowError as exc:result.update(status='interrupted',reason_code=exc.code,error_kind='unavailable')
        if result.get('status') != 'interrupted':
            result = project_worker_result(result,fresh['scope'])
        from .context_metrics import record_context_measurement, explicit_runtime_usage
        record_context_measurement(root, {'operation_id':operation_id+':interactive-input', 'operation':'interactive.input',
            'run_id':binding['run_id'],'invocation_id':identifier,'stage':request['stage'],
            'configuration_bytes':fresh['known_payload']['configuration_bytes'],'turn_bytes':fresh['known_payload']['turn_bytes'],
            'runtime_usage':explicit_runtime_usage(result.get('usage')),'helper_calls':1,'context_mode':'full'})
        from .review_policy import review_version
        if review_version(run)==1 and request['stage']=='review' and result.get('status')=='completed':
            from .adversarial_reviews import seal_actual_report
            result['review_report_hash']=seal_actual_report(result.get('output',''))
        result['output_ref'] = _blob(root, result.pop('output', ''))
        if result.get('observation_source') not in {'host-effective-configuration', 'host-invocation-metadata'}:
            result.update(observed=None, observation_source=None)
        return _commit(root, operation_id + ':native-finish', 'native-finish',
            {'binding_id': binding['binding_id'], 'revision': binding['revision'], 'invocation_id': identifier, 'result': result,
             **({'enforcement_transition_ms': int(time.time()*1000)} if enforcement_effect is not None else {})}, binding)


def measure_delegation_payload(configuration: dict, prompt: str, preloaded_units: list[dict]) -> dict:
    """Exact known bytes; host-internal instructions and history remain unknown."""
    from .document_units import canonical
    configuration_bytes, turn_bytes = len(canonical(configuration)), len(prompt.encode('utf-8'))
    if not isinstance(preloaded_units, list): raise WorkflowError('CONTEXT_PRELOAD_INVALID', 'Preloads must be a list.')
    encoded = canonical(configuration).decode('utf-8') + prompt
    seen, duplicates = set(), 0
    for unit in preloaded_units:
        if not isinstance(unit, dict) or not isinstance(unit.get('content'), str):
            raise WorkflowError('CONTEXT_PRELOAD_INVALID', 'Known preload content and hash required.')
        content_hash = hashlib.sha256(unit['content'].encode('utf-8')).hexdigest()
        if content_hash != unit.get('content_hash'):
            raise WorkflowError('CONTEXT_PRELOAD_INVALID', 'Preload content hash mismatch.')
        if content_hash in seen or content_hash in encoded or unit['content'] and unit['content'] in encoded:
            duplicates += len(unit['content'].encode('utf-8'))
        seen.add(content_hash)
    preload_bytes = len(canonical(preloaded_units)) if preloaded_units else 0
    return {'configuration_bytes': configuration_bytes, 'turn_bytes': turn_bytes, 'preload_bytes': preload_bytes,
            'known_payload_bytes': configuration_bytes + turn_bytes + preload_bytes,
            'duplicate_content_bytes': duplicates,
            'coverage': 'Known configuration, turn and explicit preload bytes only; hidden host context/history unknown.'}
