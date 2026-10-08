"""Production native discovery and scoped invocation coordinator; hooks never call it."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import time
from .platform_lock import exclusive_file
from .process_liveness import process_alive
from contextlib import contextmanager
from .store import WorkflowError, read_state, transact, HOST_CONTEXT, _atomic_json
from .hosts import validate_binding, invocation_scope
from .releases import PACKAGE_ROOT, release_descriptor, check_release
from .model_policy import effective_preferences, resolve_profile
from .native_models import NativeCache, CodexBackend, ClaudeBackend, NativeError
from .host_completion import host_brief
from .evidence import _blob

@contextmanager
def _native_lease(path):
    with path.open('a+b') as handle:
        try:
            with exclusive_file(handle, blocking=False):
                yield handle
        except BlockingIOError as exc:
            raise WorkflowError('NATIVE_INVOCATION_ACTIVE', 'Native invocation lease is held.') from exc



def policy():return json.loads((PACKAGE_ROOT/'definitions/model-policy.json').read_text(encoding='utf-8'))

def pointer_path(root,binding):
    name=hashlib.sha256((binding['host']+':'+binding['binding_id']).encode()).hexdigest()
    return Path(root)/'native-model-context'/f'{name}.json'


def cached_context(root,binding):
    if root is None:return None
    try:pointer=json.loads(pointer_path(root,binding).read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    if not isinstance(pointer,dict) or pointer.get('binding_revision')!=binding.get('revision'):return None
    return NativeCache(root).get(binding['host'],pointer.get('account_key'),policy()['version'],release_descriptor()['fingerprint'],time.time())


def discover(root,binding,refresh=False,backend=None):
    owned=backend is None;backend=backend or (CodexBackend if binding['host']=='codex' else ClaudeBackend)(binding['project_dir'])
    try:
        identity=backend.identity();version=policy()['version'];release=release_descriptor()['fingerprint'];cache=NativeCache(root);now=time.time()
        context=None if refresh or not identity.get('cacheable') else cache.get(binding['host'],identity['account_key'],version,release,now)
        reused=context is not None
        if context is None:context=backend.discover();cache.put(binding['host'],identity['account_key'],version,release,context,now,900)
        path=pointer_path(root,binding);path.parent.mkdir(parents=True,exist_ok=True)
        _atomic_json(path,{'account_key':identity['account_key'],'binding_revision':binding['revision']})
        return {**context,'account_key':identity['account_key'],'cache_hit':reused,'cacheable_account':identity.get('cacheable',False)}
    finally:
        if owned:backend.close()


def preferences(data,binding,stage):return {**effective_preferences(data['runs'][binding['run_id']],stage,binding['host']),'host':binding['host'],'stage':stage}

def prices(data,request):return data.get('prices',{}).get(request.get('price_version'))


def resolve(data,binding,stage,context=None):
    request=preferences(data,binding,stage);context=context or {}
    return resolve_profile(policy(),request,context.get('capabilities',{'configure':False,'observe':False,'models':[],'efforts':[]}),context.get('discovery',{}),prices(data,request))


def candidate_intent(data,binding,stage,context):
    """Only an explicit permitted advisory selection may await actual native access."""
    request=preferences(data,binding,stage);pin=request.get('pin');cap=context['capabilities']
    if not pin or request.get('mode','advisory')!='advisory' or not cap.get('configure'):return resolve(data,binding,stage,context)
    # This is eligibility of the requested intent, not an availability observation.
    proposed=deepcopy(context);proposed['capabilities']['models']=list(set(proposed['capabilities']['models'])|{pin})
    proposed['capabilities'].setdefault('model_efforts',{})[pin]=cap['efforts']
    proposed['discovery']['models'][pin]='available'
    decision=resolve(data,binding,stage,proposed)
    if decision['status']=='allow' and decision.get('resolved'):
        return {**decision,'status':'pending-access','reason_code':'NATIVE_ACCESS_PENDING','eligible_reason_code':decision['reason_code'],'dispatch':False}
    return decision


def invalidate(root,binding,context):
    NativeCache(root).invalidate(binding['host'],context['account_key'],policy()['version'],release_descriptor()['fingerprint'])


def remember_selected(root,binding,context,resolved):
    updated={k:deepcopy(context[k]) for k in ('capabilities','discovery')}
    model=resolved['model'];effort=resolved['effort']
    updated['discovery']['models'][model]='available'
    if model not in updated['capabilities']['models']:updated['capabilities']['models'].append(model)
    values=updated['capabilities'].setdefault('model_efforts',{}).setdefault(model,[])
    if effort not in values:values.append(effort)
    NativeCache(root).put(binding['host'],context['account_key'],policy()['version'],release_descriptor()['fingerprint'],updated,time.time(),900)


def probe(root,binding,stage,refresh=False):
    data=read_state(Path(root))['data'];backend=(CodexBackend if binding['host']=='codex' else ClaudeBackend)(binding['project_dir'])
    try:
        context=discover(root,binding,refresh,backend);decision=resolve(data,binding,stage,context)
        if not decision.get('resolved'):decision=candidate_intent(data,binding,stage,context)
        if decision['status'] not in {'allow','pending-access'} or not decision.get('resolved'):return decision
        selected=decision['resolved']
        if binding['host']=='codex':
            backend.configure(selected,'DevFlow selected-model configuration validation. No tools, file access or external actions.','read-only')
            result=backend.invoke(selected,'Reply exactly DEVFLOW_MODEL_PROBE. Do not use tools or inspect files.',binding['actor_id'],'read-only',60)
        else:result=backend.invoke(selected,'Reply exactly DEVFLOW_MODEL_PROBE. Do not inspect files or use tools.',binding['actor_id'],'none',60)
        observed=result.get('observed',{})
        if observed.get('model')!=selected['model'] or observed.get('provider') and observed['provider']!=selected['provider']:
            invalidate(root,binding,context);return {'status':'block','reason_code':'MODEL_SUBSTITUTED','requested':selected,'observed':observed}
        if binding['host']=='codex' and observed.get('effort')!=selected['effort']:
            invalidate(root,binding,context);return {'status':'block','reason_code':'MODEL_SUBSTITUTED','requested':selected,'observed':observed}
        remember_selected(root,binding,context,selected)
        return {'status':'allow','reason_code':'NATIVE_SELECTION_VALIDATED','requested':selected,'observed':observed,'observation_source':result['observation_source'],'invocation_ref':result['invocation_ref'],'capability_validated':False,'mode':decision['mode']}
    except NativeError as exc:
        if 'context' in locals():invalidate(root,binding,context)
        return {'status':'block','reason_code':exc.code,'error_kind':exc.error_kind,'message':str(exc)}
    finally:backend.close()


def _commit(root,identifier,kind,request,binding):
    token=HOST_CONTEXT.set({'binding_id':binding['binding_id'],'revision':binding['revision'],'release':binding['release']})
    try:
        event={'kind':'domain.host.'+kind,'payload':{'request':request}}
        for attempt in range(8):
            state=read_state(Path(root));previous=state['operations'].get(identifier)
            if previous and (previous['kind']!=event['kind'] or previous['payload']!=event['payload']):raise WorkflowError('OPERATION_CONFLICT','Native operation ID belongs to another request.')
            try:receipt=transact(Path(root),state['version'],identifier,event)
            except WorkflowError as exc:
                if exc.code!='STALE_STATE' or attempt==7:raise
                continue
            return receipt['state']['data']['domain_receipts'][identifier]
    finally:HOST_CONTEXT.reset(token)


def invoke(root,request,operation_id):
    root=Path(root);state=read_state(root);data=state['data'];binding=data.get('host_bindings',{}).get(request.get('binding_id'))
    if not binding:raise WorkflowError('BINDING_REQUIRED','Known native binding required.')
    identifier=request.get('invocation_id');stage=request.get('stage');prompt=request.get('prompt');access=request.get('access','read-only')
    if not isinstance(identifier,str) or not identifier or not isinstance(prompt,str) or not prompt.strip() or len(prompt.encode())>65536:raise WorkflowError('NATIVE_INPUT_REQUIRED','Invocation ID, stage and bounded nonempty prompt are required.')
    if access not in {'read-only','workspace-write'} or access=='workspace-write' and (binding['role']!='implementer' or stage!='implementation'):raise WorkflowError('NATIVE_ACCESS_DENIED','Write access is explicit and restricted to implementation work.')
    request_hash=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    run=data['runs'][binding['run_id']];prior=run.get('native_invocations',{}).get(identifier)
    if prior:
        if prior.get('request_hash')!=request_hash or prior.get('operation_id')!=operation_id:raise WorkflowError('OPERATION_CONFLICT','Invocation ID belongs to another request.')
        if prior['status']=='running':raise WorkflowError('NATIVE_INVOCATION_ACTIVE','Invocation is already running; inspect native status and reconcile only after it stops.')
        return {**run['model_receipts'][identifier],'replayed':True}
    binding=validate_binding(data,request['binding_id'],request['revision'])
    parity=check_release(binding['release'],release_descriptor(),1)
    if parity['status']!='allow':raise WorkflowError('RELEASE_MISMATCH',parity['message'])
    if stage not in policy()['stages']:raise WorkflowError('PROFILE_UNAVAILABLE','Known native stage required.')
    if policy()['stages'][stage]=='deterministic':return {'status':'allow','reason_code':'DETERMINISTIC','dispatch':False}
    timeout=request.get('timeout_seconds',300)
    if type(timeout) not in (int,float) or not 1<=timeout<=3600:raise WorkflowError('NATIVE_TIMEOUT_INVALID','Native timeout must be between 1 and 3600 seconds.')
    backend=None;context=None;started=False;result=None
    lease=root/'native-invocations'/hashlib.sha256((binding['run_id']+':'+identifier).encode()).hexdigest();lease.parent.mkdir(parents=True,exist_ok=True)
    with _native_lease(lease) as lock:
        # Another launcher may have completed between the initial read and lease acquisition.
        data=read_state(root)['data'];run=data['runs'][binding['run_id']]
        prior=run.get('native_invocations',{}).get(identifier)
        if prior:
            if prior.get('request_hash')!=request_hash or prior.get('operation_id')!=operation_id:raise WorkflowError('OPERATION_CONFLICT','Invocation ID belongs to another request.')
            if prior['status']=='running':raise WorkflowError('NATIVE_INVOCATION_ACTIVE','Interrupted launcher requires explicit stopped-worker reconciliation.')
            return {**run['model_receipts'][identifier],'replayed':True}
        binding=validate_binding(data,request['binding_id'],request['revision'])
        try:
            backend=(CodexBackend if binding['host']=='codex' else ClaudeBackend)(binding['project_dir'])
            context=discover(root,binding,request.get('refresh',False),backend)
            decision=resolve(data,binding,stage,context)
            if not decision.get('resolved'):decision=candidate_intent(data,binding,stage,context)
            if decision['status'] not in {'allow','pending-access'} or not decision.get('resolved'):return {**decision,'message':'Choose a permitted model or resolve the reported policy blocker before native work.'}
            brief=json.dumps(host_brief(data,binding),ensure_ascii=False,separators=(',',':'))
            prompt='DevFlow actor '+binding['actor_id']+'; stage '+stage+'.\nScoped authoritative brief:\n'+brief+'\nTask:\n'+prompt
            if len(prompt.encode())>262144:raise WorkflowError('NATIVE_CONTEXT_OVERFLOW','Mandatory native context exceeds budget; inspect references and scope the task.')
            start={'binding_id':binding['binding_id'],'revision':binding['revision'],'invocation_id':identifier,'stage':stage,'decision':decision,'request_hash':request_hash,'operation_id':operation_id,'policy_revision':len(run.get('model_overrides',[])),'expected_scope':invocation_scope(binding,run,stage,{}),'launcher_pid':os.getpid(),'account_key':context['account_key'],'replacement_of':request.get('replacement_of'),'replacement_authorization':request.get('replacement_authorization')}
            _commit(root,operation_id+':native-start','native-start',start,binding);started=True
            if request.get('task_id'):
                scope=invocation_scope(binding,run,stage,{})
                task={'binding_id':binding['binding_id'],'revision':binding['revision'],'task_id':request['task_id'],'invocation_id':identifier,'scope':'item' if stage=='implementation' else 'review',**{k:scope[k] for k in ('item_id','token','package_hash') if k in scope}}
                if stage not in {'implementation','review','acceptance'}:raise WorkflowError('NATIVE_TASK_SCOPE','Only implementation/review/acceptance can map a native host task.')
                task.update({k:request[k] for k in ('replace','previous_mapping_hash') if k in request})
                _commit(root,operation_id+':native-map','task-bind',task,binding)
                from .host_locators import write_task_index
                now=read_state(root)['data'];tasks=[t['task_id'] for t in now.get('host_tasks',{}).values() if t['host']==binding['host'] and t['session_id']==binding['session_id']]
                write_task_index(Path(binding['project_dir']),binding['host'],binding['session_id'],root,tasks)
            if binding['host']=='codex':
                configuration=backend.configure(decision['resolved'],brief,access)
                observed=configuration['observed'];resolved=decision['resolved']
                if any(observed.get(k)!=resolved.get(k) for k in ('model','effort','provider')):
                    result={**configuration,'status':'interrupted','error_kind':'unavailable','reason_code':'MODEL_SUBSTITUTED'}
            if result is None:result=backend.invoke(decision['resolved'],prompt,binding['actor_id'],access,request.get('timeout_seconds',300))
            result['output_ref']=_blob(root,result.pop('output',''))
        except NativeError as exc:
            if context:invalidate(root,binding,context)
            if not started:return {'status':'block','reason_code':exc.code,'error_kind':exc.error_kind,'message':str(exc)}
            result={'status':'interrupted','error_kind':exc.error_kind,'reason_code':exc.code}
        except BaseException:
            if started:
                if backend:backend.close();backend=None
                _commit(root,operation_id+':native-finish','native-finish',{'binding_id':binding['binding_id'],'revision':binding['revision'],'invocation_id':identifier,'result':{'status':'interrupted','error_kind':'unavailable','reason_code':'NATIVE_EXECUTION_INTERRUPTED'}},binding)
            raise
        finally:
            if backend:backend.close()
        receipt=_commit(root,operation_id+':native-finish','native-finish',{'binding_id':binding['binding_id'],'revision':binding['revision'],'invocation_id':identifier,'result':result},binding)
        if receipt['status']=='allow' and context:remember_selected(root,binding,context,receipt['resolved'])
        elif context:invalidate(root,binding,context)
        return receipt


def handoff_preflight(root,data,target):
    """Native destination access validation occurs before ownership changes."""
    target={**target,'revision':1}
    request=preferences(data,target,'implementation')
    revision=len(data['runs'][target['run_id']].get('model_overrides',[]))
    if not request.get('pin') and request.get('mode','advisory')=='advisory' and not any(policy().get('hosts',{}).get(target['host'],{}).values()):
        return {**resolve(data,target,'implementation'),'policy_revision':revision}
    context=discover(root,target)
    decision=resolve(data,target,'implementation',context)
    if request.get('mode','advisory')=='strict' and not context['capabilities'].get('observe'):
        return {**decision,'status':'block','reason_code':'EFFECTIVE_CONFIGURATION_UNOBSERVABLE','policy_revision':revision}
    selected=probe(root,target,'implementation')
    if selected['status']!='allow':return {**selected,'policy_revision':revision}
    decision=resolve(data,target,'implementation',cached_context(root,target))
    return {**decision,'observed':selected.get('observed'),'observation_source':selected.get('observation_source'),'invocation_ref':selected.get('invocation_ref'),'policy_revision':revision}


def reconcile(root,request,operation_id):
    """Never kill or restart a worker; explicit stop attestation closes an orphan."""
    root=Path(root);state=read_state(root);data=state['data']
    finish={'binding_id':request.get('binding_id'),'revision':request.get('revision'),'invocation_id':request.get('invocation_id'),'client_request_hash':hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'result':{'status':'interrupted','error_kind':'unavailable','reason_code':'NATIVE_ORPHAN_RECONCILED','worker_stop_confirmation':request.get('worker_stop_confirmation')}}
    previous=state['operations'].get(operation_id)
    if previous:
        if previous['kind']!='domain.host.native-finish' or previous['payload']!={'request':finish}:raise WorkflowError('OPERATION_CONFLICT','Reconciliation operation belongs to another request.')
        return {**data['domain_receipts'][operation_id],'replayed':True}
    binding=validate_binding(data,request.get('binding_id'),request.get('revision'))
    identifier=request.get('invocation_id');record=data['runs'][binding['run_id']].get('native_invocations',{}).get(identifier,{})
    if record.get('status')!='running' or record.get('scope',{}).get('binding_id')!=binding['binding_id']:
        raise WorkflowError('NATIVE_INVOCATION_REQUIRED','This binding needs a running invocation.')
    confirmation=request.get('worker_stop_confirmation') or {}
    if not isinstance(confirmation,dict) or confirmation.get('approved') is not True or not isinstance(confirmation.get('actor_id'),str) or not confirmation['actor_id']:
        raise WorkflowError('NATIVE_STOP_CONFIRMATION_REQUIRED','After inspecting and stopping the native process and its children, record the human actor confirming they stopped.')
    lease=root/'native-invocations'/hashlib.sha256((binding['run_id']+':'+identifier).encode()).hexdigest();lease.parent.mkdir(parents=True,exist_ok=True)
    with _native_lease(lease) as lock:
        pid=record.get('launcher_pid')
        if isinstance(pid,int) and pid>0:
            if process_alive(pid) is not False:
                raise WorkflowError('NATIVE_INVOCATION_ACTIVE','Recorded launcher is alive or its liveness cannot be disproved; PID reuse also fails closed.')
        return _commit(root,operation_id,'native-finish',finish,binding)
