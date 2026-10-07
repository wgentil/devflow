"""Read-only import of the locally documented DevConsole ledger schema."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
REQUIRED={'run_id','stages','rulings','parked_findings','artifacts','artifact_paths','attempts','active_attempts','work_items','enabled_optional_stages','target_increment','context_decisions'}
def import_legacy(source:Path,schema_version:int)->dict:
 if schema_version!=1:raise ValueError('unsupported legacy schema version')
 path=Path(source).expanduser().resolve(); raw=path.read_bytes(); data=json.loads(raw)
 if not isinstance(data,dict) or not REQUIRED.issubset(data):raise ValueError('unsupported legacy ledger shape')
 return {'schema_version':1,'legacy':True,'source_path':str(path),'source_hash':hashlib.sha256(raw).hexdigest(),'source_run_id':data['run_id'],'data':data,'unsupported_features':['legacy evidence is not current verification'],'gaps':[]}
def compare_parity(reference:dict,replacement:dict)->dict:
 missing=sorted(k for k,v in reference.items() if replacement.get(k)!=v)
 extra=sorted(set(replacement)-set(reference))
 return {'matches':not missing and not extra,'missing_or_different':missing,'additional':extra,'reference_count':len(reference),'replacement_count':len(replacement)}
