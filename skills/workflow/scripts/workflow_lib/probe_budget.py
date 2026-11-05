"""Budgeted validation calls; generation is never triggered by status/replay."""
from pathlib import Path
import hashlib
import time
from .document_units import digest
from .store import WorkflowError, HOST_CONTEXT, transact
from .storage_access import read_current
from .effect_dispatch import reserve_dispatch, binding_owner
from .effect_claims import validate_active_dispatch
from .enforcement_live import source_observation


def budgeted_probe(root, binding, stage, refresh, estimated_cost, operation_id, execute, *, owner=None, data=None):
    from .native_runtime import _native_lease
    root=Path(root);owner=owner or binding
    if not operation_id: raise WorkflowError('OPERATION_ID_REQUIRED','An explicit probe operation identity is required.')
    if owner['run_id'] != binding['run_id'] or owner['project_dir'] != binding['project_dir']:
        raise WorkflowError('PROBE_SCOPE_INVALID','Probe must belong to the attached repository and run.')
    identifier='probe:'+operation_id
    request_hash=digest({'binding':binding_owner(binding),'owner':binding_owner(owner),'stage':stage,
        'refresh':refresh,'estimated_cost':estimated_cost,'overrides':data['runs'][binding['run_id']].get('model_overrides',[]) if data else []})
    lease=root/'native-invocations'/hashlib.sha256((binding['run_id']+':'+identifier).encode()).hexdigest()
    lease.parent.mkdir(parents=True,exist_ok=True)
    with _native_lease(lease):
        state=read_current(root,run_id=binding['run_id']);run=state['data']['runs'][binding['run_id']]
        prior=run.get('effects',{}).get(identifier)
        if prior:
            if prior.get('client_request_hash') != request_hash:raise WorkflowError('OPERATION_CONFLICT','Probe identity belongs to another request.')
            if prior.get('result') is not None:return {**prior['result'],'replayed':True}
            raise WorkflowError('EFFECT_ALREADY_CLAIMED','Probe is active or uncertain; reconcile rather than relaunch.')
        token=HOST_CONTEXT.set({'binding_id':owner['binding_id'],'revision':owner['revision'],'release':owner['release']})
        dispatched=False
        def advance(status, *, result=None, worker_ref=None):
            current=read_current(root,run_id=binding['run_id'])
            record={'effect_id':identifier,'status':status,'now_ms':int(time.time()*1000),'dispatch_started':dispatched}
            if result is not None:record['result']=result
            if worker_ref:record['worker_ref']=worker_ref
            response=transact(root,current['version'],operation_id+':probe-'+status,
                {'kind':'domain.enforcement.probe-transition','payload':{'request':{'run_id':binding['run_id'],'record':record}}})
            return response
        try:
            reserve_dispatch(root,binding['run_id'],identifier,'probe:'+owner['binding_id'],estimated_cost,operation_id,
                {'item_id':owner['item_id']} if owner.get('item_id') else {},owner_binding=owner,effect_kind='probe',client_request_hash=request_hash)
            advance('launching')
            def before_invoke():
                nonlocal dispatched
                current=read_current(root,run_id=binding['run_id'])['data']['runs'][binding['run_id']]
                if current.get('model_overrides',[]) != data['runs'][binding['run_id']].get('model_overrides',[]):
                    raise WorkflowError('STALE_STATE','Model policy changed before probe dispatch.')
                now=int(time.time()*1000)
                validate_active_dispatch(current,identifier,{**source_observation(current),'now_ms':now})
                dispatched=True
                return min(60,(current['effect_policy']['max_elapsed_ms']-(now-current['effects_started_ms']))/1000)
            result=execute(before_invoke)
            if result.get('invocation_ref'):
                advance('running',worker_ref=result['invocation_ref'])
                advance('completed',result=result,worker_ref=result['invocation_ref'])
            elif dispatched:advance('uncertain',result=result,worker_ref=identifier)
            else:advance('failed',result=result)
            return result
        except BaseException:
            current=read_current(root,run_id=binding['run_id'])['data']['runs'][binding['run_id']]
            if current.get('effects',{}).get(identifier,{}).get('status')=='launching':
                advance('uncertain' if dispatched else 'failed',worker_ref=identifier if dispatched else None)
            raise
        finally:HOST_CONTEXT.reset(token)
