"""Local issue intake and complete-snapshot grouping."""
from __future__ import annotations
from copy import deepcopy
import hashlib,json

def _hash(x): return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def capture_issue(state:dict,issue:dict)->dict:
 if not isinstance(issue,dict) or not isinstance(issue.get('id'),str) or not issue['id']: raise ValueError('issue ID required')
 result=deepcopy(state); items=result.setdefault('issues',{}); old=items.get(issue['id'],{})
 items[issue['id']]={**old,'id':issue['id'],'original':deepcopy(issue),'fingerprint':_hash(issue)}
 return result

def validate_snapshot(snapshot:dict)->dict:
 errors=[]
 if not isinstance(snapshot,dict) or snapshot.get('complete') is not True: errors.append('snapshot is incomplete')
 pages=snapshot.get('pages',[]) if isinstance(snapshot,dict) else []
 if snapshot.get('expected_pages') is not None and len(pages)!=snapshot['expected_pages']: errors.append('snapshot pages are missing')
 if not isinstance(snapshot.get('issues'),list): errors.append('issues list is missing')
 return {'valid':not errors,'errors':errors,'snapshot_hash':_hash(snapshot) if not errors else None}

def revise_groups(state:dict,snapshot_hash:str,groups:list[dict])->dict:
 snap=next((v for v in state.get('snapshots',{}).values() if _hash(v)==snapshot_hash),None)
 if not snap or not validate_snapshot(snap)['valid']: raise ValueError('complete current snapshot required')
 known={i.get('id') for i in snap['issues']}; assigned=[]
 for group in groups:
  ids=group.get('issue_ids',[])
  if any(i not in known for i in ids): raise ValueError('group contains unknown issue')
  assigned.extend(ids)
 if set(assigned)!=known or len(assigned)!=len(set(assigned)): raise ValueError('every issue must be assigned exactly once')
 result=deepcopy(state); history=result.setdefault('group_revisions',[]); record={'snapshot_hash':snapshot_hash,'groups':deepcopy(groups),'revision':len(history)+1}; history.append(record); result['groups']=record['groups']; result['snapshot_valid']=True; result['snapshot_hash']=snapshot_hash; return result

def start_issue_run(state:dict,group_id:str,intent:str)->dict:
 if intent not in {'capture','specify','build'}: raise ValueError('unsupported issue intent')
 group=next((g for g in state.get('groups',[]) if g.get('id')==group_id),None)
 if not group or not state.get('snapshot_valid',False): raise ValueError('issue group needs a current complete snapshot')
 return {'group_id':group_id,'intent':intent,'run_id':_hash({'group':group_id,'intent':intent})[:16]}
