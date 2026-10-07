"""Idempotent external-write queue; connectors are injected by callers."""
from __future__ import annotations
from copy import deepcopy
import hashlib,json

def _hash(x): return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def enqueue_write(state:dict,approved_manifest_hash:str,operation:dict)->dict:
 authorization=state.get('write_authorizations',{}).get(operation.get('authorization_id')) if isinstance(operation,dict) else None
 if (not approved_manifest_hash or not isinstance(operation,dict) or not operation.get('id')
     or not authorization or authorization.get('approved') is not True
     or authorization.get('manifest_hash')!=approved_manifest_hash
     or authorization.get('operation_id')!=operation.get('id')
     or authorization.get('payload_hash')!=_hash(operation.get('payload'))):
  raise ValueError('recorded exact-manifest authorization required')
 result=deepcopy(state); box=result.setdefault('outbox',{}); digest=_hash(operation.get('payload'))
 old=box.get(operation['id'])
 record={'id':operation['id'],'manifest_hash':approved_manifest_hash,'payload':deepcopy(operation['payload']),'payload_hash':digest,'status':'pending','receipt':None,'authorization_id':operation['authorization_id'],'action':authorization.get('action')}
 if old and any(old.get(k)!=record[k] for k in ('manifest_hash','payload_hash','payload','authorization_id','action')): raise ValueError('operation ID scope conflict')
 box.setdefault(operation['id'],record)
 return result

def retry_writes(root, adapter):
 """Dispatch authorized writes from a durable control root, with crash recovery."""
 if isinstance(root, dict):
  raise TypeError('retry_writes requires a journal root, not an editable state dictionary')
 return _retry_journal(root, adapter)


def _retry_journal(root, adapter):
 from pathlib import Path
 from uuid import uuid4
 from .store import read_state, transact, WorkflowError
 root = Path(root).expanduser().resolve()
 for identifier in list(read_state(root)['data'].get('outbox', {})):
  state = read_state(root)
  record = state['data']['outbox'][identifier]
  if record['status'] == 'sent':
   continue
  if record['status'] == 'pending':
   token = uuid4().hex
   try:
    receipt = transact(root, state['version'], f'outbox:start:{identifier}',
        {'kind': 'domain.outbox.started', 'payload': {'request': {'id': identifier, 'token': token}}})
   except WorkflowError as exc:
    if exc.code == 'STALE_STATE':
     continue
    raise
   # Another dispatcher may have reserved this ID between read and commit.
   if receipt['replayed']:
    continue
   record = receipt['state']['data']['outbox'][identifier]
   try:
    response = adapter.send(deepcopy(record))
   except Exception:
    response = None
  else:
   # Interrupted sends are reconciled only. Never blindly resend them.
   reconcile = getattr(adapter, 'reconcile', None)
   try:
    response = reconcile(deepcopy(record)) if reconcile else None
   except Exception:
    response = None
  request = {'id': identifier, 'token': record['dispatch_token']}
  if isinstance(response, dict) and isinstance(response.get('receipt'), str) and response['receipt']:
   request['receipt'] = response['receipt']
   kind, operation_id = 'domain.outbox.receipt', f'outbox:receipt:{identifier}:{_hash(response["receipt"])}'
  else:
   kind, operation_id = 'domain.outbox.uncertain', f'outbox:uncertain:{identifier}'
  # A concurrent state update must not lose a known remote receipt.
  while True:
   latest = read_state(root)
   if latest['data']['outbox'][identifier]['status'] == 'sent':
    break
   try:
    transact(root, latest['version'], operation_id, {'kind': kind, 'payload': {'request': request}})
    break
   except WorkflowError as exc:
    if exc.code != 'STALE_STATE':
     raise
 return read_state(root)['data']

def classify_issue(state:dict,issue_id:str,proposal:dict,confirmed_hash:str|None)->dict:
 import copy
 expected=_hash({'issue_id':issue_id,'proposal':proposal})
 confirmed=confirmed_hash==expected
 return {'issue_id':issue_id,'proposal':copy.deepcopy(proposal),'proposal_hash':expected,'confirmed':confirmed,'metric_eligible':confirmed}

def prepare_reconciliation(state:dict,manifest:dict)->dict:
 eligible=(state.get('snapshot_complete') is True and state.get('manifest_hash')==manifest.get('hash')
           and state.get('residual_mandatory_work',0)==0 and state.get('delivered') is True)
 return {'eligible':eligible,'manifest_hash':manifest.get('hash'),'reason':None if eligible else 'snapshot, manifest, delivery, or residual work is not verified'}
