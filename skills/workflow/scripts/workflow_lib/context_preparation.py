"""Parent-only authority and scoped, deterministic context composition."""
from copy import deepcopy
from dataclasses import dataclass,field
import hashlib
from pathlib import Path
import re
import time
from .document_units import canonical,digest,document_path
from .store import WorkflowError
from .storage_access import read_current
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


def _grounding_files(data):
    pair=data.get('spec_pair')
    if not pair:return {}
    registered=data.get('repositories',{}).get(pair['repo_id'])
    if not registered:return {} # Preserve the ordinary live preflight error.
    repo=Path(registered['location']).resolve()
    return {str(repo/name):_file_hash(repo/name) if (repo/name).exists() or (repo/name).is_symlink() else None
        for name in ('docs/devflow-context.json','docs/devflow-ground-interview.json')}


def _assert_files_current(files):
    for path,wanted in files.items():
        if wanted is None:
            _require(not Path(path).exists() and not Path(path).is_symlink(),'A new governing input appeared after validation.','CONTEXT_SOURCE_CHANGED')
        else:_require(_file_hash(path)==wanted,'Context source changed after validation.','CONTEXT_SOURCE_CHANGED')


def _validated_governing_files(data):
    import base64
    from .governing_docs import canonical_document_bytes
    files={}
    for record in data.get('governing_input_receipt',{}).get('files',{}).values():
        source={'root':data['repositories'][record['repo_id']]['location'],'path':record['path']}
        path=document_path(source);expected=base64.b64decode(record['content_base64'],validate=True)
        try:current=path.read_bytes()
        except OSError:
            _require(False,'Governing input disappeared after live preflight.','CONTEXT_SOURCE_CHANGED')
        current_hash=hashlib.sha256(current).hexdigest()
        _require(canonical_document_bytes(current,baseline=expected)==expected and _file_hash(path)==current_hash,
            'Governing input changed after live preflight.','CONTEXT_SOURCE_CHANGED')
        files[str(path)]=current_hash
    return files


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


def _validate_envelope(data,run,envelope,item_ids,max_bytes):
    _require(isinstance(envelope,dict),'Context control envelope must be an object.')
    if set(envelope)<= {'run_id'}:
        _require(envelope.get('run_id',run['id'])==run['id'],'Context envelope belongs to another run.','CONTEXT_SCOPE_CHANGED')
        return
    if envelope.get('binding_id'):
        from .hosts import validate_binding
        from .host_completion import host_brief
        binding=validate_binding(data,envelope['binding_id'],envelope.get('revision'))
        expected=host_brief(data,binding)
    else:
        from .briefs import assemble_brief
        stage=run['plan'].get('stage',{'name':'implementation','required_slices':[]})
        expected=assemble_brief(run,run.get('context',{}),stage,item_ids,max_bytes)
    _require(set(envelope)<=set(expected) and all(value==expected[key] for key,value in envelope.items()),
        'Context control facts differ from authoritative run or host state.','CONTEXT_SCOPE_CHANGED')


def prepare_context(root:Path,run:dict,envelope:dict,item_ids:list[str],*,stage:str,state:dict|None=None,
                    max_bytes:int=20000,representation:str='markdown',output_mode:str='full')->PreparedContext:
    started=time.monotonic();root=Path(root).resolve()
    borrowed_read_ms=state.get('_context_read_ms',0) if state is not None else 0
    state=read_current(root,run_id=run['id'],binding_id=envelope.get('binding_id')) if state is None else state
    grounding_files=_grounding_files(state['data'])
    checked=preflight_inputs(root,state,'context-preparation',run['id']);state=checked['state'];data=state['data']
    _assert_files_current(grounding_files)
    validated_files=_validated_governing_files(data)
    actual=data.get('runs',{}).get(run['id'])
    _require(isinstance(actual,dict),'Context preparation needs a current run.','RUN_NOT_FOUND');_accept_run(actual,run)
    _validate_envelope(data,run,envelope,item_ids,max_bytes)
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
    stage_settings=run['plan'].get('stage',{})
    optional_slices=[key for key in stage_settings.get('optional_slices',[]) if key not in stage_settings.get('required_slices',[])]
    selection={'optional_slices':optional_slices,'spec':selected_spec,'spec_hash':content_hash(spec),'item_ids':list(item_ids),'stage':stage,'governing':governing,
               'documents':[{'source_id':sid} for sid in policy['stage_reads'][stage]]}
    scope={'run_id':run['id'],'item_ids':list(item_ids),'stage':stage,'attempt_id':(run.get('active_attempt') or {}).get('token'),
        'attempt':deepcopy(run.get('active_attempt')),'binding_id':binding_id,'revision':envelope.get('revision'),'representation':representation,'output_mode':output_mode,'context_max_bytes':max_bytes}
    files={**validated_files,**grounding_files}
    for record in data.get('governing_input_receipt',{}).get('files',{}).values():
        rid=record['repo_id'];locations[rid]=str(Path(data['repositories'][rid]['location']).resolve())
    for source in sources.values():
        path=document_path(source)
        if str(path) not in files:files[str(path)]=_file_hash(path)
    policy_path=PACKAGE_ROOT/'definitions/documentation.json'
    files[str(policy_path)]=_file_hash(policy_path)
    _require(load_documentation_policy(PACKAGE_ROOT)==policy,'Documentation policy changed during preflight.','CONTEXT_SOURCE_CHANGED')
    pair=data.get('spec_pair')
    if pair:
        repo=Path(data['repositories'][pair['repo_id']]['location']).resolve();locations[pair['repo_id']]=str(repo)
        import json
        for key in ('json_path','markdown_path'):
            path=repo/pair[key];current_hash=_file_hash(path)
            if key=='markdown_path':_require(current_hash==pair['markdown_hash'],'Specification Markdown changed during preflight.','SPEC_APPROVAL_STALE')
            else:
                try:current_spec=json.loads(path.read_text(encoding='utf-8'))
                except (OSError,ValueError) as exc:raise WorkflowError('SPEC_APPROVAL_STALE','Specification changed during preflight.') from exc
                _require(current_spec==spec and content_hash(current_spec)==pair['content_hash'] and _file_hash(path)==current_hash,'Specification JSON changed during preflight.','SPEC_APPROVAL_STALE')
            files[str(path)]=current_hash
    tail=next((event for event in state['operations'].values() if event['sequence']==state['version']),None)
    bindings={'run_hash':digest(actual),'locations':locations,'spec_pair':deepcopy(pair),'approval_hash':digest(data.get('approval')),
        'governing_hash':digest(data.get('governing_input_receipt')),'files':files,'tail_hash':state.get('_storage',{}).get('head_hash') if state.get('_storage') else digest(tail) if tail else None}
    projected={'id':run['id'],'plan':{'work_items':deepcopy(chosen)}}
    scoped_envelope=deepcopy(envelope)
    # Reserve diagnostic shape before optional content spends the byte budget.
    scoped_envelope['preparation']={'preflight_ms':9999999999999,'worker_ms':9999999999999,'total_ms':9999999999999,'journal_version':state['version'],'binding_hash':'0'*64}
    payload={'root':str(root),'scope':scope,'run':projected,'envelope':scoped_envelope,'selection':selection,'sources':sources,'policy':policy}
    elapsed=borrowed_read_ms+max(int((time.monotonic()-started)*1000),checked['timing']['preflight_ms'])
    return PreparedContext(str(root),state['version'],scope,payload,bindings,elapsed,_identity(str(root),state['version'],scope,payload,bindings),state)


def assert_preparation_current(root:Path,prepared:PreparedContext,state:dict,*,phase='freshness')->None:
    try:_assert_preparation_current(root,prepared,state)
    except WorkflowError as exc:
        raise WorkflowError(exc.code,str(exc),{**exc.details,'phase':phase}) from exc


def _assert_preparation_current(root:Path,prepared:PreparedContext,state:dict)->None:
    _require(isinstance(prepared,PreparedContext) and str(Path(root).resolve())==prepared.root,'Prepared context belongs to another root.')
    _require(prepared.binding_hash==_identity(prepared.root,prepared.journal_version,prepared.scope,prepared.payload,prepared.source_bindings),'Prepared context content changed.')
    _require(state['version']==prepared.journal_version,'Journal advanced after preparation.')
    if state.get('_storage'):
        _require(state['_storage']['head_hash']==prepared.source_bindings['tail_hash'],'Journal head changed.')
    else:
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
    _assert_files_current(prepared.source_bindings['files'])


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
    result=_measure_view({k:v for k,v in result.items() if k!='task_view'},result['task_view'],prepared.scope['context_max_bytes'],result.get('budget',{}).get('optional_omitted',[]),optional_slices=prepared.payload['selection'].get('optional_slices',[]))
    _require(result['budget']['serialized_bytes']<=prepared.scope['context_max_bytes'],'Prepared context exceeds its byte budget.','CONTEXT_BUDGET_EXCEEDED')
    return result


def normalize_stage(stage):
    return {'build':'implementation','verification':'implementation','branch-review':'review','item-review':'review',
        'pr-review':'review','pr-rework':'implementation','scan':'ingest','debugging':'build-work','hardening':'build-work',
        'architecture':'project-context','security':'review-work','delivery':'workflow','pr-opening':'workflow','delivered':'workflow','discarded':'workflow'}.get(stage,stage)


def read_context_state(root:Path,*,run_id=None,operation_id=None,binding_id=None)->dict:
    """Internal caller timing, kept outside the public replayed state shape."""
    started=time.perf_counter();state=read_current(root,run_id=run_id,operations=(operation_id,),binding_id=binding_id,active_runs=run_id is None)
    return {**state,'_context_read_ms':max(0,int((time.perf_counter()-started)*1000))}


def commit_prepared_attempt(root:Path,prepared:PreparedContext,operation_id:str,event:dict)->dict:
    from .store import transact
    _require(isinstance(prepared,PreparedContext),'An internal prepared context is required.')
    request=event.get('payload',{});attempt=prepared.scope.get('attempt') or {}
    kind='run.reverification.started' if attempt.get('mode')=='reverify' else 'run.attempt.issued'
    _require(event.get('kind')==kind and request.get('run_id')==prepared.scope['run_id']
        and request.get('attempt')==attempt,'Attempt event differs from the prepared transition.')
    try:
        result=transact(root,prepared.journal_version,operation_id,event,
            precommit=lambda state:assert_preparation_current(root,prepared,state,phase='commit'))
    except WorkflowError as exc:
        if exc.code=='STALE_STATE':raise WorkflowError('CONTEXT_PREPARATION_STALE','Journal advanced after context preparation; retry with current inputs.',{'phase':'commit','action':'Rebuild current context before retrying.'}) from exc
        raise
    _require(result['event']['kind']==kind and result['event']['payload'].get('run_id')==prepared.scope['run_id'],
        'Operation ID belongs to another transition.','OPERATION_CONFLICT')
    return result
