"""Current indexed host session, binding, task and selected-run authority."""
from pathlib import Path
import time
import json
from .storage_scopes import ReadScope,EntityQuery,GLOBAL_KEYS
from .storage_access import read_current,_run_references
from .storage_format import detect_layout

def read_host(root,**scope):
    started=time.perf_counter();state=_read_host(root,**scope)
    return {**state,'_context_read_ms':max(0,int((time.perf_counter()-started)*1000))}


def _read_host(root,*,host=None,session_id=None,binding_id=None,run_id=None,request=None,operation_id=None,hint_binding_id=None):
    root=Path(root);request=request or {}
    if detect_layout(root)['layout']!='v2':return read_current(root)
    from . import sqlite_store as sql
    binding_id=binding_id or request.get('binding_id')
    destination=request.get('destination') or {}
    host=host or request.get('host') or destination.get('host')
    session_id=session_id or request.get('session_id') or destination.get('session_id')
    ids=_run_references(request)
    if run_id:ids.add(run_id)
    entities=[('host_bindings',binding_id)] if binding_id else []
    if hint_binding_id:entities.append(('host_bindings',hint_binding_id))
    if request.get('handoff_id'):entities.append(('host_handoffs',request['handoff_id']))
    if operation_id:entities.append(('domain_receipts',operation_id))
    queries=[]
    if host and session_id:queries.append(EntityQuery('host_bindings',(('host',host),('session_id',session_id),('status','active'))))
    with sql.connection(root) as conn:
        initial=sql._read_view(conn,root,ReadScope(global_keys=(),entity_keys=tuple(entities),queries=tuple(queries),operation_ids=(operation_id,) if operation_id else ()))[0]
        for binding in initial['data'].get('host_bindings',{}).values():
            if binding.get('status')=='active' or binding['binding_id']==binding_id:ids.add(binding['run_id'])
        for handoff in initial['data'].get('host_handoffs',{}).values():
            if handoff.get('run_id'):ids.add(handoff['run_id'])
            if handoff.get('binding_id'):entities.append(('host_bindings',handoff['binding_id']))
        # Existing receipt may identify an attachment absent from a retry's input.
        receipt=initial['data'].get('domain_receipts',{}).get(operation_id,{})
        if isinstance(receipt,dict):
            if receipt.get('binding_id'):entities.append(('host_bindings',receipt['binding_id']))
            if receipt.get('run_id'):ids.add(receipt['run_id'])
        for identifier in ids:queries.extend((EntityQuery('host_bindings',(('run_id',identifier),)),EntityQuery('host_tasks',(('run_id',identifier),))))
        state=sql._read_view(conn,root,ReadScope(run_ids=tuple(ids),global_keys=GLOBAL_KEYS,entity_keys=tuple(entities),queries=tuple(queries),operation_ids=(operation_id,) if operation_id else ()))[0]
        # Resolve only effective price versions used by selected host/run policy;
        # old price catalogs do not enter routine status/completion/preparation.
        from .model_policy import effective_preferences
        from .releases import PACKAGE_ROOT
        stages=json.loads((PACKAGE_ROOT/'definitions/model-policy.json').read_text(encoding='utf-8'))['stages']
        hosts={row['host'] for row in state['data'].get('host_bindings',{}).values() if row.get('host') in {'claude','codex'}} | ({host} if host in {'claude','codex'} else set())
        versions={effective_preferences(run,stage,current_host).get('price_version')
            for run in state['data'].get('runs',{}).values() for stage in stages for current_host in hosts}
        for version in versions-{None}:
            price=sql._lookup_entity(conn,root,'prices',version)
            if price is not None:state['data'].setdefault('prices',{})[version]=price
        # Tasks/owners for a selected run matter, but another session's unrelated
        # run is never expanded. Host-hook callers use an exact session view.
        if host and session_id and not request:
            state['data']['host_bindings']={key:row for key,row in state['data'].get('host_bindings',{}).items() if row.get('host')==host and row.get('session_id')==session_id}
            state['data']['host_tasks']={key:row for key,row in state['data'].get('host_tasks',{}).items() if row.get('host')==host and row.get('session_id')==session_id}
        return state
