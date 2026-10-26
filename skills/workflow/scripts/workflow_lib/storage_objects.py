"""Immutable typed objects with bounded chunks and verified logical identities."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zlib

from .platform_lock import sync_directory
from .storage_format import confined_path
from .store import WorkflowError

CHUNK_BYTES = 4 * 1024 * 1024
MAX_STORED_CHUNK = CHUNK_BYTES + 65536
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
VERSION = 1
HASH = re.compile('[0-9a-f]{64}')
KIND = re.compile('[a-z][a-z0-9.-]{0,127}')


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require(condition, message, code='STORAGE_OBJECT_CORRUPT'):
    if not condition:
        raise WorkflowError(code, message)


def _natural(value):
    return type(value) is int and value >= 0


def _descriptor(kind, size, digest):
    return {'schema_version': VERSION, 'kind': kind, 'size_bytes': size, 'content_sha256': digest}


def _publish(path: Path, raw: bytes) -> None:
    """Publish once without replacing an existing immutable file, including on Windows."""
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
        sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _read_file(path, limit):
    try:
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
        with os.fdopen(os.open(path, flags), 'rb') as stream:
            raw = stream.read(limit + 1)
        _require(len(raw) <= limit, 'Stored object exceeds its safe read limit.')
        return raw
    except OSError as exc:
        raise WorkflowError('STORAGE_OBJECT_UNAVAILABLE', 'Required immutable content is unavailable; verify the store before dependent work.') from exc


def _manifest_path(root, object_id, *, create=False):
    return confined_path(root, 'objects/manifests/' + object_id[:2] + '/' + object_id[2:] + '.json', create_parents=create)


def _chunk_path(root, encoding, digest, *, create=False):
    return confined_path(root, 'objects/chunks/' + encoding + '/' + digest[:2] + '/' + digest[2:] + '.blob', create_parents=create)


def _decode(raw, encoding, size):
    if encoding == 'identity':
        value = raw
    else:
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw), mode='rb') as stream:
                value = stream.read(size + 1)
                _require(len(value) <= size and not stream.read(1), 'Compressed object exceeds its declared size.')
        except (OSError, EOFError, zlib.error) as exc:
            raise WorkflowError('STORAGE_OBJECT_CORRUPT', 'Compressed immutable content is corrupt.') from exc
    _require(len(value) == size, 'Object length does not match its manifest.')
    return value


def _reference(manifest, raw):
    descriptor = {key: manifest[key] for key in ('schema_version', 'kind', 'size_bytes', 'content_sha256')}
    return {'schema_version': VERSION, 'kind': manifest['kind'], 'object_id': sha(canonical(descriptor)),
            'size_bytes': manifest['size_bytes'], 'manifest_sha256': sha(raw)}


def _load_manifest(root, ref):
    _require(isinstance(ref, dict) and ref.get('schema_version') == VERSION
             and isinstance(ref.get('kind'), str) and KIND.fullmatch(ref['kind'])
             and isinstance(ref.get('object_id'), str) and HASH.fullmatch(ref['object_id'])
             and isinstance(ref.get('manifest_sha256'), str) and HASH.fullmatch(ref['manifest_sha256'])
             and _natural(ref.get('size_bytes')), 'Invalid immutable object reference.', 'STORAGE_OBJECT_INVALID')
    raw = _read_file(_manifest_path(root, ref['object_id']), MAX_MANIFEST_BYTES)
    _require(sha(raw) == ref['manifest_sha256'], 'Object manifest checksum mismatch.')
    try:
        manifest = json.loads(raw)
        _require(isinstance(manifest, dict) and manifest.get('schema_version') == VERSION
                 and manifest.get('kind') == ref['kind'] and manifest.get('size_bytes') == ref['size_bytes']
                 and isinstance(manifest.get('content_sha256'), str) and HASH.fullmatch(manifest['content_sha256'])
                 and isinstance(manifest.get('chunks'), list), 'Invalid object manifest.')
        _require(_reference(manifest, raw) == ref, 'Object identity does not match its reference.')
        total = 0
        for part in manifest['chunks']:
            _require(isinstance(part, dict) and part.get('encoding') in {'gzip', 'identity'}
                     and _natural(part.get('size_bytes')) and 0 < part['size_bytes'] <= CHUNK_BYTES
                     and _natural(part.get('stored_bytes')) and 0 < part['stored_bytes'] <= MAX_STORED_CHUNK
                     and all(isinstance(part.get(k), str) and HASH.fullmatch(part[k])
                             for k in ('sha256', 'stored_sha256')), 'Invalid object chunk descriptor.')
            total += part['size_bytes']
        _require(total == manifest['size_bytes'], 'Object chunks do not cover its declared length.')
        return manifest
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkflowError('STORAGE_OBJECT_CORRUPT', 'Immutable object manifest is corrupt.') from exc


def stream_object(root: Path, ref: dict):
    """Consume through EOF before committing effects; final digest validates the stream."""
    manifest = _load_manifest(root, ref)
    digest = hashlib.sha256()
    for part in manifest['chunks']:
        raw = _read_file(_chunk_path(root, part['encoding'], part['sha256']), MAX_STORED_CHUNK)
        _require(len(raw) == part['stored_bytes'] and sha(raw) == part['stored_sha256'], 'Stored chunk checksum mismatch.')
        value = _decode(raw, part['encoding'], part['size_bytes'])
        _require(sha(value) == part['sha256'], 'Logical chunk checksum mismatch.')
        digest.update(value)
        yield value
    _require(digest.hexdigest() == manifest['content_sha256'], 'Logical object checksum mismatch.')


def read_object(root: Path, ref: dict, *, max_bytes: int) -> bytes:
    _require(_natural(max_bytes), 'A nonnegative object read budget is required.', 'STORAGE_OBJECT_INVALID')
    _load_manifest(root, ref)
    _require(ref['size_bytes'] <= max_bytes, 'Required object exceeds the requested read budget.', 'STORAGE_OBJECT_LIMIT')
    return b''.join(stream_object(root, ref))


def put_object(root: Path, kind: str, value: bytes, *, encoding: str = 'gzip') -> dict:
    _require(isinstance(kind, str) and KIND.fullmatch(kind) and isinstance(value, bytes)
             and encoding in {'gzip', 'identity'}, 'Object kind, bytes and supported encoding are required.', 'STORAGE_OBJECT_INVALID')
    descriptor = _descriptor(kind, len(value), sha(value))
    object_id = sha(canonical(descriptor))
    path = _manifest_path(root, object_id, create=True)
    if path.exists():
        raw = _read_file(path, MAX_MANIFEST_BYTES)
        # Existing content must validate; a put must not hide corruption by replacing it.
        try:
            manifest = json.loads(raw)
            ref = _reference(manifest, raw)
        except (ValueError, TypeError, KeyError) as exc:
            raise WorkflowError('STORAGE_OBJECT_CORRUPT', 'Existing object manifest is corrupt.') from exc
        _require(ref['object_id'] == object_id, 'Existing immutable object has a different identity.')
        for _ in stream_object(root, ref):
            pass
        return ref
    parts = []
    for offset in range(0, len(value), CHUNK_BYTES):
        chunk = value[offset:offset + CHUNK_BYTES]
        digest = sha(chunk)
        if encoding == 'gzip':
            buffer = io.BytesIO()
            with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as stream:
                stream.write(chunk)
            raw = buffer.getvalue()
        else:
            raw = chunk
        target = _chunk_path(root, encoding, digest, create=True)
        _publish(target, raw)
        existing = _read_file(target, MAX_STORED_CHUNK)
        _require(_decode(existing, encoding, len(chunk)) == chunk, 'Existing immutable chunk is corrupt.')
        parts.append({'encoding': encoding, 'sha256': digest, 'size_bytes': len(chunk),
                      'stored_sha256': sha(existing), 'stored_bytes': len(existing)})
    raw = canonical({**descriptor, 'chunks': parts})
    _require(len(raw) <= MAX_MANIFEST_BYTES, 'Object manifest exceeds its safe size.', 'STORAGE_OBJECT_LIMIT')
    _publish(path, raw)
    published = _read_file(path, MAX_MANIFEST_BYTES)
    try:
        ref = _reference(json.loads(published), published)
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkflowError('STORAGE_OBJECT_CORRUPT', 'Published object manifest is corrupt.') from exc
    _require(ref['object_id'] == object_id, 'Published object identity changed.')
    for _ in stream_object(root, ref):
        pass
    return ref


def put_file(root: Path, kind: str, source: Path, *, encoding='gzip') -> dict:
    """Publish a file with bounded memory; source must be stable for this read."""
    _require(isinstance(kind, str) and KIND.fullmatch(kind) and encoding in {'gzip', 'identity'},
             'Object kind and supported encoding are required.', 'STORAGE_OBJECT_INVALID')
    parts = []; digest = hashlib.sha256(); size = 0
    with Path(source).open('rb') as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk); size += len(chunk)
            if encoding == 'gzip':
                buffer = io.BytesIO()
                with gzip.GzipFile(filename='', mode='wb', fileobj=buffer, mtime=0) as stream: stream.write(chunk)
                raw = buffer.getvalue()
            else: raw = chunk
            identity = sha(chunk)
            target = _chunk_path(root, encoding, identity, create=True)
            _publish(target, raw)
            existing = _read_file(target, MAX_STORED_CHUNK)
            _require(_decode(existing, encoding, len(chunk)) == chunk, 'Existing immutable chunk is corrupt.')
            parts.append({'encoding': encoding, 'sha256': identity, 'size_bytes': len(chunk),
                          'stored_sha256': sha(existing), 'stored_bytes': len(existing)})
            _require(len(parts) * 400 <= MAX_MANIFEST_BYTES, 'File exceeds the object manifest budget.', 'STORAGE_OBJECT_LIMIT')
    descriptor = _descriptor(kind, size, digest.hexdigest())
    raw = canonical({**descriptor, 'chunks': parts})
    _require(len(raw) <= MAX_MANIFEST_BYTES, 'Object manifest exceeds its safe size.', 'STORAGE_OBJECT_LIMIT')
    path = _manifest_path(root, sha(canonical(descriptor)), create=True)
    _publish(path, raw)
    published = _read_file(path, MAX_MANIFEST_BYTES)
    ref = _reference(json.loads(published), published)
    _require(ref['object_id'] == sha(canonical(descriptor)), 'Published file identity changed.')
    for _ in stream_object(root, ref): pass
    return ref
