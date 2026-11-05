"""Observed coordinator death plus explicit human worker-stop evidence; no killing/relaunch."""
from copy import deepcopy
import hashlib,time
from pathlib import Path
from .document_units import digest
from .store import WorkflowError
from .effect_claims import transition_effect


def need(ok,message):
    if not ok:raise WorkflowError('WORKER_RECONCILIATION_REQUIRED',message)


def observe(effect_id,owner_pid,worker_ref,confirmation,lease_key):
    from .process_liveness import process_alive
    need(type(owner_pid) is int and owner_pid>0 and process_alive(owner_pid) is False,
         'Recorded coordinator is alive or cannot be proved absent; do not replace it.')
    need(isinstance(confirmation,dict) and confirmation.get('approved') is True and confirmation.get('actor_id')
         and confirmation.get('worker_ref')==worker_ref and confirmation.get('reason')
         and confirmation.get('provenance',{}).get('kind')=='user-message' and confirmation['provenance'].get('ref'),
         'Actual human confirmation must identify this stopped worker and all children, with message provenance.')
    return {'effect_id':effect_id,'owner_pid':owner_pid,'owner_absent':True,'worker_ref':worker_ref,
        'basis':'os-owner-stopped','lease_key':lease_key,'now_ms':int(time.time()*1000),
        'evidence_refs':[confirmation['provenance']['ref'],'os-owner:'+str(owner_pid)],'confirmation':deepcopy(confirmation)}


def apply_native(state,request):
    from .hosts import validate_binding
    binding=validate_binding(state,request.get('binding_id'),request.get('revision'))
    run=state['runs'][binding['run_id']];identifier=request['invocation_id'];effect=run.get('effects',{}).get(identifier,{})
    native=run.get('native_invocations',{}).get(identifier,{})
    need(effect and effect.get('status') in {'launching','running','uncertain'},'Known active/uncertain reservation required.')
    need(binding['role']=='implementer' or effect.get('owner_binding',{}).get('actor_id')==binding['actor_id'], 'Recovery belongs to the current implementing owner or this reviewer.')
    observation=request.get('observation',{});pid=native.get('launcher_pid',effect.get('owner_pid'))
    key=hashlib.sha256((binding['run_id']+':'+identifier).encode()).hexdigest()
    confirmation=observation.get('confirmation',{})
    worker=effect.get('worker_ref') or identifier
    need(observation.get('effect_id')==identifier and observation.get('worker_ref')==worker
         and observation.get('owner_pid')==pid and observation.get('owner_absent') is True
         and observation.get('lease_key')==key and observation.get('basis')=='os-owner-stopped'
         and observation.get('evidence_refs') and confirmation.get('approved') is True
         and confirmation.get('worker_ref')==worker and confirmation.get('actor_id') and confirmation.get('reason')
         and confirmation.get('provenance',{}).get('kind')=='user-message' and confirmation['provenance'].get('ref'),
         'Bound recorded coordinator/lease observation and actual worker-stop attestation required.')
    now=observation['now_ms'];updated=deepcopy(run)
    if effect['status']!='uncertain':updated=transition_effect(updated,{'effect_id':identifier,'status':'uncertain','worker_ref':worker,'now_ms':now})
    elif not updated['effects'][identifier].get('worker_ref'):updated['effects'][identifier]['worker_ref']=worker
    observation_id=request['observation_id'];updated.setdefault('worker_termination_observations',{})[observation_id]=deepcopy(observation)
    updated=transition_effect(updated,{'effect_id':identifier,'status':'reconciled','now_ms':now,
        'termination_observation_id':observation_id,'termination_receipt':observation})
    receipt={'status':'block','reason_code':'NATIVE_ORPHAN_RECONCILED','invocation_id':identifier,
        'binding_id':binding['binding_id'],'run_id':binding['run_id'],'termination_observation_id':observation_id}
    if native:
        updated['native_invocations'][identifier].update(status='interrupted',retry_allowed=False,
            recovery=observation_id,error_kind='unavailable')
        updated.setdefault('model_receipts',{}).setdefault(identifier,{**native.get('decision',{}),**receipt,'scope':native.get('scope',{})})
    state['runs'][binding['run_id']]=updated
    return receipt


def reconcile_native(root,request,operation_id):
    from .host_projection import read_host
    from .hosts import validate_binding
    from .native_runtime import _native_lease,_commit
    root=Path(root);client_hash=digest(request)
    initial=read_host(root,request=request,operation_id=operation_id)
    prior=initial['operations'].get(operation_id)
    if prior:
        need(prior['kind']=='domain.host.native-reconcile' and prior['payload']['request'].get('client_request_hash')==client_hash,'Recovery operation belongs to another request.')
        return {**initial['data']['domain_receipts'][operation_id],'replayed':True}
    binding=validate_binding(initial['data'],request.get('binding_id'),request.get('revision'))
    identifier=request['invocation_id'];key=hashlib.sha256((binding['run_id']+':'+identifier).encode()).hexdigest()
    lease=root/'native-invocations'/key;lease.parent.mkdir(parents=True,exist_ok=True)
    with _native_lease(lease):
        state=read_host(root,request=request,operation_id=operation_id)
        prior=state['operations'].get(operation_id)
        if prior:
            need(prior['payload']['request'].get('client_request_hash')==client_hash,'Recovery operation conflict.')
            return {**state['data']['domain_receipts'][operation_id],'replayed':True}
        run=state['data']['runs'][binding['run_id']];effect=run.get('effects',{}).get(identifier,{})
        native=run.get('native_invocations',{}).get(identifier,{})
        need(effect,'Known reserved effect required.')
        observation=observe(identifier,native.get('launcher_pid',effect.get('owner_pid')),effect.get('worker_ref') or identifier,
            request.get('worker_stop_confirmation',{}),key)
        return _commit(root,operation_id,'native-reconcile',{'binding_id':binding['binding_id'],'revision':binding['revision'],
            'invocation_id':identifier,'observation_id':operation_id+':termination','observation':observation,'client_request_hash':client_hash},binding)


def validate_tool_observation(claimed,observation):
    confirmation=observation.get('confirmation',{})
    need(observation.get('owner_pid')==claimed.get('owner_pid') and observation.get('effect_id')==claimed.get('id')
         and observation.get('worker_ref')==claimed.get('id') and observation.get('owner_absent') is True
         and observation.get('basis')=='os-owner-stopped' and observation.get('evidence_refs')
         and confirmation.get('approved') is True and confirmation.get('actor_id') and confirmation.get('worker_ref')==claimed.get('id')
         and confirmation.get('provenance',{}).get('kind')=='user-message' and confirmation['provenance'].get('ref'),
         'Bound tool coordinator observation and exact actual user worker-stop evidence required.')


def reconcile_tool(root,run_id,execution_id,confirmation,operation_id):
    from .storage_access import read_current,operation_lookup
    from .store import transact
    root=Path(root);client=digest({'run_id':run_id,'execution_id':execution_id,'confirmation':confirmation})
    prior=operation_lookup(root,operation_id)
    if prior:
        need(prior['kind']=='domain.enforcement.tool-reconcile' and prior['payload']['request']['record'].get('client_hash')==client,'Recovery operation conflict.')
        return {'status':'block','reason_code':'TOOL_RECONCILED','replayed':True}
    state=read_current(root,run_id=run_id);run=state['data']['runs'][run_id]
    claimed=next((c for c in run.get('active_executions',{}).values() if c['id']==execution_id),None)
    need(claimed,'Known active/uncertain tool required.')
    key=hashlib.sha256((run_id+':'+execution_id).encode()).hexdigest()
    observation=observe(execution_id,claimed['owner_pid'],execution_id,confirmation,key)
    transact(root,state['version'],operation_id,{'kind':'domain.enforcement.tool-reconcile','payload':{'request':{'run_id':run_id,
        'record':{'item_id':claimed['item_id'],'id':execution_id,'observation':observation,'client_hash':client}}}})
    return {'status':'block','reason_code':'TOOL_RECONCILED','replayed':False}


def reconcile_session(path,execution_id,confirmation,operation_id):
    from .session_evidence import _retry,_commit
    from .review_sessions import read_session
    client={'execution_id':execution_id,'confirmation':confirmation}
    prior=_retry(path,operation_id,'recovery',client)
    if prior:return prior
    state=read_session(path);claimed=state['subject'].get('executions',{}).get(execution_id,{})
    need(claimed.get('status') in {'launching','uncertain'},'Known active/uncertain tool required.')
    observation=observe(execution_id,claimed.get('owner_pid'),execution_id,confirmation,digest(str(Path(path).resolve())))
    return _commit(path,state,operation_id,'execution-reconcile',{'id':execution_id,'observation':observation},client=client,kind='recovery')
