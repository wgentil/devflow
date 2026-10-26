"""Versioned control layout detection; reading a root never initializes it."""
from pathlib import Path
import json
import re
import stat

from .store import WorkflowError

STORAGE_FORMAT = 2
DATABASE_SCHEMA = 1
SUPPORTED_STORAGE_FORMATS = (1, 2)
FORMAT_FILE = 'format.json'
INTENT_FILE = 'maintenance/intent.json'
DATABASE_FILE = 'store-v2/control.sqlite3'
LEGACY_GUARD = {'schema_version': 2, 'sequence': 1, 'operation_id': 'storage-v2-guard',
                'kind': 'storage.upgrade-required', 'payload': {}}


def confined_path(root: Path, relative: str, *, create_parents: bool = False) -> Path:
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts or '\\' in relative:
        raise WorkflowError('STORAGE_PATH_INVALID', 'Storage paths must stay within the selected control root.')
    root = Path(root)
    if create_parents:
        # Resolve an existing root: Windows may spell a missing path differently
        # while another publisher is creating its ancestors.
        root.mkdir(parents=True,exist_ok=True)
    root = root.resolve()
    path = root / part
    if not path.is_relative_to(root):
        raise WorkflowError('STORAGE_PATH_INVALID','Storage path is not lexically within its selected root.')
    for item in (path, *path.parents):
        if item == root:break
        try:info=item.lstat()
        except FileNotFoundError:continue
        attributes=getattr(info,'st_file_attributes',0)
        tag=getattr(info,'st_reparse_tag',0)
        # Name-surrogate reparse points include junctions/mounted folders.
        if stat.S_ISLNK(info.st_mode) or attributes & 0x400 and tag & 0x20000000:
            raise WorkflowError('STORAGE_PATH_INVALID','Storage links must not redirect managed content.')
        try:resolved=item.resolve(strict=True)
        except FileNotFoundError:
            if attributes & 0x400:
                raise WorkflowError('STORAGE_PATH_INVALID','Cannot prove confinement of an unavailable reparse point.')
            continue
        if not resolved.is_relative_to(root):
            raise WorkflowError('STORAGE_PATH_INVALID','Storage links must not redirect content outside its root.')
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Recheck after creating directories; cooperative publishers never redirect them.
        return confined_path(root, relative)
    return path


def detect_layout(root: Path) -> dict:
    root = Path(root).resolve()
    manifest = confined_path(root, FORMAT_FILE)
    intent = confined_path(root, INTENT_FILE)
    if not manifest.exists():
        if intent.exists():
            return {'layout': 'incomplete', 'storage_format': None, 'root': str(root)}
        events = confined_path(root, 'events')
        if events.exists() and not events.is_dir():
            raise WorkflowError('STORAGE_LAYOUT_INVALID', 'Legacy events path is not a directory.')
        return {'layout': 'legacy' if events.is_dir() else 'uninitialized',
                'storage_format': 1 if events.is_dir() else None, 'root': str(root)}
    try:
        with manifest.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('format manifest exceeds limit')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('format manifest must be an object')
        if type(value.get('storage_format')) is not int or value.get('storage_format') not in SUPPORTED_STORAGE_FORMATS:
            raise WorkflowError('UNSUPPORTED_STORAGE_FORMAT', 'Upgrade the helper before opening this control layout.')
        if value['storage_format'] != STORAGE_FORMAT:
            raise ValueError('legacy roots do not use a v2 format manifest')
        if (type(value.get('database_schema')) is not int or value.get('database_schema') != DATABASE_SCHEMA or value.get('database') != DATABASE_FILE
                or not all(isinstance(value.get(k), str) and re.fullmatch('[0-9a-f]{32}', value[k])
                           for k in ('root_id', 'layout_id'))):
            raise ValueError('unsupported or incomplete database identity')
        database = confined_path(root, value['database'])
        if not database.is_file():
            raise ValueError('selected database is missing')
        guard = confined_path(root, 'events/00000001.json')
        with guard.open('rb') as stream: guard_raw = stream.read(65537)
        if len(guard_raw) > 65536 or json.loads(guard_raw) != LEGACY_GUARD:
            raise ValueError('legacy-client compatibility guard is missing or invalid; preserve the root and resume/verify explicitly')
        return {**value, 'layout': 'v2', 'root': str(root)}
    except WorkflowError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise WorkflowError('STORAGE_LAYOUT_INVALID', 'Preserve this root and inspect/resume its storage recovery: ' + str(exc)) from exc
