"""Explicit terminal maintenance, immutable detail and selected historical queries."""
from __future__ import annotations
import json
from pathlib import Path
from .storage_objects import put_object, read_object
from .stored_records import canonical, digest, encode_record, decode_record
from .store import WorkflowError

TERMINAL = frozenset(('delivered', 'discarded'))


def summarize_run(run):
    return {'id': run['id'], 'status': run.get('status'), 'actors': run.get('actors', {}),
        'item_outcomes': {key: item.get('status') for key, item in run.get('items', {}).items()},
        'proof_ids': sorted(set(run.get('verification_proofs', {})) | set(run.get('verifier_proofs', {}))),
        'package_ids': sorted(run.get('review_packages', {})),
        'review_ids': sorted(row['review_id'] for entries in run.get('reviews', {}).values()
                             for row in entries if row.get('review_id')),
        'delivery': {key: run.get('delivery', {})[key] for key in
                     ('manifest_hash', 'recorded_at', 'status') if key in (run.get('delivery') or {})},
        'issue_group_id': run.get('issue_group_id'), 'issue_scope': run.get('issue_scope')}


def _terminal(run):
    if (run.get('status') not in TERMINAL or run.get('active_attempt')
            or any(row.get('status') == 'running' for row in run.get('native_invocations', {}).values())
            or any(row.get('status') == 'claimed' for row in run.get('repair_cycles', []))):
        raise WorkflowError('ARCHIVE_NOT_TERMINAL', 'Only explicitly terminal runs without active work can be archived.')


def store_detail(root, run):
    _terminal(run)
    record = encode_record(root, run)
    envelope = {'archive_version': 1, 'codec': 'record' if record is not None else 'json',
                'body': record if record is not None else run}
    summary = summarize_run(run)
    raw = json.dumps(envelope,sort_keys=False,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode('utf-8')
    from .stored_records import MAX_RECORD_BYTES
    if len(raw) > MAX_RECORD_BYTES:
        raise WorkflowError('STORAGE_RECORD_LIMIT', 'Archive detail exceeds its materialization budget; the original record was retained.')
    return {'archive_version': 1, 'reference': put_object(root, 'terminal-run', raw),
            'logical_sha256': digest(run), 'summary': summary, 'summary_sha256': digest(summary)}


def summary_from_record(record):
    if not isinstance(record,dict):raise WorkflowError('INVALID_RUN_ARCHIVE','Malformed terminal archive.')
    version=record.get('archive_version')
    identity='logical_sha256' if version==1 else 'physical_sha256'
    if (type(version) is not int or version not in {1,2}
            or set(record)!={'archive_version','reference',identity,'summary','summary_sha256'}
            or record['reference'].get('kind')!='terminal-run'
            or digest(record['summary'])!=record['summary_sha256']
            or record['summary'].get('status') not in TERMINAL):
        raise WorkflowError('INVALID_RUN_ARCHIVE','Terminal archive identity/summary is invalid; preserve the root.')
    return record['summary']


def hydrate_detail(root, record):
    summary = summary_from_record(record)
    ref = record['reference']
    from .stored_records import MAX_RECORD_BYTES
    try:
        envelope = json.loads(read_object(root, ref, max_bytes=MAX_RECORD_BYTES))
        if set(envelope) != {'archive_version', 'codec', 'body'} or envelope['archive_version'] != 1:
            raise ValueError('unsupported archive envelope')
        if envelope['codec'] == 'record': run = decode_record(root, envelope['body'])
        elif envelope['codec'] == 'json': run = envelope['body']
        else: raise ValueError('unsupported archive body encoding')
        if digest(run) != record['logical_sha256'] or summarize_run(run) != summary:
            raise ValueError('archive logical body differs from its summary')
        _terminal(run)
        return run
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkflowError('INVALID_RUN_ARCHIVE', str(exc)) from exc


def store_working_detail(root,run):
    from .stored_records import _pack
    _terminal(run);node,_=_pack(root,run)
    body={'record_version':1,'node':node};summary=summarize_run(run)
    raw=json.dumps(body,sort_keys=False,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    return {'archive_version':2,'reference':put_object(root,'terminal-run',raw),
        'physical_sha256':digest(body),'summary':summary,'summary_sha256':digest(summary)}


def hydrate_working_detail(root,record,*,packages=True):
    from .stored_records import MAX_RECORD_BYTES
    summary_from_record(record)
    if record.get('archive_version')!=2:
        raise WorkflowError('INVALID_RUN_ARCHIVE','Unsupported or corrupt terminal archive summary.')
    body=json.loads(read_object(root,record['reference'],max_bytes=MAX_RECORD_BYTES))
    if digest(body)!=record.get('physical_sha256'):raise WorkflowError('INVALID_RUN_ARCHIVE','Terminal physical identity differs.')
    run=decode_record(root,body,packages=packages)
    if summarize_run(run)!=record['summary']:raise WorkflowError('INVALID_RUN_ARCHIVE','Terminal summary differs.')
    _terminal(run);return run


def archive_run(root: Path, run_id: str):
    from . import sqlite_store as sql
    from .store import _exclusive
    root = Path(root)
    with _exclusive(root), sql.connection(root, write=True) as conn:
        row = conn.execute('SELECT codec,payload,value_hash FROM entities WHERE space=? AND key=?',
                           (sql._space(('runs',)), run_id)).fetchone()
        if row is None: raise WorkflowError('RUN_NOT_FOUND', 'Select an existing run to archive.')
        run = sql._decode(root, *row,working=True)
        _terminal(run)
        if row[0] in {'archive','archive2'}: return summary_from_record(json.loads(row[1]))
        record = store_working_detail(root, run)
        conn.execute('UPDATE entities SET codec=?,payload=?,value_hash=? WHERE space=? AND key=?',
                     ('archive2', sql._json(record),record['physical_sha256'], sql._space(('runs',)), run_id))
        sql._set_meta(conn, 'generation', sql._meta(conn, 'generation') + 1)
        return record['summary']


def read_run(root, run_id):
    from .sqlite_store import read_working_state
    from .storage_scopes import ReadScope
    from .storage_format import detect_layout
    if detect_layout(Path(root))['layout']=='v2':
        state=read_working_state(root,ReadScope(global_keys=(),run_ids=(run_id,),full_packages=True))
    else:
        from .storage_access import read_current
        state=read_current(root,run_id=run_id)
    run=state['data'].get('runs',{}).get(run_id)
    if run is None: raise WorkflowError('RUN_NOT_FOUND', 'Requested historical run is unavailable.')
    return run


def _page_size(value):
    if type(value) is not int or not 1 <= value <= 1000:
        raise WorkflowError('INVALID_PAGE_SIZE', 'Page size must be between 1 and 1000.')
    return value


def iter_run_summaries(root, *, page_size=100):
    from . import sqlite_store as sql
    with sql.connection(root) as conn:
        cursor = conn.execute('SELECT codec,payload,value_hash FROM entities WHERE space=? ORDER BY position',
                              (sql._space(('runs',)),))
        while rows := cursor.fetchmany(_page_size(page_size)):
            for codec, payload, expected in rows:
                yield summary_from_record(json.loads(payload)) if codec in {'archive','archive2'} else summarize_run(sql._decode(root, codec, payload, expected,working=True))


def iter_events(root, *, after_sequence=0, page_size=100):
    from . import sqlite_store as sql
    with sql.connection(root) as conn:
        cursor = conn.execute('SELECT codec,payload,event_hash FROM events WHERE sequence>? ORDER BY sequence', (after_sequence,))
        while rows := cursor.fetchmany(_page_size(page_size)):
            for row in rows: yield sql._decode(root, *row)


def iter_entities(root, namespace, *, page_size=100):
    from . import sqlite_store as sql
    with sql.connection(root) as conn:
        cursor = conn.execute('SELECT key,codec,payload,value_hash FROM entities WHERE space=? ORDER BY position', (sql._space((namespace,)),))
        while rows := cursor.fetchmany(_page_size(page_size)):
            for key, codec, payload, expected in rows:
                yield key, sql._decode(root, codec, payload, expected)


def dependencies(run):
    """Complete reverse links derived from the full selected logical run."""
    rows = set()
    for proof_id, proof in run.get('verification_proofs', {}).items():
        rows.add(('proof', proof_id, proof_id))
        for source in proof.get('test_hashes', {}): rows.add(('test-path', source, proof_id))
    for key in run.get('review_packages', {}): rows.add(('package', key, key))
    names = {'proof_id': 'proof', 'evidence_id': 'proof', 'package_hash': 'package',
             'finding_id': 'finding', 'source_hash': 'source', 'content_digest': 'source',
             'artifact_hash': 'artifact', 'artifact_id': 'artifact', 'context_hash': 'context'}
    pending = [((), run)]
    while pending:
        path, node = pending.pop()
        from .stored_records import StoredPackage
        if isinstance(node,StoredPackage):
            for kind,source,relative,absolute in node.record['summary']['_storage_dependency_links']:
                # Named artifact/source map links use their original entry key.
                entity_key=relative if absolute else '/'.join((*path,relative))
                rows.add((kind,source,entity_key))
        elif isinstance(node, dict):
            for key, value in node.items():
                if key in names and isinstance(value, str): rows.add((names[key], value, '/'.join((*path, key))))
                if key in {'artifacts', 'current_source_indexes'} and isinstance(value, dict):
                    for name, identity in value.items():
                        if isinstance(identity, str): rows.add(('artifact' if key == 'artifacts' else 'source', identity, name))
                pending.append(((*path, key), value))
        elif isinstance(node, list):
            pending.extend(((*path, str(i)), value) for i, value in enumerate(node))
    for finding in run.get('unresolved_findings', []):
        if isinstance(finding.get('id'), str): rows.add(('finding', finding['id'], finding['id']))
    return sorted(rows)
