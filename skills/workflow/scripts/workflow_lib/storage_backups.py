"""Coordinated complete backups; only the final manifest marks success."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from .storage_format import DATABASE_FILE, confined_path, detect_layout
from .store import WorkflowError, _atomic_json
from .platform_lock import sync_directory


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        while chunk := handle.read(1024 * 1024): digest.update(chunk)
    return digest.hexdigest()


def source_files(root):
    root = Path(root).resolve()
    result = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in tuple(dirs):
            relative = (parent / name).relative_to(root).as_posix()
            if relative in {'backups', 'maintenance'}:
                dirs.remove(name); continue
            confined_path(root, relative)
        for name in files:
            path = parent / name; relative = path.relative_to(root).as_posix()
            if relative == '.lock' or relative in {DATABASE_FILE+'-wal', DATABASE_FILE+'-shm'}: continue
            confined_path(root, relative)
            if not path.is_file(): raise WorkflowError('BACKUP_SOURCE_INVALID', 'Backup source contains a nonregular file.')
            result.append((relative, path))
    return sorted(result)


def _copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.backup-', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as output, Path(source).open('rb') as input_:
            shutil.copyfileobj(input_, output, length=1024 * 1024)
            output.flush(); os.fsync(output.fileno())
        os.replace(name, target); sync_directory(target.parent)
    finally: Path(name).unlink(missing_ok=True)


def sqlite_backup(source, target):
    from .sqlite_store import _sqlite
    sqlite = _sqlite()
    source_conn = sqlite.connect(Path(source).as_uri() + '?mode=ro', uri=True)
    target_conn = sqlite.connect(target)
    os.chmod(target, 0o600)
    try:
        source_conn.backup(target_conn)
        if target_conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise WorkflowError('BACKUP_INVALID', 'SQLite backup failed integrity verification.')
    finally: target_conn.close(); source_conn.close()
    with Path(target).open('r+b') as handle: os.fsync(handle.fileno())
    sync_directory(Path(target).parent)


def verify_backup(output):
    output = Path(output).resolve()
    try:
        manifest_path = confined_path(output, 'backup.json')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        body = manifest['body']
        from .stored_records import digest
        if manifest['sha256'] != digest(body) or body['backup_version'] != 1: raise ValueError('invalid backup manifest')
        for entry in body['files']:
            path = confined_path(output, entry['path'])
            if path.stat().st_size != entry['size_bytes'] or file_hash(path) != entry['sha256']:
                raise ValueError('backup file checksum mismatch: ' + entry['path'])
        return {'valid': True, 'file_count': len(body['files']), 'source_head': body['source_head']}
    except (OSError, ValueError, TypeError, KeyError, WorkflowError) as exc:
        return {'valid': False, 'errors': [str(exc)]}


def backup_locked(root, output, *, resume=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or root.is_relative_to(output):
        raise WorkflowError('BACKUP_PATH_INVALID', 'Backup output must not contain or replace its source.')
    if output.is_relative_to(root) and not output.is_relative_to(root / 'backups'):
        raise WorkflowError('BACKUP_PATH_INVALID', 'Internal backups belong beneath the selected backups directory.')
    if (output / 'backup.json').exists():
        report = verify_backup(output)
        if not report['valid']: raise WorkflowError('BACKUP_INVALID', '; '.join(report['errors']))
        return {'completed': True, 'output': str(output), **report}
    marker = output / '.backup-incomplete.json'
    identity = {'backup_version': 1, 'source_root': str(root)}
    if output.exists():
        if not resume or not marker.is_file() or json.loads(marker.read_text()) != identity:
            raise WorkflowError('BACKUP_OUTPUT_EXISTS', 'Use a new output path or explicitly resume this owned incomplete backup.')
    else: output.mkdir(parents=True)
    _atomic_json(marker, identity)
    layout = detect_layout(root)
    from . import store
    state = store._read_journal(root)[0] if layout['layout'] in {'legacy', 'incomplete'} else None
    head = state['version'] if state is not None else None
    if layout['layout'] == 'v2':
        from .sqlite_store import connection, _meta
        with connection(root) as conn: head = _meta(conn, 'head')
    entries = []
    for relative, source in source_files(root):
        target = confined_path(output, relative, create_parents=True)
        if layout['layout'] == 'v2' and relative == DATABASE_FILE:
            target.unlink(missing_ok=True)
            sqlite_backup(source, target)
        else: _copy_file(source, target)
        entries.append({'path': relative, 'size_bytes': target.stat().st_size, 'sha256': file_hash(target)})
    from .stored_records import digest
    body = {'backup_version': 1, 'source_head': head, 'files': entries}
    _atomic_json(output / 'backup.json', {'body': body, 'sha256': digest(body)})
    report = verify_backup(output)
    if not report['valid']: raise WorkflowError('BACKUP_INVALID', '; '.join(report['errors']))
    marker.unlink(); sync_directory(output)
    return {'completed': True, 'output': str(output), **report}
