"""Explicit, immutable replay-policy recovery, separate from original events.

Inspection reads structural history. Validation and publication use a consistent
owned copy under the control lock; no reducer reads files or guesses a policy.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from .document_units import digest
from .store import WorkflowError, _exclusive, HOST_CONTEXT
from .storage_format import confined_path, detect_layout, DATABASE_FILE
from .issue_run_contracts import replay_policy_context
from .platform_lock import sync_directory

LIMIT = 16 * 1024 * 1024


def fail(message, code='ISSUE_RECOVERY_INVALID'):
    raise WorkflowError(code, message)


def _read_json(path):
    with path.open('rb') as stream: raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT: fail('Recovery metadata exceeds its 16 MiB limit.')
    try: return json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise WorkflowError('ISSUE_RECOVERY_INVALID', 'Invalid recovery JSON.') from exc


def raw_history(root):
    """Structural checks without reducing the historical run-creation event."""
    root = Path(root).resolve(); layout = detect_layout(root)
    events = []; raw_hashes = {}
    if layout['layout'] == 'v2':
        from . import sqlite_store as sql
        with sql.connection(root) as conn:
            for seq, op, codec, payload, checksum in conn.execute(
                    'SELECT sequence,operation_id,codec,payload,event_hash FROM events ORDER BY sequence'):
                event = sql._decode(root, codec, payload, checksum)
                if event.get('sequence') != seq or event.get('operation_id') != op:
                    fail('Indexed event identity differs from the original record.')
                events.append(event)
            for seq, name, raw_hash in conn.execute('SELECT sequence,name,raw_hash FROM raw_events'):
                if name != f'{seq:08d}.json': fail('Original raw-event name differs.')
                raw_hashes[str(seq)] = raw_hash
            if len(events) != sql._meta(conn, 'head'): fail('Indexed head differs from event history.')
    elif layout['layout'] == 'legacy':
        directory = confined_path(root, 'events')
        paths = sorted(directory.glob('[0-9]*.json'))
        for position, path in enumerate(paths, 1):
            path = confined_path(root, path.relative_to(root).as_posix())
            if path.name != f'{position:08d}.json': fail('Event filenames are not contiguous.')
            raw = path.read_bytes()
            try: events.append(json.loads(raw))
            except ValueError as exc: raise WorkflowError('CORRUPT_STATE', 'Invalid original event JSON.') from exc
            raw_hashes[str(position)] = hashlib.sha256(raw).hexdigest()
        if paths != sorted(directory.glob('[0-9]*.json')): fail('History advanced during inspection.', 'ISSUE_RECOVERY_STALE')
    else:
        fail('Recovery needs a complete existing legacy or v2 control root.')
    seen = set()
    for sequence, event in enumerate(events, 1):
        if (not isinstance(event, dict) or event.get('schema_version') != 1
                or type(event.get('sequence')) is not int or event['sequence'] != sequence
                or not isinstance(event.get('operation_id'), str) or not event['operation_id']
                or event['operation_id'] in seen or not isinstance(event.get('kind'), str)
                or not isinstance(event.get('payload'), dict)):
            fail('Original event continuity, schema or operation identity is invalid.')
        seen.add(event['operation_id'])
    return events, raw_hashes


def binding(events, raw_hashes):
    return {'schema_version': 1, 'head': len(events), 'stream_digest': digest(events),
            'raw_hashes': raw_hashes}


def _check_prefix(anchor, events, raw_hashes):
    if not isinstance(anchor, dict) or set(anchor) != {'schema_version','head','stream_digest','raw_hashes'}:
        fail('Exact inspected history binding required.')
    head = anchor['head']
    if type(head) is not int or head < 1 or head > len(events) or anchor['schema_version'] != 1:
        fail('Inspected history no longer exists.', 'ISSUE_RECOVERY_STALE')
    if digest(events[:head]) != anchor['stream_digest'] or not isinstance(anchor['raw_hashes'], dict):
        fail('Inspected history prefix changed.', 'ISSUE_RECOVERY_STALE')
    for sequence, checksum in anchor['raw_hashes'].items():
        if raw_hashes.get(sequence) != checksum:
            fail('Original event bytes changed or disappeared.', 'ISSUE_RECOVERY_STALE')


def _starts(events):
    return {digest(event): event for event in events
        if event['kind'] == 'domain.issues.start'
        and event['payload'].get('request', {}).get('intent') == 'build'
        and 'run_contract' not in event['payload']['request']}


def _request(request):
    keys = {'inspection','selections','actor_id','operation_id','confirmed','provenance'}
    if not isinstance(request, dict) or set(request) != keys or request['confirmed'] is not True:
        fail('Explicit confirmed recovery request required; neither policy is preselected.')
    if any(not isinstance(request[k], str) or not request[k].strip() for k in ('actor_id','operation_id')):
        fail('Explicit actor and operation identity required.')
    provenance = request['provenance']
    if (not isinstance(provenance, dict) or set(provenance) != {'kind','ref'}
            or provenance['kind'] != 'user-message' or not isinstance(provenance['ref'], str) or not provenance['ref'].strip()):
        fail('Recovery requires the reference to the user policy choice.')
    selections = request['selections']
    if not isinstance(selections, list) or not selections: fail('Select each unresolved issue-build policy explicitly.')
    result = {}
    for row in selections:
        if (not isinstance(row, dict) or set(row) != {'event_digest','choice'}
                or not isinstance(row['event_digest'], str) or len(row['event_digest']) != 64
                or row['event_digest'] in result or row['choice'] not in ('legacy','v0.3.18')):
            fail('Unique event-bound legacy or v0.3.18 choices required.')
        result[row['event_digest']] = row['choice']
    return result


def manifest_body(request, validation):
    return {'schema_version': 1, 'request': request, 'validation': validation}


def _manifests(root):
    directory = confined_path(root, 'replay-recovery')
    if not directory.exists(): return []
    return sorted(directory.glob('*.json'))


def load_selections(root, events=None, raw_hashes=None):
    root = Path(root).resolve()
    files = _manifests(root)
    if not files: return {}
    if events is None: events, raw_hashes = raw_history(root)
    starts = _starts(events); selected = {}
    for file in files:
        file = confined_path(root, file.relative_to(Path(root)).as_posix())
        record = _read_json(file)
        if not isinstance(record, dict) or set(record) != {'body','sha256'} or digest(record['body']) != record['sha256']:
            fail('Recovery manifest checksum is invalid.')
        body = record['body']
        if set(body) != {'schema_version','request','validation'} or body['schema_version'] != 1:
            fail('Unknown recovery manifest schema.')
        request = body['request']; choices = _request(request)
        if file.stem != hashlib.sha256(request['operation_id'].encode()).hexdigest(): fail('Recovery operation filename differs.')
        _check_prefix(request['inspection'], events, raw_hashes)
        expected = {'schema_version': 1, 'request_hash': digest(request), 'replay_head': request['inspection']['head'],
                    'selections': choices, 'status': 'validated'}
        if body['validation'] != expected: fail('Recovery validation receipt differs.')
        for key, choice in choices.items():
            if key not in starts or starts[key]['sequence'] > request['inspection']['head'] or key in selected:
                fail('Recovery must bind one immutable decision to an original issue start.')
            selected[key] = choice
    return selected


@contextmanager
def historical_context(root):
    # Nested temporary replay contexts used by validation remain authoritative.
    selected = load_selections(Path(root))
    with replay_policy_context(selected): yield


def inspect_replay_recovery(root):
    root = Path(root).resolve(); events, hashes = raw_history(root)
    chosen = load_selections(root, events, hashes)
    return {'binding': binding(events, hashes), 'unresolved': [
        {'sequence': event['sequence'], 'operation_id': event['operation_id'], 'event_digest': key,
         'group_id': event['payload']['request'].get('group_id')}
        for key, event in _starts(events).items() if key not in chosen]}


def publish_manifest(root, request, validation):
    directory = confined_path(root, 'replay-recovery', create_parents=True)
    directory.mkdir(exist_ok=True)
    file = confined_path(root, 'replay-recovery/' + hashlib.sha256(request['operation_id'].encode()).hexdigest() + '.json')
    record = {'body': manifest_body(request, validation)}; record['sha256'] = digest(record['body'])
    raw = (json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()
    if len(raw) > LIMIT: fail('Recovery manifest exceeds its metadata limit.')
    fd, temporary = tempfile.mkstemp(prefix='.pending-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'wb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, file)  # Atomic no-replacement publication.
        sync_directory(directory)
    finally: Path(temporary).unlink(missing_ok=True)


def _validated_copy(root, request):
    choices = _request(request)
    events, hashes = raw_history(root)
    if binding(events, hashes) != request['inspection']: fail('Recovery inspection is stale.', 'ISSUE_RECOVERY_STALE')
    previous = load_selections(root, events, hashes)
    if set(choices) != set(_starts(events)) - set(previous): fail('Choose every unresolved start exactly once.')
    if any(event['operation_id'] == request['operation_id'] for event in events):
        fail('Recovery operation belongs to logical history.', 'OPERATION_CONFLICT')
    validation = {'schema_version': 1, 'request_hash': digest(request), 'replay_head': len(events),
                  'selections': choices, 'status': 'validated'}
    from .storage_backups import source_files, _copy_file, sqlite_backup
    from .storage_maintenance import verify_store
    with tempfile.TemporaryDirectory(prefix='devflow-issue-recovery-') as temporary:
        copy = Path(temporary) / 'control'; copy.mkdir()
        for relative, source in source_files(root):
            # A completed backup manifest describes its original files, not this owned validation copy.
            if relative == 'backup.json': continue
            target = confined_path(copy, relative, create_parents=True)
            if relative == DATABASE_FILE: sqlite_backup(source, target)
            else: _copy_file(source, target)
        publish_manifest(copy, request, validation)
        result = verify_store(copy, full=True)
        if not result.get('valid'): fail('Complete copy replay failed: ' + '; '.join(result.get('errors', [])))
    # Check source identity again even though cooperating writers hold the same lock.
    after, after_hashes = raw_history(root)
    if binding(after, after_hashes) != request['inspection']: fail('Source changed during validation.', 'ISSUE_RECOVERY_STALE')
    return validation


def _unbound():
    if HOST_CONTEXT.get() is not None:
        fail('Recovery requires the explicit unbound operator path.', 'ISSUE_RECOVERY_OPERATOR_REQUIRED')


def validate_replay_recovery(root, request):
    _unbound(); root = Path(root).resolve()
    with _exclusive(root): return _validated_copy(root, request)


def apply_replay_recovery(root, request):
    _unbound(); root = Path(root).resolve()
    if not isinstance(request, dict) or 'validation' not in request: fail('Successful copy-validation receipt required.')
    supplied = request['validation']; original = {k: v for k, v in request.items() if k != 'validation'}
    _request(original)
    with _exclusive(root):
        file = confined_path(root, 'replay-recovery/' + hashlib.sha256(original['operation_id'].encode()).hexdigest() + '.json')
        if file.exists():
            load_selections(root)
            record = _read_json(file)['body']
            if record != manifest_body(original, supplied): fail('Recovery operation has different input.', 'OPERATION_CONFLICT')
            return {'completed': True, 'replayed': True, 'validation': record['validation']}
        actual = _validated_copy(root, original)
        if supplied != actual: fail('Validation receipt does not match the exact recovery request.')
        publish_manifest(root, original, actual)
        return {'completed': True, 'replayed': False, 'validation': actual}
