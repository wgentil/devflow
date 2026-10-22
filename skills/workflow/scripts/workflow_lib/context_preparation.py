"""Parent-only authority and scoped, deterministic context composition."""
from copy import deepcopy
from dataclasses import dataclass,field
import hashlib
from pathlib import Path
import re
import time
from .document_units import canonical,digest,document_path
from .store import WorkflowError,read_state
from .repo_input_gate import preflight_inputs


def _require(ok,message,code='CONTEXT_PREPARATION_STALE'):
    if not ok:raise WorkflowError(code,message,{'phase':'preflight','action':'Retry preparation from current authoritative inputs.'})


def _file_hash(path):
    path=Path(path)
    _require(not any(p.is_symlink() for p in (path,*path.parents)),'A context source became a symlink.','CONTEXT_SOURCE_CHANGED')
    try:
        sha=hashlib.sha256()
        with path.open('rb') as stream:
            while chunk:=stream.read(65536):sha.update(chunk)
        return sha.hexdigest()
    except OSError as exc:raise WorkflowError('CONTEXT_SOURCE_CHANGED','A context source is missing or unreadable.') from exc


@dataclass(frozen=True)
class PreparedContext:
    root:str
    journal_version:int
    scope:dict
    payload:dict
    source_bindings:dict
    preflight_ms:int
    binding_hash:str
    _state:dict=field(repr=False,compare=False)


def _identity(root,version,scope,payload,sources):
    return digest({'root':root,'journal_version':version,'scope':scope,'payload':payload,'source_bindings':sources})


def _accept_run(actual,proposed):
    if actual==proposed:return
    from .runs import issue_attempt
    from .reverification import begin_reverification
    attempt=proposed.get('active_attempt') or {}
    _require(isinstance(attempt.get('token'),str) and re.fullmatch('[0-9a-f]{48}',attempt['token']), 'Invalid proposed attempt.')
    expected=(begin_reverification if attempt.get('mode')=='reverify' else issue_attempt)(actual,attempt.get('item_id'))
    expected['active_attempt']['token']=attempt['token']
    expected['items'][attempt['item_id']]['attempts'][-1]['token']=attempt['token']
    _require(expected==proposed,'Proposed run differs from the authorized attempt transition.')


def prepare_context(root:Path,run:dict,envelope:dict,item_ids:list[str],*,stage:str,state:dict|None=None,
                    max_bytes:int=20000,representation:str='markdown',output_mode:str='full')->PreparedContext:
    started=time.monotonic();root=Path(root).resolve()
    state=read_state(root) if state is None else state
    checked=preflight_inputs(root,state,'context-preparation',run['id']);state=checked['state'];data=state['data']
    actual=data.get('runs',{}).get(run['id'])
    _require(isinstance(actual,dict),'Context preparation needs a current run.','RUN_NOT_FOUND');_accept_run(actual,run)
    binding_id=envelope.get('binding_id')
    if binding_id:
        from .hosts import validate_binding
        binding=validate_binding(data,binding_id,envelope.get('revision'))
        _require(binding['run_id']==run['id'],'Host binding belongs to another run.','CONTEXT_SCOPE_CHANGED')
    from .specs import content_hash
    from .task_views import governing_selections,PACKAGE_ROOT
    from .documentation import load_documentation_policy
    spec=data['spec'];_require(run.get('plan',{}).get('spec_hash')==content_hash(spec),'Task plan uses an older specification.','PLAN_STALE')
    policy=load_documentation_policy(PACKAGE_ROOT)
    stage=normalize_stage(stage)
    _require(stage in policy['stage_reads'],'Stage has no declared documentation route.','CONTEXT_STAGE_UNAVAILABLE')
    items={i['id']:i for i in run['plan']['work_items']}
    _require(all(i in items for i in item_ids),'Selected task is missing.','CONTEXT_TASK_MISSING')
    chosen=[items[i] for i in item_ids];repo_ids={i.get('repo_id') for i in chosen if i.get('repo_id')}
    if not chosen:repo_ids=set(run.get('repositories',{}))
    locations={}
    for rid in repo_ids:
        current=data.get('repositories',{}).get(rid,{}).get('location');original=actual.get('repositories',{}).get(rid,{}).get('location')
        _require(current and original and Path(current).resolve()==Path(original).resolve(),'Repository ownership changed.','CONTEXT_SCOPE_CHANGED')
        locations[rid]=str(Path(current).resolve())
    governing,sources=governing_selections(data.get('governing_input_receipt',{}),data.get('repositories',{}))
    sources.update({sid:{'root':str(PACKAGE_ROOT),'path':value['path']} for sid,value in policy['sources'].items()})
    required={rid for item in chosen for rid in item.get('requirement_ids',[])} if chosen else {r['id'] for r in spec['requirements']}
    selected_spec={**deepcopy(spec),'requirements':[deepcopy(r) for r in spec['requirements'] if r['id'] in required]}
    selection={'spec':selected_spec,'spec_hash':content_hash(spec),'item_ids':list(item_ids),'stage':stage,'governing':governing,
               'documents':[{'source_id':sid} for sid in policy['stage_reads'][stage]]}
    scope={'run_id':run['id'],'item_ids':list(item_ids),'stage':stage,'attempt_id':(run.get('active_attempt') or {}).get('token'),
        'binding_id':binding_id,'revision':envelope.get('revision'),'representation':representation,'output_mode':output_mode,'context_max_bytes':max_bytes}
    files={}
    for source in sources.values():
        path=document_path(source);files[str(path)]=_file_hash(path)
    pair=data.get('spec_pair')
    if pair:
        repo=Path(data['repositories'][pair['repo_id']]['location']).resolve();locations[pair['repo_id']]=str(repo)
        for key in ('json_path','markdown_path'):
            path=repo/pair[key];files[str(path)]=_file_hash(path)
        for name in ('docs/devflow-context.json','docs/devflow-ground-interview.json'):
            path=repo/name
            if path.exists():files[str(path)]=_file_hash(path)
    tail=next((event for event in state['operations'].values() if event['sequence']==state['version']),None)
    bindings={'run_hash':digest(actual),'locations':locations,'spec_pair':deepcopy(pair),'approval_hash':digest(data.get('approval')),
        'governing_hash':digest(data.get('governing_input_receipt')),'files':files,'tail_hash':digest(tail) if tail else None}
    projected={'id':run['id'],'plan':{'work_items':deepcopy(chosen)}}
    scoped_envelope=deepcopy(envelope)
    # Reserve diagnostic shape before optional content spends the byte budget.
    scoped_envelope['preparation']={'preflight_ms':9999999999999,'worker_ms':9999999999999,'total_ms':9999999999999,'journal_version':state['version'],'binding_hash':'0'*64}
    payload={'root':str(root),'scope':scope,'run':projected,'envelope':scoped_envelope,'selection':selection,'sources':sources,'policy':policy}
    elapsed=max(int((time.monotonic()-started)*1000),checked['timing']['preflight_ms'])
    return PreparedContext(str(root),state['version'],scope,payload,bindings,elapsed,_identity(str(root),state['version'],scope,payload,bindings),state)


def assert_preparation_current(root:Path,prepared:PreparedContext,state:dict)->None:
    _require(isinstance(prepared,PreparedContext) and str(Path(root).resolve())==prepared.root,'Prepared context belongs to another root.')
    _require(prepared.binding_hash==_identity(prepared.root,prepared.journal_version,prepared.scope,prepared.payload,prepared.source_bindings),'Prepared context content changed.')
    _require(state['version']==prepared.journal_version,'Journal advanced after preparation.')
    event_dir=Path(root)/'events';next_event=event_dir/f'{prepared.journal_version+1:08d}.json'
    _require(not next_event.exists() and not next_event.is_symlink(),'Journal advanced after preparation.')
    if prepared.journal_version:
        import json
        tail=event_dir/f'{prepared.journal_version:08d}.json'
        _require(not tail.is_symlink(),'Journal tail changed.')
        try:current=json.loads(tail.read_text(encoding='utf-8'))
        except (OSError,ValueError) as exc:raise WorkflowError('CONTEXT_PREPARATION_STALE','Journal tail unavailable; retry.') from exc
        _require(digest(current)==prepared.source_bindings['tail_hash'],'Journal tail changed.')
    data=state['data'];actual=data.get('runs',{}).get(prepared.scope['run_id'])
    _require(digest(actual)==prepared.source_bindings['run_hash'],'Run changed after preparation.')
    _require(data.get('spec_pair')==prepared.source_bindings['spec_pair'] and digest(data.get('approval'))==prepared.source_bindings['approval_hash']
        and digest(data.get('governing_input_receipt'))==prepared.source_bindings['governing_hash'],'Approval inputs changed.')
    for rid,location in prepared.source_bindings['locations'].items():
        _require(str(Path(data.get('repositories',{}).get(rid,{}).get('location','')).resolve())==location,'Repository ownership changed.','CONTEXT_SCOPE_CHANGED')
    if prepared.scope.get('binding_id'):
        from .hosts import validate_binding
        binding=validate_binding(data,prepared.scope['binding_id'],prepared.scope['revision'])
        _require(binding['run_id']==prepared.scope['run_id'],'Host scope changed.','CONTEXT_SCOPE_CHANGED')
    for path,wanted in prepared.source_bindings['files'].items():
        _require(_file_hash(path)==wanted,'Context source changed after preparation.','CONTEXT_SOURCE_CHANGED')


def compose_prepared(prepared_payload:dict)->dict:
    from .task_views import build_task_view
    p=prepared_payload;scope=p['scope']
    return build_task_view(p['run'],p['envelope'],p['selection'],p['sources'],p['policy'],root=Path(p['root']),
        max_bytes=scope['context_max_bytes'],representation=scope['representation'],output_mode=scope['output_mode'])


def finish_prepared(prepared,result,worker_ms=0):
    from .task_views import _measure_view
    result=deepcopy(result)
    result['preparation']={'preflight_ms':prepared.preflight_ms,'worker_ms':worker_ms,'total_ms':prepared.preflight_ms+worker_ms,
        'journal_version':prepared.journal_version,'binding_hash':prepared.binding_hash}
    result=_measure_view({k:v for k,v in result.items() if k!='task_view'},result['task_view'],prepared.scope['context_max_bytes'],result.get('budget',{}).get('optional_omitted',[]))
    _require(result['budget']['serialized_bytes']<=prepared.scope['context_max_bytes'],'Prepared context exceeds its byte budget.','CONTEXT_BUDGET_EXCEEDED')
    return result


def normalize_stage(stage):
    return {'build':'implementation','verification':'implementation','branch-review':'review','item-review':'review',
        'pr-review':'review','pr-rework':'implementation','scan':'ingest','debugging':'build-work','hardening':'build-work',
        'architecture':'project-context','security':'review-work','delivery':'workflow','pr-opening':'workflow','delivered':'workflow','discarded':'workflow'}.get(stage,stage)
