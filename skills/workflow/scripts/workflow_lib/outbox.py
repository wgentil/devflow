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
 record={'id':operation['id'],'manifest_hash':approved_manifest_hash,'payload':deepcopy(operation['payload']),'payload_hash':digest,'status':'pending','receipt':None}
 if old and old['payload_hash']!=digest: raise ValueError('operation ID payload conflict')
 box.setdefault(operation['id'],record)
 return result

def retry_writes(state:dict,adapter:object)->dict:
 result=deepcopy(state)
 for op in result.get('outbox',{}).values():
  if op.get('status')=='sent': continue
  reconcile=getattr(adapter,'reconcile',None)
  receipt=reconcile(op) if reconcile else None
  if not receipt and op.get('status')=='failed':
   op['failure']='remote result remains unknown; no resend was attempted'
   continue
  if not receipt: receipt=adapter.send(op)
  if isinstance(receipt,dict) and receipt.get('receipt'):
   op.update(status='sent',receipt=receipt['receipt'])
  else: op.update(status='failed',failure='remote result unavailable; reconcile before retry')
 return result

def classify_issue(state:dict,issue_id:str,proposal:dict,confirmed_hash:str|None)->dict:
 import copy
 expected=_hash({'issue_id':issue_id,'proposal':proposal})
 confirmed=confirmed_hash==expected
 return {'issue_id':issue_id,'proposal':copy.deepcopy(proposal),'proposal_hash':expected,'confirmed':confirmed,'metric_eligible':confirmed}

def prepare_reconciliation(state:dict,manifest:dict)->dict:
 eligible=(state.get('snapshot_complete') is True and state.get('manifest_hash')==manifest.get('hash')
           and state.get('residual_mandatory_work',0)==0 and state.get('delivered') is True)
 return {'eligible':eligible,'manifest_hash':manifest.get('hash'),'reason':None if eligible else 'snapshot, manifest, delivery, or residual work is not verified'}
