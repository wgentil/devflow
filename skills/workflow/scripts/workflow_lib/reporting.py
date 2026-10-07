"""Deterministic report rollups and portable exports."""
from __future__ import annotations
import csv,io,json
from datetime import datetime,timezone

def rollup(reports:list[dict],scope:dict)->dict:
 eligible=[]; excluded=[]
 for r in reports:
  date=r.get('date','')
  matches=(scope.get('project') is None or r.get('project')==scope['project']) and (scope.get('version') is None or r.get('version')==scope['version']) and (scope.get('month') is None or date.startswith(scope['month']))
  (eligible if matches else excluded).append(r)
 nums=[r.get('numerator') for r in eligible if type(r.get('numerator')) in (int,float)]; dens=[r.get('denominator') for r in eligible if type(r.get('denominator')) in (int,float)]
 numerator=sum(nums); denominator=sum(dens); ratio=numerator/denominator if denominator else None
 return {'eligible_run_ids':[r.get('id') for r in eligible],'excluded_run_ids':[r.get('id') for r in excluded],'numerator':numerator,'denominator':denominator,'ratio':ratio,'scope':scope,'status':'available' if ratio is not None else 'unavailable'}
def export_report(report:dict,format:str)->str:
 if format=='json':return json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
 if format=='markdown':return '# Report\n\n'+ '\n'.join(f'- **{k}**: {v}' for k,v in sorted(report.items()))+'\n'
 if format=='csv':
  output=io.StringIO(); w=csv.writer(output); w.writerow(['field','value'])
  for k,v in sorted(report.items()):
   text=str(v)
   if text.startswith(('=','+','-','@','\t','\r')):text="'"+text
   w.writerow([k,text])
  return output.getvalue()
 raise ValueError('unsupported export format')
