"""Evidence-derived outcome metrics with explicit unavailable history."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import hashlib,json

def _date(value): return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)
def eligible_runs(state:dict,as_of:str)->list[dict]:
 cutoff=_date(as_of)
 return [deepcopy(r) for r in state.get('runs',[]) if r.get('status')=='delivered' and r.get('acceptance') is True and r.get('delivery_at') and _date(r['delivery_at'])<=cutoff]
def calculate_metrics(runs:list[dict],usage:dict,as_of:str)->dict:
 eligible=[r for r in runs if r.get('status')=='delivered' and r.get('acceptance') is True]
 final=bool(eligible) and all(r.get('delivery_at') and (_date(as_of)-_date(r['delivery_at'])).total_seconds()>=30*86400 for r in eligible)
 confirmed_by_issue={}
 for run in eligible:
  for classification in run.get('classifications',[]):
   if classification.get('confirmed') is not True: continue
   at=classification.get('confirmed_at')
   if at and not (_date(run['delivery_at']) <= _date(at) <= min(_date(as_of),_date(run['delivery_at'])+timedelta(days=30))): continue
   confirmed_by_issue[(run['id'],classification.get('issue_id',classification.get('proposal_hash')))] = classification
 confirmed=list(confirmed_by_issue.values())
 requirements=sum(len(r.get('accepted_requirements',[])) for r in eligible)
 return {'run_ids':[r.get('id') for r in eligible],'accepted_requirements':requirements,'confirmed_classifications':len(confirmed),'escaped_defects':sum(c.get('proposal',{}).get('kind')=='escaped-defect' for c in confirmed),'spec_gaps':sum(c.get('proposal',{}).get('kind')=='spec-gap' for c in confirmed),'escaped_defect_rate':sum(c.get('proposal',{}).get('kind')=='escaped-defect' for c in confirmed)/requirements if requirements else None,'defect_window_status':'final' if final else 'provisional','human_touchpoints':sum(r['human_touchpoints'] for r in eligible) if all('human_touchpoints' in r for r in eligible) and eligible else None,'usage_coverage':usage.get('coverage'),'excluded_run_ids':[r.get('id') for r in runs if r not in eligible],'as_of':as_of,'formula_version':'1'}
def freeze_report(state:dict,report:dict)->dict:
 result=deepcopy(state); history=result.setdefault('reports',[]); record=deepcopy(report); record['id']=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode()).hexdigest();
 if not any(r.get('id')==record['id'] for r in history):history.append(record)
 return result
