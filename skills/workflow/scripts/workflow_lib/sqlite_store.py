"""Indexed transactional authority; full materialization is explicit, never a lazy dict."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import uuid
from functools import lru_cache

from .storage_format import (DATABASE_FILE, DATABASE_SCHEMA, FORMAT_FILE, INTENT_FILE,
                             confined_path, detect_layout, LEGACY_GUARD)
from .storage_objects import put_object, read_object
from .storage_scopes import ReadScope, EntityQuery, scope_for_event
from .store import WorkflowError

from . import storage_catalog

INLINE_BYTES = 65536
SCHEMA = '''
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE spaces(path TEXT PRIMARY KEY, parent TEXT REFERENCES spaces(path) ON DELETE CASCADE,
                    name TEXT NOT NULL, shape TEXT NOT NULL, position INTEGER NOT NULL);
CREATE TABLE entities(space TEXT REFERENCES spaces(path) ON DELETE CASCADE, key TEXT,
    position INTEGER NOT NULL, codec TEXT NOT NULL, payload TEXT NOT NULL, value_hash TEXT NOT NULL,
    run_id TEXT, status TEXT, host TEXT, session_id TEXT, package_hash TEXT, record_id TEXT,
    PRIMARY KEY(space,key));
CREATE INDEX entities_run ON entities(space,run_id);
CREATE INDEX entities_identity ON entities(space,record_id);
CREATE INDEX entities_status ON entities(space,status);
CREATE INDEX entities_session ON entities(space,host,session_id,status);
CREATE TABLE run_views(rspace TEXT, run_id TEXT, kind TEXT, codec TEXT NOT NULL, payload TEXT NOT NULL,
    value_hash TEXT NOT NULL, PRIMARY KEY(kind,run_id),
    FOREIGN KEY(rspace,run_id) REFERENCES entities(space,key) ON DELETE CASCADE);
CREATE TABLE document_files(space TEXT, proposal_id TEXT, repo_id TEXT, path TEXT, record_hash TEXT,
    PRIMARY KEY(proposal_id,path),
    FOREIGN KEY(space,proposal_id) REFERENCES entities(space,key) ON DELETE CASCADE);
CREATE INDEX document_file_lookup ON document_files(repo_id,path,record_hash);
CREATE TABLE events(sequence INTEGER PRIMARY KEY, operation_id TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL, codec TEXT NOT NULL, payload TEXT NOT NULL, event_hash TEXT NOT NULL);
CREATE TABLE dependencies(kind TEXT, source TEXT, space TEXT, run_id TEXT, entity_key TEXT,
    PRIMARY KEY(kind,source,run_id,entity_key),
    FOREIGN KEY(space,run_id) REFERENCES entities(space,key) ON DELETE CASCADE);
CREATE INDEX dependency_source ON dependencies(kind,source);
CREATE INDEX dependency_run ON dependencies(space,run_id);
CREATE TABLE dependency_sources(kind TEXT, source TEXT, checksum TEXT NOT NULL, row_count INTEGER NOT NULL,
    PRIMARY KEY(kind,source));
CREATE TABLE dependency_dirty(kind TEXT, source TEXT, PRIMARY KEY(kind,source));
CREATE TRIGGER dependency_insert AFTER INSERT ON dependencies BEGIN
    INSERT OR IGNORE INTO dependency_dirty VALUES(NEW.kind,NEW.source); END;
CREATE TRIGGER dependency_delete AFTER DELETE ON dependencies BEGIN
    INSERT OR IGNORE INTO dependency_dirty VALUES(OLD.kind,OLD.source); END;
CREATE TABLE raw_events(sequence INTEGER PRIMARY KEY REFERENCES events(sequence), name TEXT NOT NULL,
    reference TEXT NOT NULL, raw_hash TEXT NOT NULL);
CREATE TABLE event_segments(segment_id TEXT PRIMARY KEY, first_sequence INTEGER NOT NULL,
    last_sequence INTEGER NOT NULL, reference TEXT NOT NULL);
CREATE TABLE checkpoints(checkpoint_id TEXT PRIMARY KEY, head INTEGER NOT NULL, generation INTEGER NOT NULL,
    reference TEXT NOT NULL);
CREATE TABLE maintenance_commits(plan_hash TEXT PRIMARY KEY, source_head INTEGER NOT NULL,
    generation INTEGER NOT NULL, receipt TEXT NOT NULL);

'''
SCHEMA += storage_catalog.SCHEMA


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _sha(raw): return hashlib.sha256(raw).hexdigest()
def _space(path): return _json(list(path))


def _sqlite():
    try:
        import sqlite3
        return sqlite3
    except ImportError as exc:
        raise WorkflowError('SQLITE_UNAVAILABLE', 'Storage v2 requires Python with standard-library sqlite3 support; preserve this root.') from exc


def _meta(conn, key):
    row = conn.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
    if row is None: raise WorkflowError('CORRUPT_STORAGE', 'Required database identity or head metadata is missing.')
    try: return json.loads(row[0])
    except (ValueError, TypeError) as exc:
        raise WorkflowError('CORRUPT_STORAGE', 'Database identity/head metadata is malformed; preserve and verify this root.') from exc


def _set_meta(conn, key, value):
    conn.execute('INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, _json(value)))


def _next_position(conn):
    value = _meta(conn, 'position') + 1
    _set_meta(conn, 'position', value)
    return value


def initialize_store(root: Path,*,operation_id=None):
    from .store import _exclusive, _atomic_json
    from .platform_lock import sync_directory
    root = Path(root).resolve()
    with _exclusive(root):
        layout = detect_layout(root)
        if layout['layout'] == 'v2': return layout
        if layout['layout'] == 'incomplete':
            raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED', 'Resume the existing storage intent before initialization.')
        if list((root / 'events').glob('[0-9]*.json')):
            raise WorkflowError('LEGACY_MIGRATION_REQUIRED', 'Existing events require explicit verified migration.')
        sqlite = _sqlite()
        initiating_hash=_sha(operation_id.encode('utf-8')) if operation_id is not None else None
        database = confined_path(root, DATABASE_FILE, create_parents=True)
        if database.exists(): raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED', 'An unactivated database already exists; preserve and verify it.')
        identity = {'storage_format': 2, 'database_schema': DATABASE_SCHEMA,
                    'root_id': uuid.uuid4().hex, 'layout_id': uuid.uuid4().hex, 'database': DATABASE_FILE}
        intent = confined_path(root, INTENT_FILE, create_parents=True)
        _atomic_json(intent, {'kind': 'initialize', 'format': identity, 'phase': 'preparing', 'source_head': 0,'initiating_operation_hash':initiating_hash})
        conn = sqlite.connect(database)
        os.chmod(database, 0o600)
        try:
            conn.execute('PRAGMA foreign_keys=ON')
            if conn.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise WorkflowError('SQLITE_UNAVAILABLE', 'This filesystem cannot provide the required SQLite WAL mode.')
            conn.execute('PRAGMA synchronous=FULL')
            conn.executescript(SCHEMA)
            for key, value in {**identity, 'head': 0, 'head_hash': None, 'generation': 0, 'position': 0, 'dependency_schema': 1, 'dependency_head': 0}.items():
                _set_meta(conn, key, value)
            conn.execute('PRAGMA user_version=1')
            conn.commit()
        finally:
            conn.close()
        with database.open('r+b') as handle: os.fsync(handle.fileno())
        sync_directory(database.parent)
        _atomic_json(intent, {'kind': 'initialize', 'format': identity, 'phase': 'ready', 'source_head': 0,'initiating_operation_hash':initiating_hash})
        guard = confined_path(root, 'events/00000001.json', create_parents=True)
        _atomic_json(guard, LEGACY_GUARD)
        _atomic_json(confined_path(root, FORMAT_FILE), identity)
        intent.unlink()
        sync_directory(intent.parent)
        return detect_layout(root)


def validate_connection(conn,layout):
    if (conn.execute('PRAGMA user_version').fetchone()[0] != DATABASE_SCHEMA
            or any(_meta(conn, key) != layout[key] for key in ('root_id', 'layout_id', 'storage_format', 'database_schema'))):
        raise WorkflowError('CORRUPT_STORAGE', 'Database identity/schema does not match its selected root.')
    catalog = conn.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    if catalog != _expected_catalog():
        raise WorkflowError('UNSUPPORTED_STORAGE_SCHEMA', 'Database tables, indexes or triggers differ from the supported catalog; preserve and verify this root.')
    for key in ('head', 'generation', 'position', 'dependency_head'):
        value = _meta(conn, key)
        if type(value) is not int or value < 0:
            raise WorkflowError('CORRUPT_STORAGE', 'Database generation/head/position metadata is invalid; preserve and verify this root.')
    head = conn.execute('SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
    if (head[0] if head else 0) != _meta(conn, 'head') or (head[1] if head else None) != _meta(conn, 'head_hash'):
        raise WorkflowError('CORRUPT_STORAGE', 'Database event head and projection head disagree.')
    if (_meta(conn, 'dependency_schema') != 1 or _meta(conn, 'dependency_head') != _meta(conn, 'head')
            or conn.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='dependency_source'").fetchone() is None):
        raise WorkflowError('CORRUPT_DEPENDENCY_INDEX', 'Dependency catalog is missing or stale; verify/rebuild explicitly before work.')
    if conn.execute('SELECT 1 FROM dependency_dirty LIMIT 1').fetchone():
        raise WorkflowError('CORRUPT_DEPENDENCY_INDEX', 'Dependency witnesses are incomplete; verify/rebuild explicitly.')


@contextmanager
def connection(root: Path, *, write=False):
    # A selected-object read remains coordinated until its SQLite snapshot and
    # object hydration finish; GC cannot unlink an old projection mid-read.
    from .store import _exclusive
    if detect_layout(Path(root))['layout']!='v2':
        raise WorkflowError('STORAGE_LAYOUT_INVALID','A selected v2 layout is required.')
    with _exclusive(Path(root)):
        with _connection(root,write=write) as conn:yield conn


@contextmanager
def _connection(root: Path, *, write=False):
    root = Path(root).resolve()
    layout = detect_layout(root)
    if layout['layout'] != 'v2':
        raise WorkflowError('STORAGE_LAYOUT_INVALID', 'A selected v2 layout is required.')
    sqlite = _sqlite()
    conn = None
    try:
        uri = confined_path(root, layout['database']).as_uri() + ('?mode=rw' if write else '?mode=ro')
        conn = sqlite.connect(uri, uri=True, timeout=1, isolation_level=None)
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=1000')
        conn.execute('PRAGMA synchronous=FULL')
        if not write: conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        validate_connection(conn,layout)
        yield conn
        if write: conn.commit()
    except sqlite.Error as exc:
        if conn is not None and conn.in_transaction: conn.rollback()
        code = 'CONTROL_BUSY' if getattr(exc, 'sqlite_errorcode', None) in {sqlite.SQLITE_BUSY, sqlite.SQLITE_LOCKED} else 'CORRUPT_STORAGE'
        raise WorkflowError(code, 'Control database is busy or invalid; preserve it and retry/verify: ' + str(exc)) from exc
    except BaseException:
        if conn is not None and conn.in_transaction: conn.rollback()
        raise
    finally:
        if conn is not None: conn.close()


def _encode(root, value, kind):
    logical = _json(value).encode('utf-8')
    raw = json.dumps(value,sort_keys=False,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode('utf-8')
    from .stored_records import encode_record, MAX_RECORD_BYTES
    if len(raw) > MAX_RECORD_BYTES:
        raise WorkflowError('STORAGE_RECORD_LIMIT', 'Required logical record exceeds the 256 MiB materialization budget; no event was committed.')
    physical = encode_record(root, value)
    if physical is not None:
        encoded = json.dumps(physical,sort_keys=False,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode('utf-8')
        if len(encoded) > INLINE_BYTES:
            return 'record-object', _json(put_object(root, kind + '-record', encoded)), _sha(logical)
        return 'record', encoded.decode('utf-8'), _sha(logical)
    if len(raw) > INLINE_BYTES:
        return 'object', _json(put_object(root, kind, raw)), _sha(logical)
    return 'json', raw.decode('utf-8'), _sha(logical)


def _encode_run(root,value):
    from .stored_records import encode_record,_pack,digest,MAX_RECORD_BYTES
    physical=encode_record(root,value)
    if physical is None:
        node,_=_pack(root,value);physical={'record_version':1,'node':node}
    raw=json.dumps(physical,sort_keys=False,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(raw)>MAX_RECORD_BYTES:raise WorkflowError('STORAGE_RECORD_LIMIT','Working run exceeds its metadata budget.')
    identity=digest(physical)
    if len(raw)>INLINE_BYTES:return 'run-record-object',_json(put_object(root,'working-run',raw)),identity
    return 'run-record',raw.decode('utf-8'),identity


def _decode(root, codec, payload, expected, *, working=False):
    try:
        from .stored_records import MAX_RECORD_BYTES
        if codec in {'run-record','run-record-object'}:
            from .stored_records import decode_record,digest
            physical=json.loads(payload)
            if codec=='run-record-object':physical=json.loads(read_object(root,physical,max_bytes=MAX_RECORD_BYTES))
            if digest(physical)!=expected:raise ValueError('working run physical checksum mismatch')
            return decode_record(root,physical,packages=not working)
        if codec=='archive2':
            from .run_archives import hydrate_working_detail
            record=json.loads(payload)
            if record.get('physical_sha256')!=expected:raise ValueError('archived run physical checksum mismatch')
            return hydrate_working_detail(root,record,packages=not working)
        if codec == 'event-archive':
            from .storage_journal import hydrate_event
            return hydrate_event(root, json.loads(payload), expected)
        if codec == 'archive':
            from .run_archives import hydrate_detail
            value = hydrate_detail(root, json.loads(payload))
            if _sha(_json(value).encode('utf-8')) != expected: raise ValueError('archive logical checksum mismatch')
            return value
        if codec in {'record', 'record-object'}:
            from .stored_records import decode_record
            physical = json.loads(payload)
            if codec == 'record-object':
                physical = json.loads(read_object(root, physical, max_bytes=MAX_RECORD_BYTES))
            value = decode_record(root, physical)
            if _sha(_json(value).encode('utf-8')) != expected:
                raise ValueError('hydrated logical checksum mismatch')
            return value
        if codec == 'object':
            ref = json.loads(payload)
            raw = read_object(root, ref, max_bytes=MAX_RECORD_BYTES)
        elif codec == 'json': raw = payload.encode('utf-8')
        else: raise ValueError('unsupported cell codec')
        value = json.loads(raw)
        if _sha(_json(value).encode('utf-8')) != expected: raise ValueError('stored logical checksum mismatch')
        return value
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkflowError('CORRUPT_STORAGE', 'A database record is invalid: ' + str(exc)) from exc


def _load_space(conn, root, path, rows=None, *, working=False):
    name = _space(path)
    shape = conn.execute('SELECT shape FROM spaces WHERE path=?', (name,)).fetchone()
    if shape is None:
        if rows or storage_catalog.rows(conn,name):
            raise WorkflowError('CORRUPT_STORAGE','Required entity namespace is missing; preserve and verify the root.')
        return None
    if rows is None: rows = storage_catalog.rows(conn,name)
    values = []
    for key, codec, payload, digest in rows:
        storage_catalog.check(conn,name,key)
        value = _load_space(conn, root, tuple(json.loads(payload))) if codec == 'space' else _decode(root, codec, payload, digest,working=working and path==('runs',))
        storage_catalog.check(conn,name,key,path=path,value=value)
        values.append((key, value))
    if shape[0] == 'map': return dict(values)
    if shape[0] == 'list': return [value for _, value in values]
    if shape[0] == 'value' and len(values) == 1: return values[0][1]
    raise WorkflowError('CORRUPT_STORAGE', 'A projection namespace has an invalid shape.')


def _lookup_entity(conn, root, namespace, key, *, working=True):
    storage_catalog.check(conn,_space((namespace,)),key)
    rows = conn.execute('SELECT key,codec,payload,value_hash FROM entities WHERE space=? AND key=?', (_space((namespace,)), key)).fetchall()
    if not rows: return None
    value = _load_space(conn, root, (namespace,), rows,working=working)
    return value.get(key) if isinstance(value, dict) else value


def _sync_space(conn, root, path, value, *, before=None, complete=True):
    name = _space(path)
    shape = 'map' if isinstance(value, dict) else 'list' if isinstance(value, list) else 'value'
    prior = conn.execute('SELECT shape FROM spaces WHERE path=?', (name,)).fetchone()
    if prior is not None and prior[0] != shape:
        if not complete: raise WorkflowError('UNDECLARED_STORAGE_SCOPE', 'A partial scope cannot replace a namespace shape.')
        storage_catalog.delete_space(conn,name);prior = None
    if prior is None:
        conn.execute('INSERT INTO spaces VALUES(?,?,?,?,?)', (name, _space(path[:-1]) if len(path) > 1 else None,
                     path[-1], shape, _next_position(conn)))
    entries = dict(value) if shape == 'map' else {str(i): item for i, item in enumerate(value)} if shape == 'list' else {'': value}
    old = dict(before) if isinstance(before, dict) else {str(i): item for i, item in enumerate(before)} if isinstance(before, list) else {}
    if complete:
        existing = {row[0] for row in conn.execute('SELECT key FROM entities WHERE space=?', (name,))}
        removed = existing - set(entries)
    else: removed = set(old) - set(entries)
    for key in removed:
        if path == ('runs',):
            for kind, source in conn.execute('SELECT DISTINCT kind,source FROM dependencies WHERE space=? AND run_id=?', (name,key)).fetchall():
                select_dependents(conn, kind, source)
        child = conn.execute('SELECT payload FROM entities WHERE space=? AND key=? AND codec=?', (name,key,'space')).fetchone()
        if child: storage_catalog.delete_space(conn,child[0])
        conn.execute('DELETE FROM entities WHERE space=? AND key=?', (name,key))
        conn.execute('DELETE FROM entity_catalog WHERE space=? AND key=?', (name,key))
    position_base = _meta(conn,'position') if complete else None
    for index,(key, item) in enumerate(entries.items(),1):
        if key in old and item == old[key]:
            if complete:
                conn.execute('UPDATE entities SET position=? WHERE space=? AND key=?',(position_base+index,name,key))
                conn.execute('UPDATE entity_catalog SET position=? WHERE space=? AND key=?',(position_base+index,name,key))
            continue
        if path == ('usage',) and key == 'events' and isinstance(item,list):
            _sync_space(conn,root,path+(key,),item,complete=True)
            codec,payload,digest = 'space',_space(path+(key,)),_sha(_json(item).encode())
        else:
            prior_codec = conn.execute('SELECT codec FROM entities WHERE space=? AND key=?', (name,key)).fetchone()
            if path == ('runs',) and prior_codec and prior_codec[0] in {'archive','archive2'}:
                from .run_archives import store_working_detail
                record = store_working_detail(root, item)
                codec,payload,digest = 'archive2',_json(record),record['physical_sha256']
            elif path==('runs',):codec,payload,digest=_encode_run(root,item)
            else: codec,payload,digest = _encode(root,item,'projection-json')
        meta = item if isinstance(item,dict) else {}
        position = conn.execute('SELECT position FROM entities WHERE space=? AND key=?', (name,key)).fetchone()
        ordinal = position_base+index if complete else position[0] if position else _next_position(conn)
        fields = (name,key,ordinal,codec,payload,digest,*storage_catalog.headers(path,item))
        conn.execute('''INSERT INTO entities VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(space,key) DO UPDATE SET
            position=excluded.position,codec=excluded.codec,payload=excluded.payload,value_hash=excluded.value_hash,run_id=excluded.run_id,
            status=excluded.status,host=excluded.host,session_id=excluded.session_id,package_hash=excluded.package_hash,record_id=excluded.record_id''', fields)
        storage_catalog.sync(conn,fields)
        if path == ('runs',):
            from .run_archives import dependencies
            new_dependencies = dependencies(meta)
            sources = {(kind,source) for kind,source,_ in new_dependencies}
            sources.update(conn.execute('SELECT DISTINCT kind,source FROM dependencies WHERE space=? AND run_id=?', (name,key)).fetchall())
            for kind,source in sources:
                if conn.execute('SELECT 1 FROM dependency_dirty WHERE kind=? AND source=?', (kind,source)).fetchone() is None:
                    select_dependents(conn,kind,source)
            conn.execute('DELETE FROM dependencies WHERE space=? AND run_id=?', (name,key))
            for kind,source,entity_key in new_dependencies:
                conn.execute('INSERT INTO dependencies VALUES(?,?,?,?,?)', (kind,source,name,key,entity_key))
            from .storage_access import history_projections
            for view, value in history_projections(meta).items():
                view_codec,view_payload,view_hash = _encode(root,value,'run-history')
                conn.execute('INSERT INTO run_views VALUES(?,?,?,?,?,?) ON CONFLICT(kind,run_id) DO UPDATE SET codec=excluded.codec,payload=excluded.payload,value_hash=excluded.value_hash',
                    (name,key,view,view_codec,view_payload,view_hash))
        if path == ('document_proposals',):
            conn.execute('DELETE FROM document_files WHERE proposal_id=?', (key,))
            for file,record in meta.get('files',{}).items():
                conn.execute('INSERT INTO document_files VALUES(?,?,?,?,?)',
                    (name,key,meta.get('repo_id'),file,_sha(_json(record).encode('utf-8'))))

    if complete: _set_meta(conn,'position',max(_meta(conn,'position'),position_base+len(entries)))


def _read_view(conn, root, scope):
    if scope.full:storage_catalog.verify(conn)
    data = {}
    complete = set(scope.global_keys) | set(scope.namespaces)
    if scope.full:
        complete = {row[0] for row in conn.execute('SELECT name FROM spaces WHERE parent IS NULL ORDER BY position')}
    for name in complete:
        if conn.execute('SELECT 1 FROM spaces WHERE path=?', (_space((name,)),)).fetchone():
            data[name] = _load_space(conn, root, (name,),working=not scope.full and not scope.full_packages)
    if scope.run_view:
        if scope.run_view not in {'metrics','routing','trace'}:
            raise WorkflowError('UNDECLARED_STORAGE_SCOPE', 'Unknown historical projection.')
        all_ids = [row[0] for row in conn.execute('SELECT key FROM entities WHERE space=? ORDER BY position', (_space(('runs',)),))]
        selected_ids = all_ids if scope.history_all else [key for key in all_ids if key in scope.run_ids]
        runs = {key:{'id':key} for key in all_ids} if scope.history_all else {}
        for key in selected_ids:
            row=conn.execute('SELECT codec,payload,value_hash FROM run_views WHERE kind=? AND run_id=?', (scope.run_view,key)).fetchone()
            if row is None: raise WorkflowError('CORRUPT_STORAGE', 'Required indexed run history is missing; verify/rebuild explicitly.')
            runs[key]=_decode(root,*row)
        if runs: data['runs']=runs
    selections = list(scope.entity_keys) + ([] if scope.run_view else [('runs',key) for key in scope.run_ids])
    for namespace,key in selections:
        if namespace in complete: continue
        value = _lookup_entity(conn,root,namespace,key,working=not scope.full_packages)
        if value is not None: data.setdefault(namespace,{})[key] = value
    queries = list(scope.queries)
    if scope.active_runs: queries.append(EntityQuery('runs', (('status','active'),)))
    for query in queries:
        if query.namespace in complete: continue
        allowed = {'run_id','status','host','session_id','package_hash','record_id','key'}
        if any(field not in allowed for field,_ in query.filters):
            raise WorkflowError('UNDECLARED_STORAGE_SCOPE', 'An unindexed query is not an operational scope.')
        where = ' AND '.join(field+'=?' for field,_ in query.filters)
        sql = 'SELECT key,codec,payload,value_hash FROM entities WHERE space=?' + (' AND '+where if where else '') + ' ORDER BY position'
        rows = storage_catalog.rows(conn,_space((query.namespace,)),query.filters)
        values = _load_space(conn,root,(query.namespace,),rows,working=not scope.full_packages)
        if isinstance(values,dict): data.setdefault(query.namespace,{}).update(values)
    if scope.usage_run_ids:
        events = []
        for run_id in scope.usage_run_ids:
            rows = conn.execute('SELECT key,codec,payload,value_hash FROM entities WHERE space=? AND run_id=? ORDER BY position',
                (_space(('usage','events')),run_id)).fetchall()
            events.extend(_load_space(conn,root,('usage','events'),rows) or [])
        data['usage'] = {'events':events}
    operations = {}
    if scope.full:
        rows = conn.execute('SELECT operation_id,codec,payload,event_hash FROM events ORDER BY sequence')
    else:
        rows = [row for op in scope.operation_ids for row in conn.execute(
            'SELECT operation_id,codec,payload,event_hash FROM events WHERE operation_id=?',(op,))]
    for op,codec,payload,digest in rows: operations[op] = _decode(root,codec,payload,digest)
    state = {'schema_version':1,'version':_meta(conn,'head'),'data':data,'operations':operations,
             'recovery':{'ignored_temporary_files':[]}}
    if not scope.full:
        state['_storage'] = {key:_meta(conn,key) for key in ('root_id','layout_id','generation','head_hash')}
    return state, complete


def read_working_state(root: Path, scope: ReadScope):
    with connection(root) as conn: return _read_view(conn,Path(root),scope)[0]


def read_state(root: Path): return read_working_state(root,ReadScope(full=True))


def lookup_operation(root: Path, operation_id: str):
    with connection(root) as conn:
        row=conn.execute('SELECT codec,payload,event_hash FROM events WHERE operation_id=?',(operation_id,)).fetchone()
        return _decode(root,*row) if row else None


def read_head_event(root: Path):
    with connection(root) as conn:
        row=conn.execute('SELECT codec,payload,event_hash FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
        return _decode(root,*row) if row else None


def _transact_locked(root, expected_version, operation_id, event, *, precommit=None):
    from . import store
    with connection(root,write=True) as conn:
        guard=store.HOST_CONTEXT.get()
        guard_entities = (('host_bindings',guard['binding_id']),) if guard else ()
        minimal, _ = _read_view(conn,root,ReadScope(global_keys=(),operation_ids=(operation_id,),
            entity_keys=guard_entities+(('domain_receipts',operation_id),)))
        store._guard_transaction(minimal,event)
        from .storage_audit import operation_reserved
        if operation_reserved(root,operation_id):raise WorkflowError('OPERATION_CONFLICT','Operation ID belongs to physical maintenance.')
        previous=minimal['operations'].get(operation_id)
        if previous is not None:
            if previous['kind'].startswith('domain.'):
                return {'state':minimal,'event':previous,'replayed':True}
            original_scope, replacements = scope_for_event(previous,operation_id,binding_id=guard.get('binding_id') if guard else None)
            original_scope = ReadScope(**{**original_scope.__dict__,
                'global_keys':tuple(dict.fromkeys(original_scope.global_keys+tuple(replacements)))})
            prior_state,_ = _read_view(conn,root,original_scope)
            return {'state':prior_state,'event':previous,'replayed':True}
        if expected_version != minimal['version']:
            raise WorkflowError('STALE_STATE',f"expected state version {expected_version}, current version is {minimal['version']}")
        scope,replacements=scope_for_event(event,operation_id,binding_id=guard.get('binding_id') if guard else None)
        # Stored handoff identity selects its source binding; request data cannot replace it.
        if event['kind'] == 'domain.host.handoff-accept':
            request = event['payload'].get('request', {})
            if not isinstance(request,dict): request = {}
            envelope = _lookup_entity(conn, root, 'host_handoffs', request.get('handoff_id'))
            if envelope:
                scope = ReadScope(**{**scope.__dict__, 'entity_keys': scope.entity_keys +
                    (('host_bindings', envelope['binding_id']),)})
        if event['kind'] == 'domain.improve.case-approve':
            request = event['payload'].get('request', {})
            if not isinstance(request,dict): request = {}
            feedback = _lookup_entity(conn,root,'improvement_feedback',request.get('feedback_id'))
            if feedback:
                scope = ReadScope(**{**scope.__dict__, 'entity_keys': scope.entity_keys +
                    (('improvement_cases',(feedback.get('candidate') if isinstance(feedback.get('candidate'),dict) else {}).get('case_id','')),)})
        # Binding-selected commands and cross-run proof invalidation declare extra rows explicitly.
        extra_runs=set(scope.run_ids)
        for namespace,key in scope.entity_keys:
            if namespace=='host_bindings':
                binding=_lookup_entity(conn,root,namespace,key)
                if binding and binding.get('run_id'):extra_runs.add(binding['run_id'])
                request=event['payload'].get('request',{})
                if binding and isinstance(request,dict) and isinstance(request.get('task_id'),str):
                    task_key=binding['host']+':'+binding['session_id']+':'+request['task_id']
                    scope=ReadScope(**{**scope.__dict__,'entity_keys':scope.entity_keys+(('host_tasks',task_key),)})
        for query in scope.queries:
            if query.namespace == 'host_bindings':
                where = ' AND '.join(field+'=?' for field,_ in query.filters)
                extra_runs.update(row[0] for row in conn.execute(
                    'SELECT run_id FROM entities WHERE space=?' + (' AND '+where if where else ''),
                    (_space(('host_bindings',)), *(value for _,value in query.filters))) if row[0])
        if event['kind'] in {'test.change.applying','test.change.applied'}:
            run=_lookup_entity(conn,root,'runs',event['payload']['run_id']) or {}
            proposal=run.get('test_change_proposals',{}).get(event['payload'].get('proposal_id'),{})
            for source in proposal.get('changed_paths',[]):
                extra_runs.update(select_dependents(conn, 'test-path', source))
        queries = scope.queries
        if event['kind'].startswith('domain.host.'):
            queries += tuple(EntityQuery(namespace, (('run_id', run_id),))
                for run_id in extra_runs for namespace in ('host_bindings', 'host_tasks'))
        scope=ReadScope(**{**scope.__dict__,'run_ids':tuple(sorted(extra_runs)), 'queries': queries})
        state,complete=_read_view(conn,root,scope)
        if event['kind'] == 'domain.issues.start':
            from .journal_domains import issue_run_link
            request = event['payload'].get('request',{})
            try: link = issue_run_link(state['data'],request)
            except (WorkflowError,KeyError,TypeError,ValueError,AttributeError): link = None
            # Derivation does not replace the reducer's original validation order.
            if link is not None:
                existing = _lookup_entity(conn,root,'runs',link['run_id'])
                if existing is not None:state['data'].setdefault('runs',{})[link['run_id']] = existing
        if precommit is not None:precommit(state)
        store._guard_spec_approval(state,event)
        committed={'schema_version':1,'sequence':state['version']+1,'operation_id':operation_id,
                   'kind':event['kind'],'payload':event['payload']}
        if guard:committed['host_binding']={key:guard[key] for key in ('binding_id','revision')}
        # Legacy journal JSON canonicalizes event mappings before future replay.
        committed = json.loads(json.dumps(committed, sort_keys=True, ensure_ascii=False))
        projected=deepcopy(state)
        source_hash = None
        if event['kind'] == 'domain.stats.metrics':
            from .storage_access import metrics_source_hash
            source_hash = metrics_source_hash(root,conn,state['data'])
        store._apply_event(projected,committed,metrics_source_hash=source_hash)
        before,after=state['data'],projected['data']
        for key in set(before)|set(after):
            if key not in after:
                if key not in complete:raise WorkflowError('UNDECLARED_STORAGE_SCOPE','Cannot remove a partially loaded namespace.')
                storage_catalog.delete_space(conn,_space((key,)))
            elif key not in before or after[key] != before[key]:
                _sync_space(conn,root,(key,),after[key],before=before.get(key),complete=key in complete or key in replacements)
        _refresh_dependency_witnesses(conn)
        codec,payload,digest=_encode(root,committed,'event-json')
        conn.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(committed['sequence'],operation_id,event['kind'],codec,payload,digest))
        _set_meta(conn,'head',committed['sequence']);_set_meta(conn,'head_hash',digest)
        _set_meta(conn,'dependency_head',committed['sequence'])
        projected['version']=committed['sequence'];projected['operations'][operation_id]=committed
        projected['_storage']['head_hash']=digest
        return {'state':projected,'event':committed,'replayed':False}


def select_dependents(conn, kind, source):
    rows = conn.execute('SELECT run_id,entity_key FROM dependencies WHERE kind=? AND source=? ORDER BY run_id,entity_key', (kind,source)).fetchall()
    witness = conn.execute('SELECT checksum,row_count FROM dependency_sources WHERE kind=? AND source=?', (kind,source)).fetchone()
    if (witness is None and rows) or (witness is not None and
            (witness[0] != _sha(_json(rows).encode('utf-8')) or witness[1] != len(rows))):
        raise WorkflowError('CORRUPT_DEPENDENCY_INDEX', 'Reverse dependencies disagree with their content-bound source witness; verify/rebuild explicitly.')
    return sorted({row[0] for row in rows})


def _refresh_dependency_witnesses(conn):
    for kind,source in conn.execute('SELECT kind,source FROM dependency_dirty').fetchall():
        rows = conn.execute('SELECT run_id,entity_key FROM dependencies WHERE kind=? AND source=? ORDER BY run_id,entity_key', (kind,source)).fetchall()
        if rows:
            conn.execute('INSERT INTO dependency_sources VALUES(?,?,?,?) ON CONFLICT(kind,source) DO UPDATE SET checksum=excluded.checksum,row_count=excluded.row_count',
                (kind,source,_sha(_json(rows).encode('utf-8')),len(rows)))
        else: conn.execute('DELETE FROM dependency_sources WHERE kind=? AND source=?', (kind,source))
    conn.execute('DELETE FROM dependency_dirty')


@lru_cache(maxsize=1)
def _expected_catalog():
    conn = _sqlite().connect(':memory:')
    try:
        conn.executescript(SCHEMA)
        return conn.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
    finally: conn.close()
