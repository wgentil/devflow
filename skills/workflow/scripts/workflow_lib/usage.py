"""Versioned import of explicitly supplied runtime usage records."""
from __future__ import annotations
from copy import deepcopy

def import_usage(records:list[dict],adapter_version:str,bindings:dict)->dict:
 events={};gaps=[]
 if adapter_version!='v1':return {'version':adapter_version,'events':[],'complete':False,'gaps':['unsupported adapter version']}
 for row in records:
  required=('source_id','event_id','provider','model','input_tokens','cached_tokens','output_tokens')
  if not isinstance(row,dict) or any(k not in row for k in required):gaps.append('record missing required fields');continue
  nums=[row[k] for k in required[-3:]]
  if any(type(n)is not int or n<0 for n in nums):gaps.append('invalid token counts');continue
  key=(row['source_id'],row['event_id']);event={'source_id':key[0],'event_id':key[1],'provider':row['provider'],'model':row['model'],'input_tokens':nums[0],'cached_tokens':nums[1],'output_tokens':nums[2],'binding':deepcopy(bindings.get(f'{key[0]}:{key[1]}'))}
  if key in events and events[key]!=event:gaps.append('conflicting shared event');continue
  events[key]=event
 return {'version':adapter_version,'events':[events[k] for k in sorted(events)],'complete':not gaps,'gaps':gaps,'unbound':[f'{k[0]}:{k[1]}' for k,v in events.items() if v['binding'] is None]}

def usage_coverage(events:list[dict],usage:dict)->dict:
 ids={ (e.get('source_id'),e.get('event_id')) for e in events}; imported={(e.get('source_id'),e.get('event_id')) for e in usage.get('events',[])}
 matched=ids&imported
 return {'matched':len(matched),'total':len(ids),'coverage':len(matched)/len(ids) if ids else None,'missing':sorted(f'{a}:{b}' for a,b in ids-matched)}
