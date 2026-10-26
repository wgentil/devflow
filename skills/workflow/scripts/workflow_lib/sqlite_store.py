"""Indexed transactional authority; full materialization is explicit, never a lazy dict."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import uuid

from .storage_format import (DATABASE_FILE, DATABASE_SCHEMA, FORMAT_FILE, INTENT_FILE,
                             confined_path, detect_layout)
from .storage_objects import put_object, read_object
from .storage_scopes import ReadScope, EntityQuery, scope_for_event
from .store import WorkflowError

INLINE_BYTES = 65536
SCHEMA = '''
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE spaces(path TEXT PRIMARY KEY, parent TEXT REFERENCES spaces(path) ON DELETE CASCADE,
                    name TEXT NOT NULL, shape TEXT NOT NULL, position INTEGER NOT NULL);
CREATE TABLE entities(space TEXT REFERENCES spaces(path) ON DELETE CASCADE, key TEXT,
    position INTEGER NOT NULL, codec TEXT NOT NULL, payload TEXT NOT NULL, value_hash TEXT NOT NULL,
    run_id TEXT, status TEXT, host TEXT, session_id TEXT, package_hash TEXT,
    PRIMARY KEY(space,key));
CREATE INDEX entities_run ON entities(space,run_id);
CREATE INDEX entities_status ON entities(space,status);
CREATE INDEX entities_session ON entities(space,host,session_id,status);
CREATE TABLE events(sequence INTEGER PRIMARY KEY, operation_id TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL, codec TEXT NOT NULL, payload TEXT NOT NULL, event_hash TEXT NOT NULL);
CREATE TABLE dependencies(kind TEXT, source TEXT, space TEXT, run_id TEXT, entity_key TEXT,
    PRIMARY KEY(kind,source,run_id,entity_key),
    FOREIGN KEY(space,run_id) REFERENCES entities(space,key) ON DELETE CASCADE);
CREATE INDEX dependency_source ON dependencies(kind,source);
'''


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
    return json.loads(row[0])


def _set_meta(conn, key, value):
    conn.execute('INSERT INTO metadata(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, _json(value)))


def _next_position(conn):
    value = _meta(conn, 'position') + 1
    _set_meta(conn, 'position', value)
    return value


def initialize_store(root: Path):
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
        database = confined_path(root, DATABASE_FILE, create_parents=True)
        if database.exists(): raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED', 'An unactivated database already exists; preserve and verify it.')
        identity = {'storage_format': 2, 'database_schema': DATABASE_SCHEMA,
                    'root_id': uuid.uuid4().hex, 'layout_id': uuid.uuid4().hex, 'database': DATABASE_FILE}
        intent = confined_path(root, INTENT_FILE, create_parents=True)
        _atomic_json(intent, {'kind': 'initialize', 'format': identity, 'phase': 'preparing', 'source_head': 0})
        sqlite = _sqlite()
        conn = sqlite.connect(database)
        try:
            conn.execute('PRAGMA foreign_keys=ON')
            if conn.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise WorkflowError('SQLITE_UNAVAILABLE', 'This filesystem cannot provide the required SQLite WAL mode.')
            conn.execute('PRAGMA synchronous=FULL')
            conn.executescript(SCHEMA)
            for key, value in {**identity, 'head': 0, 'head_hash': None, 'generation': 0, 'position': 0}.items():
                _set_meta(conn, key, value)
            conn.execute('PRAGMA user_version=1')
            conn.commit()
        finally:
            conn.close()
        with database.open('rb') as handle: os.fsync(handle.fileno())
        sync_directory(database.parent)
        _atomic_json(intent, {'kind': 'initialize', 'format': identity, 'phase': 'ready', 'source_head': 0})
        guard = confined_path(root, 'events/00000001.json', create_parents=True)
        _atomic_json(guard, {'schema_version': 2, 'sequence': 1, 'operation_id': 'storage-v2-guard',
                             'kind': 'storage.upgrade-required', 'payload': {}})
        _atomic_json(confined_path(root, FORMAT_FILE), identity)
        intent.unlink()
        sync_directory(intent.parent)
        return detect_layout(root)


@contextmanager
def connection(root: Path, *, write=False):
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
        if (conn.execute('PRAGMA user_version').fetchone()[0] != DATABASE_SCHEMA
                or any(_meta(conn, key) != layout[key] for key in ('root_id', 'layout_id', 'storage_format', 'database_schema'))):
            raise WorkflowError('CORRUPT_STORAGE', 'Database identity/schema does not match its selected root.')
        head = conn.execute('SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
        if (head[0] if head else 0) != _meta(conn, 'head') or (head[1] if head else None) != _meta(conn, 'head_hash'):
            raise WorkflowError('CORRUPT_STORAGE', 'Database event head and projection head disagree.')
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
    raw = _json(value).encode('utf-8')
    from .stored_records import encode_record
    physical = encode_record(root, value)
    if physical is not None:
        encoded = _json(physical).encode('utf-8')
        if len(encoded) > INLINE_BYTES:
            return 'record-object', _json(put_object(root, kind + '-record', encoded)), _sha(raw)
        return 'record', encoded.decode('utf-8'), _sha(raw)
    if len(raw) > INLINE_BYTES:
        return 'object', _json(put_object(root, kind, raw)), _sha(raw)
    return 'json', raw.decode('utf-8'), _sha(raw)


def _decode(root, codec, payload, expected):
    try:
        if codec in {'record', 'record-object'}:
            from .stored_records import decode_record
            physical = json.loads(payload)
            if codec == 'record-object':
                physical = json.loads(read_object(root, physical, max_bytes=physical['size_bytes']))
            value = decode_record(root, physical)
            if _sha(_json(value).encode('utf-8')) != expected:
                raise ValueError('hydrated logical checksum mismatch')
            return value
        if codec == 'object':
            ref = json.loads(payload)
            raw = read_object(root, ref, max_bytes=ref['size_bytes'])
        elif codec == 'json': raw = payload.encode('utf-8')
        else: raise ValueError('unsupported cell codec')
        if _sha(raw) != expected: raise ValueError('stored logical checksum mismatch')
        return json.loads(raw)
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkflowError('CORRUPT_STORAGE', 'A database record is invalid: ' + str(exc)) from exc


def _load_space(conn, root, path, rows=None):
    name = _space(path)
    shape = conn.execute('SELECT shape FROM spaces WHERE path=?', (name,)).fetchone()
    if shape is None: return None
    if rows is None: rows = conn.execute('SELECT key,codec,payload,value_hash FROM entities WHERE space=? ORDER BY position', (name,)).fetchall()
    values = []
    for key, codec, payload, digest in rows:
        value = _load_space(conn, root, tuple(json.loads(payload))) if codec == 'space' else _decode(root, codec, payload, digest)
        values.append((key, value))
    if shape[0] == 'map': return dict(values)
    if shape[0] == 'list': return [value for _, value in values]
    if shape[0] == 'value' and len(values) == 1: return values[0][1]
    raise WorkflowError('CORRUPT_STORAGE', 'A projection namespace has an invalid shape.')


def _lookup_entity(conn, root, namespace, key):
    rows = conn.execute('SELECT key,codec,payload,value_hash FROM entities WHERE space=? AND key=?', (_space((namespace,)), key)).fetchall()
    if not rows: return None
    value = _load_space(conn, root, (namespace,), rows)
    return value.get(key) if isinstance(value, dict) else value


def _sync_space(conn, root, path, value, *, before=None, complete=True):
    name = _space(path)
    shape = 'map' if isinstance(value, dict) else 'list' if isinstance(value, list) else 'value'
    prior = conn.execute('SELECT shape FROM spaces WHERE path=?', (name,)).fetchone()
    if prior is not None and prior[0] != shape:
        if not complete: raise WorkflowError('UNDECLARED_STORAGE_SCOPE', 'A partial scope cannot replace a namespace shape.')
        conn.execute('DELETE FROM spaces WHERE path=?', (name,));prior = None
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
        child = conn.execute('SELECT payload FROM entities WHERE space=? AND key=? AND codec=?', (name,key,'space')).fetchone()
        if child: conn.execute('DELETE FROM spaces WHERE path=?', (child[0],))
        conn.execute('DELETE FROM entities WHERE space=? AND key=?', (name,key))
    for key, item in entries.items():
        if key in old and item == old[key]: continue
        if path == ('usage',) and key == 'events' and isinstance(item,list):
            _sync_space(conn,root,path+(key,),item,complete=True)
            codec,payload,digest = 'space',_space(path+(key,)),_sha(_json(item).encode())
        else: codec,payload,digest = _encode(root,item,'projection-json')
        meta = item if isinstance(item,dict) else {}
        position = conn.execute('SELECT position FROM entities WHERE space=? AND key=?', (name,key)).fetchone()
        ordinal = position[0] if position else _next_position(conn)
        fields = (name,key,ordinal,codec,payload,digest,
            meta.get('run_id') or (meta.get('id') if path==('runs',) else None),
            meta.get('status'),meta.get('host'),meta.get('session_id'),meta.get('package_hash'))
        conn.execute('''INSERT INTO entities VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(space,key) DO UPDATE SET
            codec=excluded.codec,payload=excluded.payload,value_hash=excluded.value_hash,run_id=excluded.run_id,
            status=excluded.status,host=excluded.host,session_id=excluded.session_id,package_hash=excluded.package_hash''', fields)
        if path == ('runs',):
            conn.execute('DELETE FROM dependencies WHERE space=? AND run_id=?', (name,key))
            for proof_id,proof in meta.get('verification_proofs',{}).items():
                for source in proof.get('test_hashes',{}):
                    conn.execute('INSERT OR IGNORE INTO dependencies VALUES(?,?,?,?,?)', ('test-path',source,name,key,proof_id))


def _read_view(conn, root, scope):
    data = {}
    complete = set(scope.global_keys) | set(scope.namespaces)
    if scope.full:
        complete = {row[0] for row in conn.execute('SELECT name FROM spaces WHERE parent IS NULL ORDER BY position')}
    for name in complete:
        if conn.execute('SELECT 1 FROM spaces WHERE path=?', (_space((name,)),)).fetchone():
            data[name] = _load_space(conn, root, (name,))
    selections = list(scope.entity_keys) + [('runs',key) for key in scope.run_ids]
    for namespace,key in selections:
        if namespace in complete: continue
        value = _lookup_entity(conn,root,namespace,key)
        if value is not None: data.setdefault(namespace,{})[key] = value
    queries = list(scope.queries)
    if scope.active_runs: queries.append(EntityQuery('runs', (('status','active'),)))
    for query in queries:
        if query.namespace in complete: continue
        allowed = {'run_id','status','host','session_id','package_hash','key'}
        if any(field not in allowed for field,_ in query.filters):
            raise WorkflowError('UNDECLARED_STORAGE_SCOPE', 'An unindexed query is not an operational scope.')
        where = ' AND '.join(field+'=?' for field,_ in query.filters)
        sql = 'SELECT key,codec,payload,value_hash FROM entities WHERE space=?' + (' AND '+where if where else '') + ' ORDER BY position'
        rows = conn.execute(sql, (_space((query.namespace,)),*(value for _,value in query.filters))).fetchall()
        values = _load_space(conn,root,(query.namespace,),rows)
        if isinstance(values,dict): data.setdefault(query.namespace,{}).update(values)
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
        scope,replacements=scope_for_event(event,operation_id,binding_id=guard.get('binding_id') if guard else None)
        # Stored handoff identity selects its source binding; request data cannot replace it.
        if event['kind'] == 'domain.host.handoff-accept':
            request = event['payload'].get('request', {})
            envelope = _lookup_entity(conn, root, 'host_handoffs', request.get('handoff_id'))
            if envelope:
                scope = ReadScope(**{**scope.__dict__, 'entity_keys': scope.entity_keys +
                    (('host_bindings', envelope['binding_id']),)})
        # Binding-selected commands and cross-run proof invalidation declare extra rows explicitly.
        extra_runs=set(scope.run_ids)
        for namespace,key in scope.entity_keys:
            if namespace=='host_bindings':
                binding=_lookup_entity(conn,root,namespace,key)
                if binding and binding.get('run_id'):extra_runs.add(binding['run_id'])
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
                extra_runs.update(row[0] for row in conn.execute('SELECT DISTINCT run_id FROM dependencies WHERE kind=? AND source=?',('test-path',source)))
        queries = scope.queries
        if event['kind'].startswith('domain.host.'):
            queries += tuple(EntityQuery(namespace, (('run_id', run_id),))
                for run_id in extra_runs for namespace in ('host_bindings', 'host_tasks'))
        scope=ReadScope(**{**scope.__dict__,'run_ids':tuple(sorted(extra_runs)), 'queries': queries})
        state,complete=_read_view(conn,root,scope)
        store._guard_transaction(state,event)
        previous=state['operations'].get(operation_id)
        if previous is not None:return {'state':state,'event':previous,'replayed':True}
        if expected_version != state['version']:
            raise WorkflowError('STALE_STATE',f"expected state version {expected_version}, current version is {state['version']}")
        if precommit is not None:precommit(state)
        store._guard_spec_approval(state,event)
        committed={'schema_version':1,'sequence':state['version']+1,'operation_id':operation_id,
                   'kind':event['kind'],'payload':event['payload']}
        if guard:committed['host_binding']={key:guard[key] for key in ('binding_id','revision')}
        projected=deepcopy(state)
        store._apply_event(projected,committed)
        before,after=state['data'],projected['data']
        for key in set(before)|set(after):
            if key not in after:
                if key not in complete:raise WorkflowError('UNDECLARED_STORAGE_SCOPE','Cannot remove a partially loaded namespace.')
                conn.execute('DELETE FROM spaces WHERE path=?',(_space((key,)),))
            elif key not in before or after[key] != before[key]:
                _sync_space(conn,root,(key,),after[key],before=before.get(key),complete=key in complete or key in replacements)
        codec,payload,digest=_encode(root,committed,'event-json')
        conn.execute('INSERT INTO events VALUES(?,?,?,?,?,?)',(committed['sequence'],operation_id,event['kind'],codec,payload,digest))
        _set_meta(conn,'head',committed['sequence']);_set_meta(conn,'head_hash',digest)
        projected['version']=committed['sequence'];projected['operations'][operation_id]=committed
        projected['_storage']['head_hash']=digest
        return {'state':projected,'event':committed,'replayed':False}
