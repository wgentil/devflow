"""Independent, bounded session manifests and atomic operation receipts in SQLite."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from .document_units import digest
from .enforcement_events import apply_enforcement
from .store import WorkflowError

MAX_MANIFEST_BYTES = 4 * 1024 * 1024


def _encode(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if len(raw.encode('utf-8')) > MAX_MANIFEST_BYTES:
        raise WorkflowError('SESSION_SIZE_LIMIT', 'Session manifest exceeds its bounded storage contract.')
    return raw


@contextmanager
def _connection(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise WorkflowError('SESSION_UNAVAILABLE', 'Existing regular session database required.')
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        conn.execute('PRAGMA synchronous=FULL')
        conn.execute('BEGIN IMMEDIATE')
        yield conn
        conn.commit()
    except sqlite3.DatabaseError as exc:
        conn.rollback()
        raise WorkflowError('SESSION_CORRUPT', 'Preserve the session for explicit recovery.') from exc
    except BaseException:
        conn.rollback(); raise
    finally: conn.close()


def initialize_session(path: Path, manifest: dict) -> dict:
    path = Path(path).absolute()
    repos = manifest.get('repositories')
    if not isinstance(repos, list) or not repos or not manifest.get('source_identity') or not manifest.get('id'):
        raise WorkflowError('INVALID_SESSION', 'Explicit repositories, source identity and session ID required.')
    if any(path.resolve().is_relative_to(Path(repo).resolve()) for repo in repos):
        raise WorkflowError('SESSION_INSIDE_SCOPE', 'Keep session output outside reviewed repositories.')
    subject = {**manifest, 'enforcement': {'protocol':'devflow.python-enforcement/v1', 'policy_version': 1}, 'state_version': 0}
    raw = _encode({'schema_version': 1, 'version': 0, 'subject': subject})
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb'): pass
    except FileExistsError as exc:
        raise WorkflowError('SESSION_EXISTS', 'Session already exists; read it instead.') from exc
    with _connection(path) as conn:
        conn.execute('CREATE TABLE manifest (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL)')
        conn.execute('CREATE TABLE operations (id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, receipt TEXT NOT NULL)')
        conn.execute('INSERT INTO manifest VALUES (1,?)', (raw,))
    return json.loads(raw)


def _read(conn):
    row = conn.execute('SELECT length(CAST(body AS BLOB)) FROM manifest WHERE id=1').fetchone()
    if not row or row[0] > MAX_MANIFEST_BYTES:
        raise WorkflowError('SESSION_CORRUPT', 'Missing or oversized session manifest.')
    try:
        value = json.loads(conn.execute('SELECT body FROM manifest WHERE id=1').fetchone()[0])
        if value['schema_version'] != 1 or type(value['version']) is not int or not isinstance(value['subject'], dict): raise ValueError()
        return value
    except (ValueError, KeyError, TypeError) as exc:
        raise WorkflowError('SESSION_CORRUPT', 'Invalid session manifest; preserve for recovery.') from exc


def read_session(path: Path) -> dict:
    with _connection(path) as conn: return _read(conn)


def transact_session(path: Path, expected_version: int, operation_id: str, event: dict) -> dict:
    if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 2048:
        raise WorkflowError('INVALID_OPERATION_ID', 'Bounded operation identity required.')
    request_hash = digest(event)
    with _connection(path) as conn:
        previous = conn.execute('SELECT request_hash,receipt FROM operations WHERE id=?', (operation_id,)).fetchone()
        if previous:
            if previous[0] != request_hash: raise WorkflowError('OPERATION_CONFLICT', 'Operation belongs to another request.')
            return {**json.loads(previous[1]), 'replayed': True}
        state = _read(conn)
        if state['version'] != expected_version:
            raise WorkflowError('STATE_VERSION_CONFLICT', 'Re-read the session before issuing a new operation.')
        subject = apply_enforcement(state['subject'], event['action'], event['record'])
        updated = {**state, 'version': expected_version+1, 'subject': subject}
        receipt = {'version': updated['version'], 'operation_id': operation_id, 'subject_hash': digest(subject), 'replayed': False}
        conn.execute('UPDATE manifest SET body=? WHERE id=1', (_encode(updated),))
        conn.execute('INSERT INTO operations VALUES (?,?,?)', (operation_id, request_hash, _encode(receipt)))
        return receipt
