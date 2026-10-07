"""Configured local gates and stable cross-repository work ordering."""
from __future__ import annotations
from pathlib import Path
import hashlib,subprocess

def verify_gate(root:Path,run_id:str,gate_id:str,command:list[str])->dict:
 root=Path(root).expanduser().resolve()
 if not command:return {'passed':False,'failure':'COMMAND_UNAVAILABLE'}
 try: result=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=900,check=False)
 except (OSError,subprocess.TimeoutExpired): return {'passed':False,'failure':'COMMAND_UNAVAILABLE'}
 digest=hashlib.sha256((result.stdout+result.stderr).encode()).hexdigest()
 return {'passed':result.returncode==0,'failure':None if result.returncode==0 else 'GATE_FAILED','run_id':run_id,'gate_id':gate_id,'argv':command,'output_hash':digest}

def repository_schedule(plan:dict,repositories:dict)->dict:
 items={x['id']:x for x in plan.get('work_items',[])}; order=[]; done=set(); visiting=set()
 def visit(k):
  if k in visiting: raise ValueError('dependency cycle')
  if k in done:return
  if k not in items: raise ValueError('unknown dependency')
  visiting.add(k)
  for dep in items[k].get('dependencies',[]):visit(dep)
  visiting.remove(k);done.add(k);order.append(k)
 for k in items:visit(k)
 missing=sorted({x.get('repo_id') for x in items.values()}-set(repositories))
 return {'order':order,'repositories':sorted(set(x.get('repo_id') for x in items.values())),'missing_repositories':missing,'valid':not missing}
