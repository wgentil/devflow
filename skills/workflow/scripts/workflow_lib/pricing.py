"""Explicit, versioned API-equivalent usage pricing."""
from __future__ import annotations
import hashlib,json

def store_prices(state:dict,version:str,source:dict,rates:dict)->dict:
 if not version or not isinstance(rates,dict):raise ValueError('price version and rates are required')
 for model,rate in rates.items():
  if not isinstance(rate,dict) or any(type(rate.get(k)) not in (int,float) or rate[k]<0 for k in ('input','cached','output')):raise ValueError('all explicit nonnegative rates are required')
 record={'version':version,'source':source,'rates':rates}; record['id']=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest(); return record

def price_usage(usage:dict,prices:dict,coverage:dict)->dict:
 if type(coverage.get('coverage')) not in (int,float) or coverage['coverage']<.9:return {'eligible':False,'cost':None,'reason':'usage coverage below 90%'}
 total=0.0
 for e in usage.get('events',[]):
  rate=prices.get('rates',{}).get(f"{e.get('provider')}/{e.get('model')}")
  if not rate:return {'eligible':False,'cost':None,'reason':'missing model price'}
  total+=((e.get('input_tokens',0)-e.get('cached_tokens',0))*rate['input']+e.get('cached_tokens',0)*rate['cached']+e.get('output_tokens',0)*rate['output'])/1_000_000
 return {'eligible':True,'cost':total,'unit':'API-equivalent estimate','price_version':prices.get('version'),'price_id':prices.get('id')}
