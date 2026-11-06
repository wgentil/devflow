"""Configured local gates and stable cross-repository work ordering."""
from __future__ import annotations
from pathlib import Path
import hashlib,subprocess
import shutil
from .gate_reports import parse_gate_report

def verify_gate(root:Path,run_id:str,gate_id:str,command:list[str],contract:dict|None=None,*,artifacts_root:Path|None=None)->dict:
 root=Path(root).expanduser().resolve()
 if not command:return {'passed':False,'failure':'COMMAND_UNAVAILABLE'}
 if not Path(command[0]).is_absolute() and shutil.which(command[0]) is None:return {'passed':False,'failure':'COMMAND_UNAVAILABLE'}
 try:
  from .evidence import repository_fingerprint
  before=repository_fingerprint(root)
 except Exception: return {'passed':False,'failure':'REPOSITORY_NOT_REGISTERED','run_id':run_id,'gate_id':gate_id}
 from .tool_execution import before_command,started,ended
 before_command()
 timeout=900
 from .tool_execution import CURRENT_TOOL
 context=CURRENT_TOOL.get()
 if context:
  from .storage_access import read_current
  from .review_orchestration import remaining_seconds
  import time
  remaining=remaining_seconds(read_current(context['root'],run_id=context['run_id'])['data']['runs'][context['run_id']],int(time.time()*1000))
  if remaining is not None:timeout=min(timeout,remaining)
 try:
  started();result=subprocess.run(command,cwd=root,capture_output=True,timeout=timeout,check=False);ended()
 except (OSError,subprocess.TimeoutExpired): return {'passed':False,'failure':'COMMAND_UNAVAILABLE'}
 digest=hashlib.sha256(result.stdout+result.stderr).hexdigest()
 try: after=repository_fingerprint(root)
 except Exception: after=None
 refs={}
 if artifacts_root is not None:
  from .evidence import _blob
  refs={'stdout_ref':_blob(artifacts_root,result.stdout),'stderr_ref':_blob(artifacts_root,result.stderr),'exit_code':result.returncode}
 if after!=before:return {'passed':False,'failure':'STALE_CONFIGURATION','run_id':run_id,'gate_id':gate_id,'output_hash':digest,**refs}
 selected=contract or {'kind':'exit-status'}
 try:
  stdout=result.stdout.decode('utf-8') if selected.get('kind')=='json-report' else ''
 except UnicodeError:
  return {'passed':False,'failure':'INVALID_REPORT_ENCODING','run_id':run_id,'gate_id':gate_id,'output_hash':digest,**refs}
 report=parse_gate_report(selected,stdout,'',result.returncode)
 return {**report,'run_id':run_id,'gate_id':gate_id,'argv':command,'output_hash':digest,**refs}

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
