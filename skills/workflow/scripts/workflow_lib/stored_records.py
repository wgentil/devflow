"""Typed physical records with explicit, verified logical hydration boundaries."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json

from .storage_objects import put_object, read_object
from .store import WorkflowError

MAX_RECORD_BYTES = 256 * 1024 * 1024

SOURCE_FIELDS = frozenset(('content_base64', 'before_content_base64', 'after_content_base64',
                           'text', 'diff', 'patch'))
SUMMARY_FIELDS = ('package_hash', 'schema_version', 'run_id', 'role', 'item_id', 'plan_hash',
                  'spec_hash', 'pr_id', 'head_sha', 'base_sha')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value): return hashlib.sha256(canonical(value)).hexdigest()


def _valid_package(value):
    return (isinstance(value, dict) and isinstance(value.get('package_hash'), str)
            and digest({key: item for key, item in value.items() if key != 'package_hash'}) == value['package_hash'])


def _reference(root, kind, value, *, summary=None):
    raw = value.encode('utf-8') if kind == 'source-field' else canonical(value)
    if len(raw) > MAX_RECORD_BYTES:
        raise WorkflowError('STORAGE_RECORD_LIMIT', 'Required logical record exceeds the 256 MiB materialization budget; preserve legacy authority and inspect/export it explicitly.')
    return {'record_version': 1, 'record_kind': kind, 'reference': put_object(root, kind, raw),
            'logical_sha256': hashlib.sha256(raw).hexdigest(), 'summary': summary or {}}


def store_package(root, package):
    if not _valid_package(package):
        raise WorkflowError('INVALID_PACKAGE', 'Review package body does not match its original logical hash.')
    # The object contains a physical tree so shared source fields deduplicate even
    # between distinct packages. Its physical checksum is not the package hash.
    node, _ = _pack(root, package, package_body=True)
    record = _reference(root, 'review-package', node,
                        summary={key: package[key] for key in SUMMARY_FIELDS if key in package})
    record['logical_sha256'] = digest(package)
    return record


def _pack(root, value, *, key=None, package_body=False):
    if isinstance(value, dict):
        if not package_body and _valid_package(value):
            return {'object': store_package(root, value)}, True
        result = {}; changed = False
        for name, item in value.items():
            result[name], child = _pack(root, item, key=name)
            changed |= child
        return {'map': result}, changed
    if isinstance(value, list):
        result = []; changed = False
        for item in value:
            child, altered = _pack(root, item)
            result.append(child); changed |= altered
        return result, changed
    if isinstance(value, str) and key in SOURCE_FIELDS:
        return {'object': _reference(root, 'source-field', value)}, True
    return value, False


def encode_record(root, value):
    node, changed = _pack(root, value)
    return {'record_version': 1, 'node': node} if changed else None


def _resolve(root, record):
    if (not isinstance(record, dict) or set(record) != {'record_version', 'record_kind', 'reference', 'logical_sha256', 'summary'}
            or type(record.get('record_version')) is not int or record['record_version'] != 1
            or record['record_kind'] not in {'review-package', 'source-field'}
            or not isinstance(record['summary'], dict)):
        raise WorkflowError('INVALID_STORED_RECORD', 'Unsupported or malformed typed record; preserve the root.')
    ref = record['reference']
    if ref.get('kind') != record['record_kind']:
        raise WorkflowError('INVALID_STORED_RECORD', 'Typed record and object kind disagree.')
    raw = read_object(root, ref, max_bytes=MAX_RECORD_BYTES)
    if record['record_kind'] == 'source-field':
        if hashlib.sha256(raw).hexdigest() != record['logical_sha256'] or record['summary']:
            raise WorkflowError('INVALID_STORED_RECORD', 'Source content identity differs from its record.')
        return raw.decode('utf-8')
    try: value = _unpack(root, json.loads(raw))
    except (ValueError, TypeError, KeyError) as exc:
        raise WorkflowError('INVALID_STORED_RECORD', 'Invalid package object tree.') from exc
    if (not _valid_package(value) or digest(value) != record['logical_sha256']
            or record['summary'] != {key: value[key] for key in SUMMARY_FIELDS if key in value}):
        raise WorkflowError('INVALID_PACKAGE', 'Hydrated body, routing summary or original package hash differs.')
    return value


def _unpack(root, node):
    if isinstance(node, list): return [_unpack(root, child) for child in node]
    if not isinstance(node, dict): return node
    if set(node) == {'map'} and isinstance(node['map'], dict):
        return {key: _unpack(root, value) for key, value in node['map'].items()}
    if set(node) == {'object'}: return _resolve(root, node['object'])
    raise WorkflowError('INVALID_STORED_RECORD', 'A physical record contains an unrecognized node.')


def decode_record(root, record):
    if not isinstance(record, dict) or set(record) != {'record_version', 'node'} or record['record_version'] != 1:
        raise WorkflowError('INVALID_STORED_RECORD', 'Unsupported physical record encoding.')
    return _unpack(root, record['node'])


def resolve_package(root, package):
    if isinstance(package, dict) and 'record_kind' in package:
        if package['record_kind'] != 'review-package':
            raise WorkflowError('INVALID_PACKAGE', 'A review package body is required.')
        return _resolve(root, package)
    if not _valid_package(package):
        raise WorkflowError('INVALID_PACKAGE', 'Review package body does not match its original logical hash.')
    return deepcopy(package)


def object_references(physical, *, root=None):
    """Enumerate typed references; root opts into verifying nested object trees."""
    pending = [physical]; seen = set()
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            if node.get('record_kind') in {'review-package', 'source-field'} and 'reference' in node:
                ref = node['reference']
                if ref['object_id'] not in seen:
                    seen.add(ref['object_id']); yield ref
                    if root is not None and ref['kind'] == 'review-package':
                        pending.append(json.loads(read_object(root, ref, max_bytes=MAX_RECORD_BYTES)))
            else: pending.extend(node.values())
        elif isinstance(node, list): pending.extend(node)
