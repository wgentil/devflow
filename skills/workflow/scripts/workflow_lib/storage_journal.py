"""Immutable event segments, exact locators and recovery checkpoints."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .storage_format import DATABASE_FILE, confined_path
from .storage_objects import put_object, put_file, read_object, stream_object
from .stored_records import canonical, digest
from .store import WorkflowError

MAX_RECORD_BYTES = 256 * 1024 * 1024


def hydrate_event(root, reference, expected):
    from . import sqlite_store as sql
    if reference.get('kind') != 'event-record':
        raise WorkflowError('INVALID_EVENT_ARCHIVE', 'Exact event locator has an unsupported kind.')
    value = json.loads(read_object(root, reference, max_bytes=MAX_RECORD_BYTES))
    if set(value) != {'event_record_version', 'codec', 'payload'} or value['event_record_version'] != 1 or value['codec'] not in {'json', 'object', 'record', 'record-object'}:
        raise WorkflowError('INVALID_EVENT_ARCHIVE', 'Unsupported immutable event record.')
    return sql._decode(root, value['codec'], value['payload'], expected)


def archive_events(conn, root, *, page_size=128):
    from . import sqlite_store as sql
    cursor = conn.execute("SELECT sequence,operation_id,codec,payload,event_hash FROM events WHERE codec!='event-archive' ORDER BY sequence")
    while rows := cursor.fetchmany(page_size):
        entries = []
        for sequence, op, codec, payload, event_hash in rows:
            reference = put_object(root, 'event-record', canonical({'event_record_version': 1, 'codec': codec, 'payload': payload}))
            raw = conn.execute('SELECT reference FROM raw_events WHERE sequence=?', (sequence,)).fetchone()
            entries.append({'sequence': sequence, 'operation_id': op, 'event_hash': event_hash,
                            'record': reference, 'raw': json.loads(raw[0]) if raw else None})
            conn.execute('UPDATE events SET codec=?,payload=? WHERE sequence=?', ('event-archive',sql._json(reference),sequence))
        segment = {'segment_version': 1, 'first_sequence': rows[0][0], 'last_sequence': rows[-1][0], 'entries': entries}
        ref = put_object(root, 'event-segment', canonical(segment))
        conn.execute('INSERT OR IGNORE INTO event_segments VALUES(?,?,?,?)',
                     (ref['object_id'], rows[0][0], rows[-1][0], sql._json(ref)))


def checkpoint(root, identity):
    from . import sqlite_store as sql
    from .storage_backups import sqlite_backup
    root = Path(root)
    with sql.connection(root) as conn:
        prior = conn.execute('SELECT reference FROM checkpoints WHERE checkpoint_id=?', (identity,)).fetchone()
        if prior:
            ref = json.loads(prior[0]); verify_checkpoint(root, ref, conn); return ref
        head = sql._meta(conn, 'head'); generation = sql._meta(conn, 'generation')
        body = {'checkpoint_version': 1, 'root_id': sql._meta(conn, 'root_id'),
                'layout_id': sql._meta(conn, 'layout_id'), 'head': head, 'generation': generation,
                'head_hash': sql._meta(conn, 'head_hash'),
                'segments': [json.loads(row[0]) for row in conn.execute('SELECT reference FROM event_segments ORDER BY first_sequence')],
                'logical_data_sha256': digest({row[0]: sql._load_space(conn,root,(row[0],)) for row in
                    conn.execute('SELECT name FROM spaces WHERE parent IS NULL ORDER BY position')})}
    target = confined_path(root, 'maintenance/checkpoint-' + identity + '.sqlite3', create_parents=True)
    target.unlink(missing_ok=True)
    sqlite_backup(confined_path(root, DATABASE_FILE), target)
    body['database'] = put_file(root, 'sqlite-checkpoint', target)
    ref = put_object(root, 'control-checkpoint', canonical(body))
    with sql.connection(root, write=True) as conn:
        if sql._meta(conn,'head') != head or sql._meta(conn,'generation') != generation:
            raise WorkflowError('STALE_MAINTENANCE_PLAN', 'History changed while making the coordinated checkpoint.')
        conn.execute('INSERT INTO checkpoints VALUES(?,?,?,?)', (identity,head,generation,sql._json(ref)))
    target.unlink(); return ref


def verify_checkpoint(root, reference, conn=None):
    from . import sqlite_store as sql
    if reference.get('kind') != 'control-checkpoint':
        raise WorkflowError('INVALID_CHECKPOINT', 'Recovery checkpoint has an unsupported kind.')
    body = json.loads(read_object(root, reference, max_bytes=MAX_RECORD_BYTES))
    if body.get('checkpoint_version') != 1 or body.get('database', {}).get('kind') != 'sqlite-checkpoint':
        raise WorkflowError('INVALID_CHECKPOINT', 'Unsupported recovery checkpoint.')
    if conn is not None:
        if (body.get('root_id') != sql._meta(conn,'root_id') or body.get('layout_id') != sql._meta(conn,'layout_id')
                or type(body.get('head')) is not int or not 0 <= body['head'] <= sql._meta(conn,'head')
                or body.get('generation', -1) > sql._meta(conn,'generation')):
            raise WorkflowError('INVALID_CHECKPOINT', 'Checkpoint cannot replace this root or a newer generation.')
        row = conn.execute('SELECT event_hash FROM events WHERE sequence=?', (body['head'],)).fetchone()
        if body['head_hash'] != (row[0] if row else None):
            raise WorkflowError('INVALID_CHECKPOINT', 'Checkpoint omits or contradicts committed history.')
    for _ in stream_object(root, body['database']): pass
    for ref in body['segments']:
        for _ in stream_object(root, ref): pass
    return body


def read_raw_event(root, sequence):
    from . import sqlite_store as sql
    from .storage_format import detect_layout
    root = Path(root)
    if type(sequence) is not int or sequence < 1:
        raise WorkflowError('INVALID_EVENT_SEQUENCE', 'Choose a positive global event sequence.')
    name = f'{sequence:08d}.json'
    if detect_layout(root)['layout'] == 'legacy':
        from .store import _read_journal
        state, _ = _read_journal(root)
        if sequence > state['version']: raise WorkflowError('EVENT_NOT_FOUND', 'Unknown event sequence.')
        return {'name': name, 'bytes': confined_path(root, 'events/' + name).read_bytes()}
    with sql.connection(root) as conn:
        row = conn.execute('SELECT name,reference,raw_hash FROM raw_events WHERE sequence=?', (sequence,)).fetchone()
        logical = conn.execute('SELECT codec,payload,event_hash FROM events WHERE sequence=?', (sequence,)).fetchone()
        if logical is None: raise WorkflowError('EVENT_NOT_FOUND', 'Unknown event sequence.')
        event = sql._decode(root, *logical)
        if row:
            raw = read_object(root, json.loads(row[1]), max_bytes=MAX_RECORD_BYTES)
            if row[0] != name or hashlib.sha256(raw).hexdigest() != row[2] or json.loads(raw) != event:
                raise WorkflowError('INVALID_RAW_EVENT', 'Original raw event identity differs from committed logical history.')
            return {'name': name, 'bytes': raw}
        return {'name': name, 'bytes': canonical(event)}
