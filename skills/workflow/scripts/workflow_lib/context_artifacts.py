"""Immutable context content and advisory, conservative retrieval indexes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .document_units import canonical, digest, document_path, select_document_units
from .store import WorkflowError, _atomic_json

VERSION = 1
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024


def _directory(root: Path) -> Path:
    root = Path(root).resolve()
    path = root / 'context-artifacts'
    if path.is_symlink():
        raise WorkflowError('CONTEXT_CACHE_INVALID', 'context cache must be within the selected control root')
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read(path: Path):
    if path.is_symlink():
        raise ValueError('symlink cache file')
    with path.open('rb') as stream:
        raw = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError('cache file exceeds safe read limit')
    return json.loads(raw)


def store_context_artifact(root: Path, value: dict, identity: dict) -> dict:
    envelope = {'builder_version': VERSION, 'identity': identity, 'value': value}
    raw = canonical(envelope)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise WorkflowError('CONTEXT_ARTIFACT_OVERFLOW', 'context artifact exceeds storage limit')
    artifact_id = hashlib.sha256(raw).hexdigest()
    path = _directory(root) / (artifact_id + '.json')
    try:
        valid = _read(path) == envelope
    except (OSError, ValueError):
        valid = False
    if not valid:
        _atomic_json(path, envelope)
    return {'artifact_id': artifact_id, 'artifact_ref': str(path), 'content_bytes': len(canonical(value))}


def inspect_context_artifact(root: Path, artifact_id: str) -> dict:
    if not isinstance(artifact_id, str) or not re.fullmatch(r'[0-9a-f]{64}', artifact_id):
        raise WorkflowError('CONTEXT_ARTIFACT_INVALID', 'a valid content-addressed artifact ID is required')
    try:
        envelope = _read(_directory(root) / (artifact_id + '.json'))
        if digest(envelope) != artifact_id or envelope['builder_version'] != VERSION or not isinstance(envelope['value'], dict):
            raise ValueError('content identity mismatch')
        return envelope['value']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise WorkflowError('CONTEXT_ARTIFACT_UNAVAILABLE', 'context artifact is missing or corrupt') from exc


def _index(root):
    try:
        index = _read(_directory(root) / 'index.json')
        if index.get('schema_version') != VERSION or not isinstance(index.get('entries'), dict):
            raise ValueError('stale index schema')
        for entry in index['entries'].values():
            if (not isinstance(entry, dict) or not isinstance(entry.get('source_hashes'), dict)
                    or not isinstance(entry.get('dependencies'), dict) or not isinstance(entry.get('policy_hash'), str)
                    or not entry.get('artifact_id')):
                raise ValueError('incomplete dependency graph')
        return index, True
    except (OSError, ValueError, TypeError, AttributeError):
        return {'schema_version': VERSION, 'entries': {}}, False


def _current_sources(sources, ids):
    hashes, provenance = {}, {}
    for sid in ids:
        if sid not in sources:
            raise WorkflowError('CONTEXT_REQUIRED_SOURCE_MISSING', f'required source {sid} is no longer registered')
        source = sources[sid]
        try:
            hasher = hashlib.sha256()
            with document_path(source).open('rb') as stream:
                while chunk := stream.read(65536):
                    hasher.update(chunk)
            hashes[sid] = hasher.hexdigest()
        except OSError as exc:
            raise WorkflowError('CONTEXT_REQUIRED_SOURCE_MISSING', f'required source {sid} is missing') from exc
        if source.get('content_hash') and source['content_hash'] != hashes[sid]:
            raise WorkflowError('CONTEXT_SOURCE_CHANGED', f'required source {sid} changed')
        provenance[sid] = {**source, 'content_hash': hashes[sid]}
    return hashes, provenance


def resolve_cached_units(root: Path, selection: dict) -> dict:
    sources, selections, policy = selection['sources'], selection['selections'], selection['policy']
    # Source locations define scope, while commits/provenance never define reusable content.
    scope = digest({'sources': {sid: {k: source[k] for k in ('root', 'path')} for sid, source in sources.items()},
                    'selections': selections, 'policy': policy, 'builder_version': VERSION})
    index, _ = _index(root)
    entry = index['entries'].get(scope)
    validation_reads = 0
    if entry:
        hashes, provenance = _current_sources(sources, entry['source_hashes'])
        validation_reads = len(hashes)
        if hashes == entry['source_hashes']:
            try:
                value = inspect_context_artifact(root, entry['artifact_id'])
                if value['source_hashes'] != hashes or value.get('dependencies') != entry.get('dependencies'):
                    raise ValueError('cache graph mismatch')
                return {**value, 'artifact_id': entry['artifact_id'],
                        'artifact_ref': str(_directory(root) / (entry['artifact_id'] + '.json')),
                        'cache_outcome': 'hit', 'source_provenance': provenance,
                        'retrieval_calls': len(hashes)}
            except (WorkflowError, KeyError, ValueError, TypeError):
                pass
    value = select_document_units(sources, selections, policy)
    hashes, provenance = _current_sources(sources, value['source_hashes'])
    if hashes != value['source_hashes']:
        raise WorkflowError('CONTEXT_SOURCE_CHANGED', 'source changed during context assembly')
    ref = store_context_artifact(root, value, {'policy': digest(policy), 'builder_version': VERSION,
        'source_hashes': hashes, 'selectors': [u['selector'] for u in value['units']], 'closure': value['dependencies']})
    index['entries'][scope] = {**ref, 'policy_hash': digest(policy), 'source_hashes': hashes,
                               'dependencies': value['dependencies']}
    _atomic_json(_directory(root) / 'index.json', index)
    return {**value, **ref, 'cache_outcome': 'miss', 'source_provenance': provenance,
            'retrieval_calls': value['retrieval_calls'] + len(hashes) + validation_reads}


def invalidate_context_artifacts(root: Path, observed_sources: dict, policy_hash: str) -> dict:
    index, valid = _index(root)
    known = {sid for entry in index['entries'].values() for sid in entry['source_hashes']}
    unknown = bool(set(observed_sources) - known)
    affected, retained = {}, {}
    for scope, entry in index['entries'].items():
        reasons = []
        if unknown:
            reasons.append('unknown-source-scope')
        if entry['policy_hash'] != policy_hash:
            reasons.append('policy-changed')
        for sid, current in sorted(observed_sources.items()):
            if sid in entry['source_hashes'] and current != entry['source_hashes'][sid]:
                reasons.append('source-changed-or-deleted:' + sid)
        if reasons:
            affected.setdefault(entry['artifact_id'], []).extend(reasons)
        else:
            retained[scope] = entry
    index['entries'] = retained
    _atomic_json(_directory(root) / 'index.json', index)
    return {'status': 'ok', 'reason_code': 'CONSERVATIVE_INVALIDATION' if unknown or not valid else 'DEPENDENCIES_CHECKED',
            'affected_ids': sorted(affected), 'reasons': {key: sorted(set(value)) for key, value in sorted(affected.items())},
            'retained_entries': len(retained), 'scope': 'retrieval-only'}
