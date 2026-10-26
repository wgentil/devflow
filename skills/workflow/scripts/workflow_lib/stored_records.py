"""Typed physical records with explicit, verified logical hydration boundaries."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json

from .storage_objects import put_object, read_object
from .store import WorkflowError

MAX_RECORD_BYTES = 256 * 1024 * 1024

SOURCE_FIELDS = frozenset(('content_base64', 'before_content_base64', 'after_content_base64',
                           'text', 'diff', 'patch'))
SUMMARY_FIELDS = ('package_hash', 'schema_version', 'run_id', 'role', 'item_id', 'plan_hash',
                  'spec_hash', 'pr_id', 'head_sha', 'base_sha')


@dataclass(frozen=True)
class StoredPackage:
    """An explicit internal handle; JSON/deepcopy never expands package history.

    Access to body fields resolves this one complete verified package. Metadata
    scans must use package_metadata instead. This is deliberately not a dict.
    """
    root: str
    record: dict
    def __deepcopy__(self,memo):return self
    def get(self,key,default=None):return require_package(self).get(key,default)
    def __getitem__(self,key):return require_package(self)[key]
    def items(self):return require_package(self).items()


def require_package(value):
    return _resolve(value.root,value.record) if isinstance(value,StoredPackage) else value


def package_metadata(value):
    return value.record['summary'] if isinstance(value,StoredPackage) else value


def dependency_links(value):
    names={'proof_id':'proof','evidence_id':'proof','package_hash':'package','finding_id':'finding',
        'source_hash':'source','content_digest':'source','artifact_hash':'artifact','artifact_id':'artifact','context_hash':'context'}
    rows=set();pending=[((),value)]
    while pending:
        path,node=pending.pop()
        if isinstance(node,dict):
            for key,item in node.items():
                if key in names and isinstance(item,str):rows.add((names[key],item,'/'.join((*path,key)),False))
                if key in {'artifacts','current_source_indexes'} and isinstance(item,dict):
                    for name,identity in item.items():
                        if isinstance(identity,str):rows.add(('artifact' if key=='artifacts' else 'source',identity,name,True))
                pending.append(((*path,key),item))
        elif isinstance(node,list):pending.extend(((*path,str(i)),item) for i,item in enumerate(node))
    return [list(row) for row in sorted(rows)]


def _package_summary(package,version=2):
    fields=SUMMARY_FIELDS if version==1 else SUMMARY_FIELDS+('input_paths',)
    summary={key:package[key] for key in fields if key in package}
    if version==2:summary['_storage_dependency_links']=dependency_links(package)
    return summary


def working_identity(root,value):
    physical=encode_record(root,value)
    if physical is None:
        node,_=_pack(root,value);physical={'record_version':1,'node':node}
    return digest(physical)


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
                        summary=_package_summary(package))
    record['record_version']=2
    record['logical_sha256'] = digest(package)
    return record


def _pack(root, value, *, key=None, package_body=False):
    if isinstance(value,StoredPackage):return {'object':deepcopy(value.record)},True
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
            or type(record.get('record_version')) is not int or record['record_version'] not in {1,2}
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
            or record['summary'] != _package_summary(value,record['record_version'])):
        raise WorkflowError('INVALID_PACKAGE', 'Hydrated body, routing summary or original package hash differs.')
    return value


def _unpack(root, node, *, packages=True):
    if isinstance(node, list): return [_unpack(root, child,packages=packages) for child in node]
    if not isinstance(node, dict): return node
    if set(node) == {'map'} and isinstance(node['map'], dict):
        return {key: _unpack(root, value,packages=packages) for key, value in node['map'].items()}
    if set(node) == {'object'}:
        record=node['object']
        if not packages and record.get('record_kind')=='review-package':
            if record.get('record_version')!=2:
                # Compatibility for pre-reference metadata; full verify retains
                # legacy identities. Newly written working rows always use v2.
                return _resolve(root,record)
            return StoredPackage(str(root),record)
        return _resolve(root, record)
    raise WorkflowError('INVALID_STORED_RECORD', 'A physical record contains an unrecognized node.')


def decode_record(root, record, *, packages=True):
    if not isinstance(record, dict) or set(record) != {'record_version', 'node'} or record['record_version'] != 1:
        raise WorkflowError('INVALID_STORED_RECORD', 'Unsupported physical record encoding.')
    return _unpack(root, record['node'],packages=packages)


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


def _string_parts(value):
    yield b'"'
    for offset in range(0,len(value),1024*1024):
        yield json.dumps(value[offset:offset+1024*1024],ensure_ascii=False)[1:-1].encode('utf-8')
    yield b'"'


def _value_parts(value):
    if isinstance(value,str): yield from _string_parts(value)
    elif isinstance(value,dict):
        yield b'{'
        for i,key in enumerate(sorted(value)):
            if i:yield b','
            yield canonical(key);yield b':';yield from _value_parts(value[key])
        yield b'}'
    elif isinstance(value,list):
        yield b'['
        for i,item in enumerate(value):
            if i:yield b','
            yield from _value_parts(item)
        yield b']'
    else: yield canonical(value)


def _node_parts(root,node):
    if isinstance(node,list):
        yield b'['
        for i,item in enumerate(node):
            if i:yield b','
            yield from _node_parts(root,item)
        yield b']';return
    if not isinstance(node,dict):yield from _value_parts(node);return
    if set(node)=={'map'} and isinstance(node['map'],dict):
        yield b'{'
        for i,key in enumerate(sorted(node['map'])):
            if i:yield b','
            yield canonical(key);yield b':';yield from _node_parts(root,node['map'][key])
        yield b'}';return
    if set(node)!={'object'}:raise WorkflowError('INVALID_STORED_RECORD','Unrecognized physical node in streamed audit.')
    record=node['object'];ref=record['reference']
    if record.get('record_version') not in {1,2} or ref.get('kind')!=record.get('record_kind') or ref.get('size_bytes',MAX_RECORD_BYTES+1)>MAX_RECORD_BYTES:
        raise WorkflowError('INVALID_STORED_RECORD','Unsupported streamed record kind or budget.')
    if record['record_kind']=='source-field':
        import codecs
        from .storage_objects import stream_object
        decoder=codecs.getincrementaldecoder('utf-8')();hasher=hashlib.sha256()
        if record.get('summary')!={}:raise WorkflowError('INVALID_STORED_RECORD','Invalid source-field summary.')
        yield b'"'
        for chunk in stream_object(root,ref):
            hasher.update(chunk);text=decoder.decode(chunk)
            if text:yield json.dumps(text,ensure_ascii=False)[1:-1].encode('utf-8')
        tail=decoder.decode(b'',final=True)
        if tail:yield json.dumps(tail,ensure_ascii=False)[1:-1].encode('utf-8')
        if hasher.hexdigest()!=record['logical_sha256']:raise WorkflowError('INVALID_STORED_RECORD','Streamed source identity differs.')
        yield b'"';return
    if record['record_kind']!='review-package':raise WorkflowError('INVALID_STORED_RECORD','Unsupported streamed object kind.')
    package=json.loads(read_object(root,ref,max_bytes=MAX_RECORD_BYTES))
    if set(package)!={'map'} or not isinstance(package['map'],dict):raise WorkflowError('INVALID_PACKAGE','Malformed streamed package body.')
    fields=package['map'];summary={key:_unpack(root,fields[key]) for key in SUMMARY_FIELDS+(('input_paths',) if record['record_version']==2 else ()) if key in fields}
    if record['record_version']==2:
        # Dependency metadata is verified against the complete logical body by
        # _resolve in full materialization; streaming verifies original hashes.
        summary['_storage_dependency_links']=record['summary'].get('_storage_dependency_links')
    if summary!=record['summary'] or 'package_hash' not in summary:raise WorkflowError('INVALID_PACKAGE','Streamed package routing summary differs.')
    full=hashlib.sha256();unsigned=hashlib.sha256();unsigned.update(b'{');full.update(b'{');yield b'{'
    unsigned_count=0
    for i,key in enumerate(sorted(fields)):
        prefix=(b',' if i else b'')+canonical(key)+b':'
        full.update(prefix);yield prefix
        included=key!='package_hash'
        if included:
            unsigned.update((b',' if unsigned_count else b'')+canonical(key)+b':');unsigned_count+=1
        for chunk in _node_parts(root,fields[key]):
            full.update(chunk)
            if included:unsigned.update(chunk)
            yield chunk
    full.update(b'}');unsigned.update(b'}')
    if full.hexdigest()!=record['logical_sha256'] or unsigned.hexdigest()!=summary['package_hash']:
        raise WorkflowError('INVALID_PACKAGE','Streamed package body differs from its logical hashes.')
    yield b'}'


def stream_cell_json(root,codec,payload,expected):
    """Yield canonical logical JSON; EOF verifies every contributing identity."""
    from .storage_objects import stream_object
    def parts():
        if codec=='json':yield from _value_parts(json.loads(payload));return
        if codec=='object':
            ref=json.loads(payload)
            if ref['size_bytes']>MAX_RECORD_BYTES:raise WorkflowError('STORAGE_OBJECT_LIMIT','Logical record exceeds audit materialization budget.')
            yield from _value_parts(json.loads(read_object(root,ref,max_bytes=MAX_RECORD_BYTES)));return
        if codec in {'run-record','run-record-object'}:
            value=json.loads(payload)
            if codec=='run-record-object':value=json.loads(read_object(root,value,max_bytes=MAX_RECORD_BYTES))
            if digest(value)!=expected:raise WorkflowError('CORRUPT_STORAGE','Working run physical identity differs.')
            yield from _node_parts(root,value['node']);return
        if codec=='archive2':
            from .run_archives import hydrate_working_detail
            run=hydrate_working_detail(root,json.loads(payload),packages=False)
            if working_identity(root,run)!=expected:raise WorkflowError('CORRUPT_STORAGE','Archived run physical identity differs.')
            node,_=_pack(root,run);yield from _node_parts(root,node);return
        if codec in {'record','record-object'}:
            value=json.loads(payload)
            if codec=='record-object':value=json.loads(read_object(root,value,max_bytes=MAX_RECORD_BYTES))
            if value.get('record_version')!=1 or set(value)!={'record_version','node'}:
                raise WorkflowError('INVALID_STORED_RECORD','Unsupported streamed physical record.')
            yield from _node_parts(root,value['node']);return
        if codec=='archive':
            from .run_archives import summary_from_record
            value=json.loads(payload);summary_from_record(value)
            if value['logical_sha256']!=expected:raise WorkflowError('INVALID_RUN_ARCHIVE','Archive logical identity differs.')
            envelope=json.loads(read_object(root,value['reference'],max_bytes=MAX_RECORD_BYTES))
            if envelope.get('archive_version')!=1:raise WorkflowError('INVALID_RUN_ARCHIVE','Unsupported streamed terminal archive.')
            if envelope['codec']=='record':
                body=envelope['body']
                if body.get('record_version')!=1:raise WorkflowError('INVALID_STORED_RECORD','Unsupported archive physical record.')
                yield from _node_parts(root,body['node'])
            elif envelope['codec']=='json':yield from _value_parts(envelope['body'])
            else:raise WorkflowError('INVALID_RUN_ARCHIVE','Unsupported streamed archive encoding.')
            return
        raise WorkflowError('CORRUPT_STORAGE','Unsupported logical JSON stream codec.')
    checksum=hashlib.sha256()
    for chunk in parts():checksum.update(chunk);yield chunk
    if codec not in {'run-record','run-record-object','archive2'} and checksum.hexdigest()!=expected:raise WorkflowError('CORRUPT_STORAGE','Streamed logical record checksum mismatch.')
