"""Explicit command/record read adapters; full materialization is audit-only."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
from .storage_format import detect_layout
from .storage_scopes import ReadScope, EntityQuery, GLOBAL_KEYS, DOMAIN_NAMESPACES


def read_current(root, *, run_id=None, run_ids=(), operations=(), namespaces=(), entities=(),
                 global_keys=GLOBAL_KEYS, active_runs=False, queries=(), binding_id=None):
    root = Path(root)
    if detect_layout(root)['layout'] != 'v2':
        from .store import read_state
        return read_state(root)
    from . import sqlite_store as sql
    ids = set(run_ids)
    if run_id: ids.add(run_id)
    selected = list(entities)
    selected.extend(('domain_receipts',op) for op in operations if op)
    if binding_id: selected.append(('host_bindings',binding_id))
    return sql.read_working_state(root,ReadScope(run_ids=tuple(sorted(ids)),global_keys=tuple(global_keys),
        namespaces=tuple(namespaces),entity_keys=tuple(selected),operation_ids=tuple(op for op in operations if op),
        active_runs=active_runs,queries=tuple(queries)))


def operation_lookup(root, operation_id, state=None):
    if not operation_id: return None
    if detect_layout(Path(root))['layout'] == 'v2':
        from .sqlite_store import lookup_operation
        return lookup_operation(root,operation_id)
    if state is None: state = read_current(root)
    return state['operations'].get(operation_id)


def _run_references(value):
    ids = set(); pending = [value]
    while pending:
        node = pending.pop()
        if isinstance(node,dict):
            if isinstance(node.get('run_id'),str):ids.add(node['run_id'])
            pending.extend(node.values())
        elif isinstance(node,list):pending.extend(node)
    return ids


def read_command(root, parsed, *, family=None, request=None):
    family = family or getattr(parsed,'command',None)
    ids = _run_references(request or {})
    run_id = getattr(parsed,'run_id',None)
    if run_id: ids.add(run_id)
    op = getattr(parsed,'operation_id',None)
    namespaces = []
    if family in {'issues','ingest'}: namespaces.extend(DOMAIN_NAMESPACES[family])
    if family == 'improve': namespaces.extend(('improvement_cases','improvement_feedback'))
    if family == 'stats': namespaces.extend(DOMAIN_NAMESPACES['stats'])
    if family == 'pr': namespaces.append('pr_setup')
    if family == 'issues': namespaces.append('outbox')
    return read_current(root,run_ids=tuple(ids),operations=(op,op+':start' if op else None),
                        namespaces=namespaces,binding_id=getattr(parsed,'mutation_binding_id',None))


def read_operation_context(root, operation_id):
    event = operation_lookup(root,operation_id)
    ids = _run_references(event.get('payload',{})) if event else set()
    if event and event.get('kind')=='run.started': ids.add(event['payload']['run']['id'])
    return read_current(root,run_ids=tuple(ids),operations=(operation_id,))


def history_projections(run):
    # Reporting facts remain separate from package/source/context bodies.
    metrics = {key:deepcopy(run[key]) for key in ('id','status') if key in run}
    metrics['acceptances'] = [{key:deepcopy(row[key]) for key in ('complete','fresh') if key in row} | {
        'requirements':[{key:entry[key] for key in ('id','verdict') if key in entry} for entry in row.get('requirements',[])]}
        for row in run.get('acceptances',[])]
    delivery = run.get('delivery') or {}
    metrics['delivery'] = {key:delivery[key] for key in ('recorded_at',) if key in delivery}
    if 'actual_result' in delivery:metrics['delivery']['actual_result'] = {'delivered_at':delivery['actual_result'].get('delivered_at')}
    routing = {'id':run.get('id'),'native_invocations':{}}
    for identifier,row in run.get('native_invocations',{}).items():
        decision=(row.get('decision') or {}).get('routing')
        selected={key:deepcopy(row[key]) for key in ('operation_id','status','retry_count','scope') if key in row}
        if decision is not None:
            selected['decision']={'routing':{key:deepcopy(decision[key]) for key in
                ('execution_path','escalation_index','retry_of','known_payload','task_facts') if key in decision}}
        result=row.get('result') or {}
        selected['result']={key:deepcopy(result[key]) for key in ('usage','worker_outcome','known_payload') if key in result}
        routing['native_invocations'][identifier]=selected
    allowed = ('id','status','plan','items','active_attempt','verifier_proofs','verification_proofs',
        'pending_pr','pr_open','pr_rework','pr_rejected','hardening_config','hardening_config_hash','hardening_proofs',
        'required_hardening_gates','unresolved_findings','reviews','acceptances','repair_cycles','model_receipts',
        'model_interruptions','improvement_trace_enabled','elapsed_ms')
    trace = {key:deepcopy(run[key]) for key in allowed if key in run}
    return {'metrics':metrics,'routing':routing,'trace':trace}


def read_history(root, view, *, run_id=None, namespaces=()):
    if detect_layout(Path(root))['layout'] != 'v2': return read_current(root)
    from .sqlite_store import read_working_state
    return read_working_state(root,ReadScope(global_keys=(),namespaces=tuple(name for name in namespaces if name!='usage'),
        run_ids=(run_id,) if run_id else (),run_view=view,history_all=run_id is None,
        usage_run_ids=(run_id,) if run_id and 'usage' in namespaces else ()))


def read_entity(root, namespace, key):
    return read_current(root,global_keys=(),entities=((namespace,key),))['data'].get(namespace,{}).get(key)


def document_diff_approved(root, data, repo_id, path, record):
    def matches(proposal, approvals):
        return (proposal.get('repo_id')==repo_id and proposal.get('files',{}).get(path)==record
                and proposal.get('proposal_hash') in approvals)
    if detect_layout(Path(root))['layout'] != 'v2':
        return any(matches(proposal,data.get('document_approvals',{})) for proposal in data.get('document_proposals',{}).values())
    from . import sqlite_store as sql
    with sql.connection(root) as conn:
        rows = conn.execute('SELECT f.proposal_id FROM document_files f JOIN entities a ON a.space=? AND a.key=f.proposal_id WHERE f.repo_id=? AND f.path=? AND f.record_hash=?',
            (sql._space(('document_approvals',)),repo_id,path,sql._sha(sql._json(record).encode('utf-8')))).fetchall()
        for (key,) in rows:
            proposal=sql._lookup_entity(conn,Path(root),'document_proposals',key)
            approval=sql._lookup_entity(conn,Path(root),'document_approvals',key)
            if proposal and approval and matches(proposal,{key:approval}):return True
    return False


def metrics_source_hash(root, conn, data):
    """Preserve the original flat canonical source hash without a giant run map."""
    import hashlib
    from . import sqlite_store as sql
    from .stored_records import canonical, stream_cell_json
    checksum=hashlib.sha256();checksum.update(b'{')
    for i,name in enumerate(sorted(('runs','classifications','usage','prices'))):
        checksum.update((b',' if i else b'')+canonical(name)+b':')
        if name!='runs':checksum.update(canonical(data.get(name)));continue
        if not conn.execute('SELECT 1 FROM spaces WHERE path=?',(sql._space(('runs',)),)).fetchone():
            checksum.update(b'null');continue
        checksum.update(b'{')
        for j,(key,codec,payload,expected) in enumerate(conn.execute('SELECT key,codec,payload,value_hash FROM entities WHERE space=? ORDER BY key', (sql._space(('runs',)),))):
            checksum.update((b',' if j else b'')+canonical(key)+b':')
            for chunk in stream_cell_json(root,codec,payload,expected):checksum.update(chunk)
        checksum.update(b'}')
    checksum.update(b'}');return checksum.hexdigest()


def find_entity_id(root, namespace, identity):
    if detect_layout(Path(root))['layout']!='v2':
        values=read_current(root)['data'].get(namespace,[])
        return next((row for row in values if row.get('id')==identity),None)
    from . import sqlite_store as sql
    with sql.connection(root) as conn:
        row=conn.execute('SELECT codec,payload,value_hash FROM entities WHERE space=? AND record_id=? ORDER BY position LIMIT 1',
            (sql._space((namespace,)),identity)).fetchone()
        return sql._decode(root,*row) if row else None
