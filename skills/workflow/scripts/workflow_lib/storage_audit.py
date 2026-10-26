"""Durable physical-maintenance receipts, distinct from logical workflow events."""
from pathlib import Path
import hashlib
import json
from .storage_format import confined_path
from .stored_records import digest
from .store import WorkflowError,_atomic_json,_exclusive,HOST_CONTEXT,_guard_transaction
from .platform_lock import sync_directory

LIMIT=16*1024*1024

def operation_key(operation_id):return hashlib.sha256(operation_id.encode('utf-8')).hexdigest()

def paths(root,operation_id):
    key=operation_key(operation_id)
    return (confined_path(root,'maintenance-receipts/'+key+'.json'),
            confined_path(root,'maintenance-receipts/pending/'+key+'.json'))

def read_record(path):
    try:
        with path.open('rb') as stream:raw=stream.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError('oversized audit record')
        record=json.loads(raw)
        if set(record)!={'body','sha256'} or digest(record['body'])!=record['sha256'] or record['body'].get('audit_version')!=1:
            raise ValueError('invalid audit identity')
        return record['body']
    except (ValueError,TypeError,KeyError) as exc:raise WorkflowError('MAINTENANCE_AUDIT_INVALID','Physical maintenance audit is invalid; preserve it for recovery.') from exc

def operation_reserved(root,operation_id):
    for path in paths(root,operation_id):
        if path.exists():
            record=read_record(path)
            if record.get('operation_id')!=operation_id:raise WorkflowError('MAINTENANCE_AUDIT_INVALID','Operation locator differs from its audit record.')
            return record
    return None

def write_record(path,body):
    path.parent.mkdir(parents=True,exist_ok=True)
    encoded={'body':body,'sha256':digest(body)}
    if len(json.dumps(encoded).encode('utf-8'))>LIMIT:raise WorkflowError('MAINTENANCE_AUDIT_LIMIT','Maintenance audit exceeds its bounded record limit.')
    _atomic_json(path,encoded)

def perform(root,kind,request,operation_id,actor_id,action):
    if not all(isinstance(value,str) and value.strip() for value in (operation_id,actor_id)):
        raise WorkflowError('MAINTENANCE_IDENTITY_REQUIRED','An explicit operation ID and actor ID are required.')
    root=Path(root).resolve()
    with _exclusive(root):
        from .storage_access import read_current,operation_lookup
        guard=HOST_CONTEXT.get()
        if guard:
            state=read_current(root,global_keys=(),binding_id=guard['binding_id'])
            _guard_transaction(state,{'kind':'maintenance.physical','payload':{}})
        if operation_lookup(root,operation_id) is not None:
            raise WorkflowError('OPERATION_CONFLICT','Operation ID already belongs to workflow history.')
        receipt,pending=paths(root,operation_id)
        fingerprint=digest({'kind':kind,'request':request,'actor_id':actor_id})
        prior=operation_reserved(root,operation_id)
        if prior:
            if prior.get('request_hash')!=fingerprint:raise WorkflowError('OPERATION_CONFLICT','Maintenance operation belongs to another actor or request.')
            if 'result' in prior:return {**prior['result'],'replayed':True}
        else:
            prior={'audit_version':1,'operation_id':operation_id,'actor_id':actor_id,'kind':kind,
                'request':request,'request_hash':fingerprint}
            write_record(pending,prior)
        result=action(prior)
        if result.get('completed',True):
            write_record(receipt,{**prior,'result':result})
            pending.unlink(missing_ok=True);sync_directory(pending.parent)
        return {**result,'replayed':False}


def verify_receipts(root,conn=None,*,logical_operations=()):
    root=Path(root).resolve();directory=confined_path(root,'maintenance-receipts')
    if not directory.exists():return 0
    count=0
    for path in directory.rglob('*.json'):
        confined_path(root,path.relative_to(root).as_posix());body=read_record(path)
        if path.parent.name=='progress':
            if not isinstance(body.get('candidates'),list) or not isinstance(body.get('plan_hash'),str):
                raise WorkflowError('MAINTENANCE_AUDIT_INVALID','GC progress metadata is incomplete.')
            continue
        operation_id=body.get('operation_id');actor_id=body.get('actor_id')
        if (not isinstance(operation_id,str) or not operation_id or operation_key(operation_id)!=path.stem
                or not isinstance(actor_id,str) or not actor_id.strip()
                or body.get('kind') not in {'gc','compact','backup','pins-reconcile'}
                or digest({'kind':body['kind'],'request':body.get('request'),'actor_id':actor_id})!=body.get('request_hash')
                or operation_id in logical_operations
                or conn is not None and conn.execute('SELECT 1 FROM events WHERE operation_id=?',(operation_id,)).fetchone()):
            raise WorkflowError('MAINTENANCE_AUDIT_INVALID','Maintenance identity, request or workflow operation uniqueness is invalid.')
        count+=1
    return count
