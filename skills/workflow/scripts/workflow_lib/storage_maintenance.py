"""Explicit content-bound maintenance, verified staging and resumable activation."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from . import sqlite_store as sql
from .storage_format import DATABASE_FILE, FORMAT_FILE, INTENT_FILE, confined_path, detect_layout, LEGACY_GUARD
from .storage_objects import put_object, read_object, stream_object
from .stored_records import canonical, digest
from .storage_backups import (backup_locked, verify_backup, source_files, file_hash, _copy_file)
from .storage_journal import (archive_events, checkpoint, verify_checkpoint, read_raw_event)
from .run_archives import TERMINAL, store_working_detail, dependencies
from .store import WorkflowError, _exclusive, _atomic_json, _empty, _apply_event, _read_journal
from .platform_lock import sync_directory

GUARD = LEGACY_GUARD
FORMAT_KEYS = ('storage_format', 'database_schema', 'root_id', 'layout_id', 'database')
MAX_METADATA_BYTES = 16 * 1024 * 1024


def _read_json(path):
    with Path(path).open('rb') as handle: raw = handle.read(MAX_METADATA_BYTES + 1)
    if len(raw) > MAX_METADATA_BYTES: raise WorkflowError('MAINTENANCE_METADATA_INVALID', 'Maintenance metadata exceeds its read budget.')
    try: return json.loads(raw)
    except (ValueError, TypeError) as exc: raise WorkflowError('MAINTENANCE_METADATA_INVALID', str(exc)) from exc


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise WorkflowError('INVALID_MAINTENANCE_PLAN', 'An exact content-bound plan hash is required.')
    return value


def _snapshot(root):
    layout = detect_layout(root)
    if layout['layout'] == 'incomplete':
        raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED', 'Resume the durable maintenance intent before planning work.')
    if layout['layout'] == 'v2':
        with sql.connection(root) as conn:
            data = {row[0]: sql._load_space(conn, root, (row[0],)) for row in conn.execute('SELECT name FROM spaces WHERE parent IS NULL ORDER BY position')}
            return layout, {'version': sql._meta(conn,'head'), 'data': data}, {
                key: sql._meta(conn,key) for key in ('generation','head_hash','root_id','layout_id')}
    state, _ = _read_journal(root)
    last = next(reversed(state['operations'].values()), None)
    return layout, state, {'generation': 0, 'head_hash': digest(last) if last else None, 'root_id': None, 'layout_id': None}


def _pins(root):
    path = confined_path(root, 'pins')
    if not path.exists(): return []
    result = []
    for file in sorted(path.rglob('*')):
        relative = file.relative_to(root).as_posix(); confined_path(root,relative)
        if file.is_file(): result.append({'path':relative,'size_bytes':file.stat().st_size,'sha256':file_hash(file)})
    return result


def _blockers(data, pins):
    blockers = []
    for key, run in data.get('runs', {}).items():
        active = bool(run.get('active_attempt'))
        for name in ('native_invocations', 'hardening_attempts', 'migration_pilot_attempts'):
            active |= any(row.get('status') == 'running' for row in run.get(name, {}).values())
        active |= any(row.get('status') == 'claimed' for row in run.get('repair_cycles', []))
        active |= run.get('pr_open', {}).get('status') in {'pending','uncertain'} if isinstance(run.get('pr_open'),dict) else False
        active |= any(row.get('status') == 'applying' for row in run.get('test_change_proposals', {}).values())
        if active: blockers.append('in-flight work: ' + key)
    if any(row.get('status') == 'dispatching' for row in data.get('outbox', {}).values()): blockers.append('outbox dispatch is in flight')
    if pins: blockers.append('prepared context or reader pins are present')
    return blockers


def compaction_plan(root):
    root = Path(root).resolve()
    layout, state, metadata = _snapshot(root)
    pins = _pins(root)
    files = []
    for relative, path in source_files(root):
        if relative in {'offload.jsonl','.offload.lock','context-metrics.jsonl','.context-metrics.lock'} or relative.startswith(('maintenance-receipts/pending/','maintenance-receipts/progress/')):continue
        stat = path.stat()
        files.append({'path':relative,'size_bytes':stat.st_size,'sha256':file_hash(path),
                      'device':stat.st_dev,'inode':stat.st_ino})
    size = sum(row['size_bytes'] for row in files)
    stat = root.stat() if root.exists() else None
    body = {'maintenance_version':1,'root':str(root), 'root_fs': [stat.st_dev,stat.st_ino] if stat else None,
        'layout':layout['layout'],'head':state['version'], **metadata,
        'policy_hash':digest(state['data'].get('maintenance_policy',{})), 'pins':pins,'files':files,
        'terminal_candidates': sorted(key for key,run in state['data'].get('runs',{}).items() if run.get('status') in TERMINAL),
        'telemetry_excluded':['offload.jsonl','.offload.lock','context-metrics.jsonl','.context-metrics.lock'],
        'blockers':_blockers(state['data'],pins),'source_bytes':size,'required_free_bytes':max(16*1024*1024,size*3)}
    if layout['layout'] == 'uninitialized': body['blockers'].append('initialize a project before maintenance')
    return {**body,'plan_hash':digest(body)}


def _write_intent(root, intent):
    _atomic_json(confined_path(root,INTENT_FILE,create_parents=True),intent)


def _phase(root, intent, phase, **fields):
    intent.update(fields); intent['phase'] = phase; _write_intent(root,intent)


def _receipt_path(root, plan_hash):
    return confined_path(root,'maintenance/receipts/'+_hash(plan_hash)+'.json',create_parents=True)


def _read_receipt(root, plan_hash):
    # Read-only lookup must not create the receipts directory.
    path = confined_path(root,'maintenance/receipts/'+_hash(plan_hash)+'.json')
    if not path.exists(): return None
    value = _read_json(path); body = value['body']
    if value.get('sha256') != digest(body) or body.get('plan_hash') != plan_hash or not body.get('completed'):
        raise WorkflowError('MAINTENANCE_RECEIPT_INVALID','Completed maintenance receipt is invalid.')
    layout = detect_layout(root)
    if layout.get('root_id') != body.get('root_id') or layout.get('layout_id') != body.get('layout_id'):
        raise WorkflowError('MAINTENANCE_RECEIPT_INVALID','Maintenance receipt belongs to a different selected authority.')
    return body


def _disk_check(root, required):
    if shutil.disk_usage(root).free < required:
        raise WorkflowError('INSUFFICIENT_STORAGE','Maintenance needs verified staging and backup headroom; originals were retained.')


def backup_control(root, output, *, resume=False):
    root = Path(root).resolve()
    with _exclusive(root):
        _,state,_=_snapshot(root)
        blockers=_blockers(state['data'],_pins(root))
        if blockers:raise WorkflowError('MAINTENANCE_BLOCKED','; '.join(blockers))
        _disk_check(root,max(16*1024*1024,sum(path.stat().st_size for _,path in source_files(root))*2))
        return backup_locked(root,output,resume=resume)


def _archive_runs(conn, root):
    rows = conn.execute('SELECT key,codec,payload,value_hash FROM entities WHERE space=? AND status IN (?,?)',
                        (sql._space(('runs',)),'delivered','discarded')).fetchall()
    for key,codec,payload,expected in rows:
        if codec in {'archive','archive2'}: continue
        run = sql._decode(root,codec,payload,expected,working=True)
        record = store_working_detail(root,run)
        conn.execute('UPDATE entities SET codec=?,payload=?,value_hash=? WHERE space=? AND key=?',
                     ('archive2',sql._json(record),record['physical_sha256'],sql._space(('runs',)),key))


def _commit_record(conn, plan, generation):
    receipt = {'plan_hash':plan['plan_hash'],'source_head':plan['head'],'generation':generation}
    conn.execute('INSERT INTO maintenance_commits VALUES(?,?,?,?)',
                 (plan['plan_hash'],plan['head'],generation,sql._json(receipt)))


def _stage_legacy(root, intent):
    plan = intent['plan']; backup = confined_path(root,intent['backup'])
    report = verify_backup(backup)
    if not report['valid']: raise WorkflowError('BACKUP_INVALID','Verified original backup is unavailable: '+str(report.get('errors')))
    source, _ = _read_journal(backup)
    if source['version'] != plan['head'] or (digest(next(reversed(source['operations'].values()))) if source['operations'] else None) != plan['head_hash']:
        raise WorkflowError('STALE_MAINTENANCE_SOURCE','Original backup differs from the approved source head.')
    stage = confined_path(root,intent['stage'],create_parents=True)
    sql.initialize_store(stage)
    with sql.connection(stage,write=True) as conn:
        prior = conn.execute('SELECT source_head FROM maintenance_commits WHERE plan_hash=?',(plan['plan_hash'],)).fetchone()
        if prior:
            if prior[0] != plan['head'] or sql._meta(conn,'head') != plan['head']:
                raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Staged authority has an unexpected committed tail.')
        else:
            if sql._meta(conn,'head') != 0: raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Staging contains unrelated history.')
            for key,value in source['data'].items(): sql._sync_space(conn,stage,(key,),value,complete=True)
            for event in source['operations'].values():
                codec,payload,event_hash = sql._encode(stage,event,'event-json')
                conn.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',
                    (event['sequence'],event['operation_id'],event['kind'],codec,payload,event_hash))
                name = f"{event['sequence']:08d}.json"
                raw = confined_path(backup,'events/'+name).read_bytes()
                ref = put_object(stage,'legacy-event-bytes',raw)
                conn.execute('INSERT INTO raw_events VALUES(?,?,?,?)',
                    (event['sequence'],name,sql._json(ref),hashlib.sha256(raw).hexdigest()))
            sql._refresh_dependency_witnesses(conn)
            sql._set_meta(conn,'head',source['version']); sql._set_meta(conn,'head_hash',plan['head_hash'])
            sql._set_meta(conn,'dependency_head',source['version']);sql._set_meta(conn,'generation',1)
            _archive_runs(conn,stage);archive_events(conn,stage);_commit_record(conn,plan,1)
    report = verify_store(stage,full=True)
    if not report['valid']: raise WorkflowError('MAINTENANCE_VERIFICATION_FAILED',str(report['errors']))
    layout = detect_layout(stage)
    _phase(root,intent,'database-committed',target_format={key:layout[key] for key in FORMAT_KEYS},target_generation=1)
    return stage


def _publish_objects(root, stage):
    for relative, source in source_files(stage):
        if not relative.startswith('objects/'): continue
        target = confined_path(root,relative,create_parents=True)
        if target.exists():
            if source.stat().st_size != target.stat().st_size or file_hash(source) != file_hash(target):
                raise WorkflowError('STORAGE_OBJECT_CORRUPT','Published object collision; originals were retained.')
        else:
            os.link(source,target);sync_directory(target.parent)


def _publish_database(root, stage):
    source = confined_path(stage,DATABASE_FILE)
    target = confined_path(root,DATABASE_FILE,create_parents=True)
    if target.exists():
        if file_hash(source) != file_hash(target):
            raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','An unselected database differs from verified staging; do not overwrite it.')
    else: _copy_file(source,target)


def _assert_legacy_source(root, intent):
    plan = intent['plan']
    stat = root.stat()
    if [stat.st_dev,stat.st_ino] != plan['root_fs']:
        raise WorkflowError('STALE_MAINTENANCE_SOURCE','Selected root filesystem identity changed; preserve it for explicit recovery.')
    expected = {row['path']:row for row in plan['files']}
    names = {p.name for p in confined_path(root,'events').glob('[0-9]*.json')}
    old_names = {Path(path).name for path in expected if path.startswith('events/') and Path(path).name[:1].isdigit()}
    if names != old_names:
        raise WorkflowError('STALE_MAINTENANCE_SOURCE','Legacy event tail changed after planning; no history was replaced.')
    for relative, row in expected.items():
        path = confined_path(root,relative)
        if relative == 'events/00000001.json' and path.exists():
            try:
                if _read_json(path) == GUARD: continue
            except WorkflowError: pass
        if not path.is_file() or path.stat().st_size != row['size_bytes'] or file_hash(path) != row['sha256']:
            raise WorkflowError('STALE_MAINTENANCE_SOURCE','A planned source file changed: '+relative)
    if _pins(root) != plan['pins']:
        raise WorkflowError('STALE_MAINTENANCE_SOURCE','Work pins changed; preserve originals and resolve the source before resume.')


def _validate_selected(root, intent):
    layout = detect_layout(root)
    target = intent['target_format']; plan = intent['plan']
    if any(layout.get(key) != target.get(key) for key in FORMAT_KEYS):
        raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Selected authority differs from this maintenance intent.')
    with sql.connection(root) as conn:
        row = conn.execute('SELECT source_head,generation FROM maintenance_commits WHERE plan_hash=?',(plan['plan_hash'],)).fetchone()
        if (row != (plan['head'],intent['target_generation']) or sql._meta(conn,'generation') != intent['target_generation']
                or sql._meta(conn,'head') < plan['head']):
            raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Do not replace a newer generation or discard a committed tail.')
        at_source = conn.execute('SELECT event_hash FROM events WHERE sequence=?',(plan['head'],)).fetchone()
        if (at_source[0] if at_source else None) != plan['head_hash']:
            raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Source history prefix differs from the selected authority.')
        if intent.get('checkpoint'): verify_checkpoint(root,intent['checkpoint'],conn)


def _finish(root, intent):
    _validate_selected(root,intent)
    report = verify_store(root,full=True)
    if not report['valid']: raise WorkflowError('MAINTENANCE_VERIFICATION_FAILED',str(report['errors']))
    _phase(root,intent,'cleanup')
    pending = []
    if intent['plan']['layout'] == 'legacy':
        for row in intent['plan']['files']:
            relative = row['path']
            if relative == 'events/00000001.json': continue
            if not (relative == 'state.json' or (relative.startswith('events/') and Path(relative).name[:1].isdigit())): continue
            path = confined_path(root,relative)
            if not path.exists(): continue
            if file_hash(path) != row['sha256']: raise WorkflowError('STALE_MAINTENANCE_SOURCE','Hot-file cleanup found changed content; preserved '+relative)
            try: path.unlink();sync_directory(path.parent)
            except PermissionError: pending.append(relative)
    if intent.get('stage'):
        stage = confined_path(root,intent['stage'])
        if stage.exists():
            try: shutil.rmtree(stage)
            except PermissionError: pending.append(intent['stage'])
    if pending:
        _phase(root,intent,'cleanup',cleanup_pending=pending)
        return {'completed':False,'activated':True,'cleanup_pending':pending,'plan_hash':intent['plan']['plan_hash']}
    with sql.connection(root) as conn:
        receipt = {'completed':True,'activated':True,'plan_hash':intent['plan']['plan_hash'],
            'source_head':intent['plan']['head'],'final_head':sql._meta(conn,'head'),
            'generation':sql._meta(conn,'generation'),'root_id':sql._meta(conn,'root_id'),
            'layout_id':sql._meta(conn,'layout_id'),'storage_format':2,'checkpoint':intent['checkpoint'],
            'backup':intent['backup'],'cleanup_pending':[]}
    _atomic_json(_receipt_path(root,receipt['plan_hash']),{'body':receipt,'sha256':digest(receipt)})
    confined_path(root,INTENT_FILE).unlink();sync_directory(root/'maintenance')
    return receipt


def _run_intent_locked(root, intent):
    plan = intent['plan']
    if plan['layout'] == 'legacy':
        if confined_path(root,FORMAT_FILE).exists(): return _finish(root,intent)
        _assert_legacy_source(root,intent)
        stage = _stage_legacy(root,intent)
        ref = checkpoint(stage,plan['plan_hash'])
        _publish_objects(root,stage)
        _phase(root,intent,'objects-synced',checkpoint=ref)
        _publish_database(root,stage)
        verify_checkpoint(root,ref)
        _phase(root,intent,'ready')
        _atomic_json(confined_path(root,'events/00000001.json',create_parents=True),GUARD)
        _phase(root,intent,'guard-installed')
        _atomic_json(confined_path(root,FORMAT_FILE),intent['target_format'])
        _phase(root,intent,'activated')
        return _finish(root,intent)
    with sql.connection(root,write=True) as conn:
        prior = conn.execute('SELECT generation FROM maintenance_commits WHERE plan_hash=?',(plan['plan_hash'],)).fetchone()
        if prior:
            generation = prior[0]
            if sql._meta(conn,'generation') != generation:
                raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','A newer generation must not be overwritten.')
        else:
            if sql._meta(conn,'head') != plan['head'] or sql._meta(conn,'generation') != plan['generation']:
                raise WorkflowError('STALE_MAINTENANCE_SOURCE','Selected history changed before compaction committed.')
            _archive_runs(conn,root);archive_events(conn,root)
            generation = plan['generation']+1
            sql._set_meta(conn,'generation',generation);_commit_record(conn,plan,generation)
        layout = detect_layout(root)
    _phase(root,intent,'database-committed',target_format={key:layout[key] for key in FORMAT_KEYS},target_generation=generation)
    ref = checkpoint(root,plan['plan_hash'])
    _phase(root,intent,'objects-synced',checkpoint=ref)
    _phase(root,intent,'ready');_phase(root,intent,'guard-installed');_phase(root,intent,'activated')
    return _finish(root,intent)


def apply_compaction(root, plan_hash):
    root = Path(root).resolve();_hash(plan_hash)
    with _exclusive(root):
        receipt = _read_receipt(root,plan_hash)
        if receipt is not None: return receipt
        if confined_path(root,INTENT_FILE).exists():
            raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Resume the existing intent; do not replace it.')
        plan = compaction_plan(root)
        if plan['plan_hash'] != plan_hash:
            raise WorkflowError('STALE_MAINTENANCE_PLAN','Root/head/policy/pins or source files changed; inspect a fresh dry-run plan.')
        if plan['blockers']: raise WorkflowError('MAINTENANCE_BLOCKED','; '.join(plan['blockers']))
        _disk_check(root,plan['required_free_bytes']);sql._sqlite()
        report = verify_store(root,full=True)
        if not report['valid']: raise WorkflowError('MAINTENANCE_VERIFICATION_FAILED',str(report['errors']))
        backup = 'backups/'+plan_hash
        backup_locked(root,confined_path(root,backup),resume=True)
        intent = {'intent_version':1,'kind':'compact','phase':'preparing','plan':plan,'backup':backup,
                  'stage':'maintenance/staging/'+plan_hash if plan['layout']=='legacy' else None,
                  'target_format':None,'target_generation':None,'checkpoint':None}
        _write_intent(root,intent)
        try: return _run_intent_locked(root,intent)
        except OSError as exc: raise WorkflowError('MAINTENANCE_IO_FAILED','Storage operation interrupted; originals and intent were retained: '+str(exc)) from exc


def resume_compaction(root):
    root = Path(root).resolve()
    with _exclusive(root):
        path = confined_path(root,INTENT_FILE)
        if not path.exists(): raise WorkflowError('NO_MAINTENANCE_INTENT','There is no incomplete maintenance intent to resume.')
        intent = _read_json(path)
        if not isinstance(intent, dict):
            raise WorkflowError('MAINTENANCE_METADATA_INVALID','Durable intent must be an object; preserve the root.')
        if intent.get('kind') == 'initialize': return _resume_initialization(root,intent)
        if intent.get('intent_version') != 1 or intent.get('kind') != 'compact':
            raise WorkflowError('MAINTENANCE_METADATA_INVALID','Unsupported durable maintenance intent.')
        required = {'plan','backup','stage','phase','target_format','target_generation','checkpoint'}
        if not required.issubset(intent) or not isinstance(intent['plan'],dict):
            raise WorkflowError('MAINTENANCE_METADATA_INVALID','Durable intent is incomplete; preserve the root.')
        plan = intent['plan']; body = {key:value for key,value in plan.items() if key!='plan_hash'}
        if (plan.get('maintenance_version') != 1 or plan.get('layout') not in {'legacy','v2'}
                or digest(body) != plan.get('plan_hash') or plan.get('root') != str(root)):
            raise WorkflowError('MAINTENANCE_METADATA_INVALID','Intent plan identity differs; preserve the root.')
        if intent.get('checkpoint'):
            verify_checkpoint(root,intent['checkpoint'])
        return _run_intent_locked(root,intent)


def _resume_initialization(root, intent):
    identity = intent.get('format',{})
    database = confined_path(root,DATABASE_FILE)
    sqlite = sql._sqlite();conn = sqlite.connect(database.as_uri()+'?mode=ro',uri=True)
    try:
        if (conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok'
                or any(sql._meta(conn,key)!=identity.get(key) for key in FORMAT_KEYS)
                or conn.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()!=sql._expected_catalog()):
            raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Incomplete initialization database cannot be safely activated.')
        if not confined_path(root,FORMAT_FILE).exists() and sql._meta(conn,'head')!=0:
            raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Unselected initialization contains unexpected history.')
    finally: conn.close()
    if not confined_path(root,FORMAT_FILE).exists():
        _atomic_json(confined_path(root,'events/00000001.json',create_parents=True),GUARD)
        _atomic_json(confined_path(root,FORMAT_FILE),identity)
    elif any(detect_layout(root).get(key)!=identity.get(key) for key in FORMAT_KEYS):
        raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Initialization intent differs from the selected authority.')
    confined_path(root,INTENT_FILE).unlink();sync_directory(root/'maintenance')
    return {'completed':True,'kind':'initialize','storage_format':2}


def verify_store(root, *, full=False):
    root = Path(root).resolve()
    try:
        layout = detect_layout(root)
        if layout['layout'] in {'legacy','uninitialized'}:
            state,_ = _read_journal(root)
            if full:
                from .storage_audit import verify_receipts
                verify_receipts(root,logical_operations=state['operations'])
            return {'valid':True,'storage_format':layout.get('storage_format'),'head':state['version'],'full':full}
        if layout['layout'] != 'v2': raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Resume incomplete initialization/migration before full verification.')
        with sql.connection(root) as conn:
            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or conn.execute('PRAGMA foreign_key_check').fetchone():
                raise WorkflowError('CORRUPT_STORAGE','SQLite integrity or foreign-key verification failed.')
            head = sql._meta(conn,'head')
            if full:
                from .storage_audit import verify_receipts
                verify_receipts(root,conn)
                replay = _empty(); seen = set()
                for expected,row in enumerate(conn.execute('SELECT sequence,operation_id,codec,payload,event_hash FROM events ORDER BY sequence'),1):
                    sequence,op,codec,payload,event_hash = row
                    event = sql._decode(root,codec,payload,event_hash)
                    if (sequence != expected or event.get('sequence') != expected or event.get('operation_id')!=op
                            or event.get('schema_version')!=1 or op in seen):
                        raise WorkflowError('CORRUPT_STORAGE','Event continuity, schema or operation identity failed verification.')
                    seen.add(op);_apply_event(replay,event);replay['version']=sequence
                    raw = conn.execute('SELECT name,reference,raw_hash FROM raw_events WHERE sequence=?',(sequence,)).fetchone()
                    if raw:
                        data = read_object(root,json.loads(raw[1]),max_bytes=256*1024*1024)
                        if raw[0]!=f'{sequence:08d}.json' or hashlib.sha256(data).hexdigest()!=raw[2] or json.loads(data)!=event:
                            raise WorkflowError('INVALID_RAW_EVENT','Original raw event differs from logical history.')
                data = {row[0]:sql._load_space(conn,root,(row[0],)) for row in conn.execute('SELECT name FROM spaces WHERE parent IS NULL ORDER BY position')}
                if replay['version']!=head or replay['data']!=data:
                    raise WorkflowError('CORRUPT_STORAGE','Complete replay and current projection differ; no checkpoint was restored.')
                from .storage_access import history_projections
                expected_views = {}
                for key,run in data.get('runs',{}).items():
                    for view,value in history_projections(run).items():expected_views[(sql._space(('runs',)),key,view)] = value
                actual_views = {(space,key,view):sql._decode(root,codec,payload,checksum)
                    for space,key,view,codec,payload,checksum in conn.execute('SELECT * FROM run_views')}
                if expected_views != actual_views:raise WorkflowError('CORRUPT_STORAGE','Indexed reporting views differ from complete logical runs.')
                expected_documents = sorted((sql._space(('document_proposals',)),key,proposal.get('repo_id'),path,digest(record))
                    for key,proposal in data.get('document_proposals',{}).items() for path,record in proposal.get('files',{}).items())
                if expected_documents != sorted(conn.execute('SELECT * FROM document_files').fetchall()):
                    raise WorkflowError('CORRUPT_STORAGE','Governing approval lookup differs from authoritative proposal bodies.')
                expected_links = sorted((kind,source,sql._space(('runs',)),key,entity) for key,run in data.get('runs',{}).items() for kind,source,entity in dependencies(run))
                actual_links = sorted(conn.execute('SELECT kind,source,space,run_id,entity_key FROM dependencies').fetchall())
                if actual_links!=expected_links: raise WorkflowError('CORRUPT_DEPENDENCY_INDEX','Reverse dependencies differ from complete logical runs.')
                for kind,source in {(row[0],row[1]) for row in expected_links}: sql.select_dependents(conn,kind,source)
                covered_archives = set()
                for segment_id,first,last,reference in conn.execute('SELECT * FROM event_segments'):
                    ref = json.loads(reference); segment = json.loads(read_object(root,ref,max_bytes=256*1024*1024))
                    if ref['object_id']!=segment_id or segment.get('segment_version')!=1 or segment['first_sequence']!=first or segment['last_sequence']!=last or len(segment['entries'])!=last-first+1:
                        raise WorkflowError('INVALID_EVENT_ARCHIVE','Event segment boundaries differ from their catalog.')
                    for sequence,entry in enumerate(segment['entries'],first):
                        if sequence in covered_archives:
                            raise WorkflowError('INVALID_EVENT_ARCHIVE','Immutable event segments overlap.')
                        covered_archives.add(sequence)
                        row = conn.execute('SELECT operation_id,event_hash,payload,codec FROM events WHERE sequence=?',(sequence,)).fetchone()
                        if (not row or entry['sequence']!=sequence or entry['operation_id']!=row[0] or entry['event_hash']!=row[1]
                                or row[3]!='event-archive' or json.loads(row[2])!=entry['record']):
                            raise WorkflowError('INVALID_EVENT_ARCHIVE','Exact operation locator differs from its immutable segment.')
                archived_sequences = {row[0] for row in conn.execute("SELECT sequence FROM events WHERE codec='event-archive'")}
                if covered_archives != archived_sequences:
                    raise WorkflowError('INVALID_EVENT_ARCHIVE','Segment catalog omits an archived event locator.')
                for (reference,) in conn.execute('SELECT reference FROM checkpoints'): verify_checkpoint(root,json.loads(reference),conn)
            return {'valid':True,'storage_format':2,'head':head,'full':full}
    except (WorkflowError,OSError,ValueError,TypeError,KeyError) as exc:
        return {'valid':False,'errors':[str(exc)],'error_code':getattr(exc,'code','STORAGE_VERIFY_FAILED'),'full':full}


def apply_authorized_compaction(root,plan_hash,*,operation_id,actor_id):
    from .storage_audit import perform,paths,write_record
    root=Path(root).resolve()
    def apply(audit):
        intent_path=confined_path(root,INTENT_FILE)
        if intent_path.exists():
            intent=_read_json(intent_path)
            if intent.get('plan',{}).get('plan_hash')!=plan_hash:raise WorkflowError('OPERATION_CONFLICT','Resume the original maintenance request.')
            return resume_compaction(root)
        if 'plan' not in audit:
            plan=compaction_plan(root)
            if plan['plan_hash']!=plan_hash:raise WorkflowError('STALE_MAINTENANCE_PLAN','Root/head/policy/pins or source files changed.')
            audit['plan']=plan;write_record(paths(root,operation_id)[1],audit)
        return apply_compaction(root,plan_hash)
    return perform(root,'compact',{'plan_hash':plan_hash},operation_id,actor_id,apply)


def post_terminal(root,event,*,committed_data=None):
    """Opt-in physical work after success; never migration, GC or a new outcome."""
    from .storage_access import read_current
    from .utf8_io import warn_utf8
    root=Path(root).resolve()
    try:
        if detect_layout(root)['layout']!='v2':
            if (committed_data or {}).get('maintenance_policy',{}).get('post_terminal_compaction') is True:
                warn_utf8('devflow: post-terminal compaction skipped: legacy conversion requires explicit manual maintenance.')
            return
        data=read_current(root,global_keys=('maintenance_policy','maintenance_policy_authorization'))['data']
        if data.get('maintenance_policy',{}).get('post_terminal_compaction') is not True:return
        plan=compaction_plan(root)
        if plan['blockers']:
            warn_utf8('devflow: post-terminal compaction skipped: '+'; '.join(plan['blockers']))
            return
        actor=data.get('maintenance_policy_authorization',{}).get('actor_id') or 'system:post-terminal'
        apply_authorized_compaction(root,plan['plan_hash'],operation_id=event['operation_id']+':post-terminal',actor_id=actor)
    except Exception as exc:
        warn_utf8('devflow: post-terminal compaction deferred; terminal result remains valid: '+str(exc)[:400])
