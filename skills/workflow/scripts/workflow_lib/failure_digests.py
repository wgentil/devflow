"""Bounded deterministic navigation over original verification evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

from .document_units import canonical
from .evidence import _report
from .git_paths import resolve_repo_path
from .store import WorkflowError

MAX_READ_BYTES = 1_048_576
OUTCOMES = ('failed', 'error', 'skipped', 'passed')


def build_failure_digest(result: dict, artifacts: dict, *, max_bytes: int = 8192, deadline: float | None = None) -> dict:
    original = {key: result[key] for key in ('passed', 'status', 'exit_code', 'failure', 'token', 'attempt_id', 'id',
                'run_id', 'item_id', 'output_hash', 'report_hash') if key in result}
    refs = {key: result[key] for key in ('stdout_ref', 'stderr_ref', 'report_ref') if result.get(key)}
    value = {'status': 'unavailable', 'reason_code': 'REPORT_UNAVAILABLE', 'original_result': original,
             'counts': result.get('test_counts'), 'affected_ids': [], 'groups': [], 'artifact_refs': refs,
             'omissions': [], 'source_hashes': {}, 'purpose': 'Navigation only; original evidence and verdict remain authoritative.'}
    if type(max_bytes) is not int or max_bytes < 1024:
        raise WorkflowError('DIGEST_BUDGET_INVALID', 'digest output budget must be at least 1024 bytes')
    deadline = deadline if deadline is not None else time.monotonic() + 5
    outputs, complete = {}, True
    try:
        for key, relative in refs.items():
            if time.monotonic() >= deadline:
                raise TimeoutError('digest deadline exceeded')
            root = Path(artifacts['root']).resolve()
            path = resolve_repo_path(root, relative)
            if path.is_symlink():
                raise ValueError('symlink evidence')
            with path.open('rb') as stream:
                raw = stream.read(MAX_READ_BYTES + 1)
            if len(raw) > MAX_READ_BYTES:
                complete = False
                value['omissions'].append(key + ': read limit exceeded; complete evidence remains referenced')
                raw = raw[:MAX_READ_BYTES]
            else:
                actual_hash = hashlib.sha256(raw).hexdigest()
                # Existing raw artifacts encode their complete hash in their path.
                match = re.fullmatch(r'artifacts/sha256/([0-9a-f]{2})/([0-9a-f]{62})', relative)
                if match and actual_hash != match[1] + match[2]:
                    raise ValueError('evidence content hash mismatch')
                value['source_hashes'][key] = actual_hash
            outputs[key] = raw.decode('utf-8', errors='replace')
        if time.monotonic() >= deadline:
            raise TimeoutError('digest deadline exceeded')
        outcomes = None
        if complete and outputs:
            try:
                outcomes = _report(outputs.get('stdout_ref', ''), outputs.get('stderr_ref', ''), result.get('report_format', 'json'))
                if not outcomes:
                    outcomes = None
            except WorkflowError:
                pass
        if outcomes is not None:
            value['counts'] = {kind: sum(outcome == kind for outcome in outcomes.values()) for kind in OUTCOMES}
            value['affected_ids'] = sorted(identifier for identifier, outcome in outcomes.items() if outcome in {'failed', 'error', 'skipped'})
            messages = {}
            try:
                report = json.loads(outputs.get('stdout_ref', ''))
                messages = {item['id']: str(item.get('message', item.get('error', '')))[:2048] for item in report['tests']}
            except (ValueError, TypeError, KeyError):
                try:
                    report = ET.fromstring(outputs.get('stdout_ref', ''))
                    for case in report.findall('.//testcase'):
                        identifier = '.'.join(part for part in (case.get('classname'), case.get('name')) if part)
                        messages[identifier] = '\n'.join(''.join(child.itertext()) for child in case if child.tag in {'failure', 'error', 'skipped'})[:2048]
                except ET.ParseError:
                    pass
            grouped = {}
            for identifier in value['affected_ids']:
                outcome = outcomes[identifier]
                excerpt = messages.get(identifier) or outputs.get('stderr_ref', '')[-2048:] or outcome
                grouped.setdefault((outcome, excerpt), []).append(identifier)
            value['groups'] = [{'outcome': outcome, 'excerpt': excerpt, 'ids': ids, 'count': len(ids)}
                               for (outcome, excerpt), ids in sorted(grouped.items())]
            value.update(status='available', reason_code='STRUCTURED_REPORT')
        elif isinstance(result.get('finding_ids'), list):
            value.update(status='available', reason_code='GATE_FINDINGS', affected_ids=sorted(result['finding_ids']),
                counts={'findings': result.get('finding_count', len(result['finding_ids']))})
        elif value['counts'] is not None:
            value.update(status='available', reason_code='RECORDED_TOTALS')
        else:
            value['omissions'].append('Structured totals unavailable; no zero-failure inference was made.')
            if outputs.get('stderr_ref'):
                value['groups'] = [{'outcome': 'unavailable', 'ids': [], 'count': None,
                                    'excerpt': outputs['stderr_ref'][-2048:]}]
    except (OSError, ValueError, KeyError, TypeError, TimeoutError):
        value.update(status='unavailable', reason_code='DIGEST_INPUT_UNAVAILABLE')
        value['omissions'].append('Details unavailable within bounds; inspect original evidence.')
    while len(canonical(value)) > max_bytes and value['groups']:
        value['groups'].pop()
        if 'Grouped detail omitted to fit output budget; inspect complete evidence.' not in value['omissions']:
            value['omissions'].append('Grouped detail omitted to fit output budget; inspect complete evidence.')
    if len(canonical(value)) > max_bytes:
        value['affected_ids'] = []
        value['omissions'].append('Individual IDs remain in complete evidence.')
    if len(canonical(value)) > max_bytes:
        raise WorkflowError('DIGEST_OUTPUT_OVERFLOW', 'mandatory failure digest metadata exceeds output budget', {'artifact_refs': refs})
    return value
