"""Conservative, content-bound collection of proven unreachable immutable files."""
from collections import deque
import hashlib
import gzip
import json
from pathlib import Path
import tempfile
from . import sqlite_store as sql
from .storage_objects import (read_object,stream_object,_load_manifest,_reference,
    _manifest_path,_chunk_path,_read_file,MAX_MANIFEST_BYTES,CHUNK_BYTES,MAX_STORED_CHUNK)
from .storage_format import confined_path,detect_layout
from .storage_backups import source_files,file_hash
from .stored_records import digest,MAX_RECORD_BYTES
from .storage_maintenance import _snapshot,_pins,_blockers,verify_store
from .storage_audit import perform,read_record,write_record,operation_key,paths
from .store import WorkflowError,_exclusive
from .platform_lock import sync_directory

PHYSICAL_RECORD_KINDS=frozenset(('projection-json-record','event-json-record','run-history-record'))
ADVISORY=frozenset(('offload.jsonl','.offload.lock','context-metrics.jsonl','.context-metrics.lock'))

def planned_files(root):
    result=[]
    for relative,path in source_files(root):
        if relative in ADVISORY or relative.startswith(('maintenance-receipts/pending/','maintenance-receipts/progress/')):continue
        stat=path.stat();result.append({'path':relative,'size_bytes':stat.st_size,'sha256':file_hash(path),
            'device':stat.st_dev,'inode':stat.st_ino})
    return result

def _tree_refs(node):
    if isinstance(node,list):
        for value in node:yield from _tree_refs(value)
    elif isinstance(node,dict):
        if set(node)=={'map'} and isinstance(node['map'],dict):
            for value in node['map'].values():yield from _tree_refs(value)
        elif set(node)=={'object'}:
            record=node['object']
            if record.get('record_kind') not in {'review-package','source-field'} or record.get('record_version') not in {1,2}:
                raise WorkflowError('GC_GRAPH_INVALID','Unsupported typed reference in retained history.')
            yield record['reference']
        else:raise WorkflowError('GC_GRAPH_INVALID','Malformed physical tree in retained history.')

def _cell_refs(codec,payload):
    value=json.loads(payload)
    if codec in {'json','space'}:return
    if codec in {'object','record-object','run-record-object','event-archive'}:yield value
    elif codec in {'record','run-record'}:yield from _tree_refs(value['node'])
    elif codec in {'archive','archive2'}:yield value['reference']
    else:raise WorkflowError('GC_GRAPH_INVALID','Unsupported retained storage codec: '+str(codec))

def _database_refs(conn):
    for codec,payload in conn.execute('SELECT codec,payload FROM entities UNION ALL SELECT codec,payload FROM events UNION ALL SELECT codec,payload FROM run_views'):
        yield from _cell_refs(codec,payload)
    for table in ('raw_events','event_segments','checkpoints'):
        for reference, in conn.execute('SELECT reference FROM '+table):yield json.loads(reference)

def _possible_refs(value):
    if isinstance(value,dict):
        if {'object_id','manifest_sha256','size_bytes','kind','schema_version'}<=set(value):yield value
        else:
            for item in value.values():yield from _possible_refs(item)
    elif isinstance(value,list):
        for item in value:yield from _possible_refs(item)

def _mark(root):
    pending=deque();marked=set();chunks=set();manifest_chunks={}
    with sql.connection(root) as conn:
        pending.extend(_database_refs(conn));identity={key:sql._meta(conn,key) for key in ('root_id','layout_id')};head=sql._meta(conn,'head')
    # Published contexts/checkpoint chains and durable physical receipts remain
    # roots even when an advisory retrieval index has forgotten their locations.
    for directory in ('context-artifacts','context-checkpoints','context-preparations','maintenance-receipts'):
        path=confined_path(root,directory)
        if not path.exists():continue
        for file in path.rglob('*.json'):
            confined_path(root,file.relative_to(root).as_posix())
            if directory=='maintenance-receipts':value=read_record(file)
            else:
                with file.open('rb') as stream:raw=stream.read(32*1024*1024+1)
                if len(raw)>32*1024*1024:raise WorkflowError('GC_GRAPH_INVALID','Retained context exceeds its read budget.')
                value=json.loads(raw)
            pending.extend(_possible_refs(value))
    while pending:
        ref=pending.popleft();object_id=ref.get('object_id')
        if object_id in marked:
            _load_manifest(root,ref);continue # Conflicting locators must fail, too.
        manifest=_load_manifest(root,ref);marked.add(object_id)
        paths={_chunk_path(root,part['encoding'],part['sha256']).relative_to(root).as_posix() for part in manifest['chunks']}
        chunks.update(paths);manifest_chunks[object_id]=paths
        kind=ref['kind']
        if kind=='sqlite-checkpoint':
            # Read a bounded private temporary copy outside the control root.
            # Dry-run never creates authority, projections or archives.
            with tempfile.TemporaryDirectory(prefix='devflow-gc-checkpoint-') as temporary:
                path=Path(temporary)/'checkpoint.sqlite3'
                with path.open('wb') as output:
                    for chunk in stream_object(root,ref):output.write(chunk)
                conn=sql._sqlite().connect(path.as_uri()+'?mode=ro',uri=True)
                try:
                    if (conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok'
                            or conn.execute('PRAGMA foreign_key_check').fetchone()
                            or conn.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()!=sql._expected_catalog()
                            or any(sql._meta(conn,key)!=wanted for key,wanted in identity.items())
                            or not 0<=sql._meta(conn,'head')<=head):
                        raise WorkflowError('GC_GRAPH_INVALID','Retained checkpoint database is invalid or belongs to another root.')
                    pending.extend(_database_refs(conn))
                finally:conn.close()
            continue
        if kind=='source-field':
            for _ in stream_object(root,ref):pass
            continue
        value=json.loads(read_object(root,ref,max_bytes=MAX_RECORD_BYTES))
        if kind=='review-package':pending.extend(_tree_refs(value))
        elif kind=='terminal-run':
            if value.get('record_version')==1:pending.extend(_tree_refs(value['node']))
            elif value.get('archive_version')==1 and value.get('codec')=='record':pending.extend(_tree_refs(value['body']['node']))
            elif value.get('archive_version')!=1 or value.get('codec')!='json':raise WorkflowError('GC_GRAPH_INVALID','Unsupported terminal object.')
        elif kind=='event-record':pending.extend(_cell_refs(value['codec'],value['payload']))
        elif kind=='event-segment':
            for entry in value['entries']:
                pending.append(entry['record'])
                if entry.get('raw'):pending.append(entry['raw'])
        elif kind=='control-checkpoint':pending.append(value['database']);pending.extend(value['segments'])
        elif kind=='working-run' or kind in PHYSICAL_RECORD_KINDS:
            if value.get('record_version')!=1:raise WorkflowError('GC_GRAPH_INVALID','Unsupported retained physical record.')
            pending.extend(_tree_refs(value['node']))
        elif kind not in {'projection-json','event-json','run-history','legacy-event-bytes'}:
            raise WorkflowError('GC_GRAPH_INVALID','Unknown retained object kind; preserve it before collection: '+kind)
    return marked,chunks,manifest_chunks

def _known_chunk(path,encoding,identity):
    try:
        with path.open('rb') as source:raw=source.read(MAX_STORED_CHUNK+1)
        if len(raw)>MAX_STORED_CHUNK:return False
        if encoding=='identity':value=raw
        else:
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(raw),mode='rb') as source:
                value=source.read(CHUNK_BYTES+1)
                if len(value)>CHUNK_BYTES or source.read(1):return False
        return 0<len(value)<=CHUNK_BYTES and hashlib.sha256(value).hexdigest()==identity
    except (OSError,EOFError,ValueError):return False


def gc_plan(root):
    root=Path(root).resolve()
    if detect_layout(root)['layout']!='v2':raise WorkflowError('GC_V2_REQUIRED','Explicitly compact/migrate this root before collecting immutable content.')
    with _exclusive(root):
        report=verify_store(root,full=True)
        if not report['valid']:raise WorkflowError('GC_GRAPH_INVALID','Complete history verification failed; no deletion is authorized.',{'verification':report})
        _,state,metadata=_snapshot(root);pins=_pins(root)
        marked,kept_chunks,manifest_chunks=_mark(root);candidates=[];unknown=[]
        files=planned_files(root);by_path={row['path']:row for row in files}
        for row in files:
            relative=row['path']
            if relative.startswith('objects/manifests/'):
                parts=Path(relative).parts
                if len(parts)!=4 or not relative.endswith('.json'):
                    unknown.append(relative);continue
                object_id=parts[2]+Path(parts[3]).stem
                raw=_read_file(confined_path(root,relative),MAX_MANIFEST_BYTES)
                try:manifest=json.loads(raw);ref=_reference(manifest,raw)
                except (ValueError,KeyError,TypeError) as exc:raise WorkflowError('GC_GRAPH_INVALID','Malformed manifest blocks collection.') from exc
                if ref['object_id']!=object_id:raise WorkflowError('GC_GRAPH_INVALID','Manifest path differs from its content identity.')
                manifest=_load_manifest(root,ref)
                object_chunks={_chunk_path(root,part['encoding'],part['sha256']).relative_to(root).as_posix() for part in manifest['chunks']}
                manifest_chunks[object_id]=object_chunks
                if object_id not in marked:
                    if ref['kind'] not in {'source-field','review-package','terminal-run','event-record','event-segment','control-checkpoint','sqlite-checkpoint','working-run','projection-json','event-json','run-history','legacy-event-bytes'} and ref['kind'] not in PHYSICAL_RECORD_KINDS:
                        # Unknown provenance cannot establish that nested refs are
                        # absent, so preserve the root instead of guessing.
                        raise WorkflowError('GC_GRAPH_INVALID','Unknown orphan object type blocks reachability proof: '+ref['kind'])
                    candidates.append({**row,'object_id':object_id,'reason':'unreferenced-manifest','chunks':sorted(object_chunks)})
            elif not relative.startswith(('objects/chunks/','store-v2/','events/','context-artifacts/','context-checkpoints/','context-preparations/','maintenance-receipts/')) and relative not in {'format.json','state.json'}:
                unknown.append(relative)
        for row in files:
            if row['path'].startswith('objects/chunks/') and row['path'] not in kept_chunks:
                # A regular file outside the exact immutable chunk naming scheme
                # is unknown, never a deletion candidate.
                parts=Path(row['path']).parts
                if (len(parts)==5 and parts[2] in {'gzip','identity'} and len(parts[3])==2
                        and len(Path(parts[4]).stem)==62 and row['path'].endswith('.blob')
                        and _known_chunk(confined_path(root,row['path']),parts[2],parts[3]+Path(parts[4]).stem)):
                    candidates.append({**row,'reason':'unreferenced-chunk'})
                else:unknown.append(row['path'])
        stat=root.stat();body={'gc_version':1,'root':str(root),'root_fs':[stat.st_dev,stat.st_ino],
            'head':state['version'],**metadata,'policy_hash':digest(state['data'].get('maintenance_policy',{})),
            'pins':pins,'blockers':_blockers(state['data'],pins),'files':files,'candidates':candidates,
            'candidate_bytes':sum(row['size_bytes'] for row in candidates),'retained_unknown':sorted(unknown),
            'telemetry_excluded':sorted(ADVISORY),'marked_objects':len(marked)}
        return {**body,'plan_hash':digest(body)}

def apply_gc(root,plan_hash,*,operation_id,actor_id):
    root=Path(root).resolve()
    return perform(root,'gc',{'plan_hash':plan_hash},operation_id,actor_id,
        lambda audit:_apply(root,plan_hash,operation_id,audit))

def _apply(root,plan_hash,operation_id,audit):
    path=confined_path(root,'maintenance-receipts/progress/'+operation_key(operation_id)+'.json')
    plan=gc_plan(root)
    if plan['blockers']:raise WorkflowError('MAINTENANCE_BLOCKED','; '.join(plan['blockers']))
    if path.exists():
        progress=read_record(path)
        if progress.get('plan_hash')!=plan_hash or progress.get('root_id')!=plan['root_id']:
            raise WorkflowError('OPERATION_CONFLICT','GC intent belongs to another plan or root.')
        # A newer writer can revive a formerly orphaned object. Never delete it
        # merely because an interrupted operation once listed it.
        allowed={row['path'] for row in plan['candidates']}
    else:
        if plan['plan_hash']!=plan_hash:raise WorkflowError('STALE_MAINTENANCE_PLAN','Root/head/pins or candidate files changed; inspect a new plan.')
        audit['plan']=plan;write_record(paths(root,operation_id)[1],audit)
        progress={'audit_version':1,'plan_hash':plan_hash,'root_id':plan['root_id'],'candidates':plan['candidates'],
            'deleted':[],'absent':[],'reclaimed_bytes':0}
        write_record(path,progress);allowed={row['path'] for row in plan['candidates']}
    deferred=[];protected=set();done=set(progress['deleted'])|set(progress['absent'])
    for row in progress['candidates']:
        relative=row['path']
        if relative in done:continue
        candidate=confined_path(root,relative)
        if not candidate.exists():
            progress['absent'].append(relative);write_record(path,progress);continue
        if relative not in allowed or relative in protected:
            deferred.append({'path':relative,'reason':'retained by current graph or deferred manifest'})
            protected.update(row.get('chunks',[]));continue
        stat=candidate.stat()
        if (stat.st_dev!=row['device'] or stat.st_ino!=row['inode'] or stat.st_size!=row['size_bytes'] or file_hash(candidate)!=row['sha256']):
            raise WorkflowError('STALE_MAINTENANCE_PLAN','A candidate changed after planning; preserve '+relative)
        try:candidate.unlink();sync_directory(candidate.parent)
        except OSError as exc:
            deferred.append({'path':relative,'reason':str(exc)});protected.update(row.get('chunks',[]));continue
        progress['deleted'].append(relative);progress['reclaimed_bytes']+=row['size_bytes'];write_record(path,progress)
    return {'completed':True,'plan_hash':plan_hash,'reclaimed_bytes':progress['reclaimed_bytes'],
        'deleted_files':len(progress['deleted']),'absent_after_interruption':len(progress['absent']),'deferred':deferred}
