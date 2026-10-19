"""Best-effort context-byte observations; no document bodies or inferred costs."""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import sys
import time

from .document_units import canonical
from .platform_lock import exclusive_file

NUMBERS = ('document_bytes', 'envelope_bytes', 'configuration_bytes', 'turn_bytes', 'helper_calls', 'retrieval_calls', 'duration_ms')
TEXT = ('operation_id', 'operation', 'run_id', 'stage', 'work_item', 'invocation_id', 'consumer_id', 'context_mode', 'cache_outcome')


def measure_context_view(view: dict, *, operation_id: str, operation: str, duration_ms: int = 0) -> dict:
    task = view.get('task_view', view.get('brief', {}).get('task_view', view if 'units' in view else {}))
    units = task.get('changed_units', task.get('units', []))
    source_records = view.get('sources', [])
    source_records = [source for source in source_records if isinstance(source.get('text'), str)]
    if source_records:
        units = [{'id': source['path'], 'content': source['text'], 'content_hash': source['hash']} for source in source_records]
    documents = len(canonical(source_records or units)) if units else 0
    unit_records = [{'id': u['id'], 'content_hash': u['content_hash'], 'bytes': len(canonical(u.get('content', ''))) - 2}
                    for u in units if u.get('content_hash')]
    coverage = task.get('coverage', {})
    return {'operation_id': operation_id, 'operation': operation, 'run_id': view.get('run_id'), 'stage': view.get('stage'),
            'document_bytes': documents, 'envelope_bytes': max(0, len(canonical(view)) - documents),
            'helper_calls': 1, 'retrieval_calls': task.get('retrieval_calls', 0), 'duration_ms': duration_ms,
            'context_mode': view.get('context_mode', 'full' if task else 'not-context'), 'cache_outcome': task.get('cache_outcome', 'unknown'),
            'units': unit_records, 'required_ids': task.get('required_ids', []),
            'supplied_ids': coverage.get('supplied_ids', []), 'missing_required_ids': coverage.get('missing_ids', [])}


def _append(root, entry):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'context-metrics.jsonl'
    deadline = time.monotonic() + 0.05
    with (root / '.context-metrics.lock').open('a+') as lock, exclusive_file(lock, blocking=False):
        if path.is_file():
            with path.open(encoding='utf-8') as stream:
                for line in stream:
                    if time.monotonic() >= deadline or len(line.encode('utf-8')) > 65536:
                        raise ValueError('bounded telemetry deduplication scan unavailable')
                    if json.loads(line).get('operation_id') == entry['operation_id']:
                        return {'recorded': True, 'duplicate': True}
        with path.open('a', encoding='utf-8') as stream:
            stream.write(canonical(entry).decode('utf-8') + '\n')
            stream.flush()
            os.fsync(stream.fileno())
    return {'recorded': True, 'duplicate': False}


def record_context_measurement(root: Path, measurement: dict) -> dict:
    try:
        if not isinstance(measurement, dict) or any(not isinstance(measurement.get(k), str) or not measurement[k] for k in ('operation_id', 'operation')):
            return {'recorded': False, 'gap': 'invalid_measurement'}
        entry = {'schema_version': 1}
        for key in TEXT:
            if measurement.get(key) is not None:
                if not isinstance(measurement[key], str) or len(measurement[key]) > 2048:
                    raise ValueError('invalid attribution')
                entry[key] = measurement[key]
        for key in NUMBERS:
            value = measurement.get(key, 0)
            if type(value) is not int or value < 0:
                raise ValueError('invalid numeric measurement')
            entry[key] = value
        entry['units'] = []
        for unit in measurement.get('units', []):
            if (not isinstance(unit['id'], str) or not isinstance(unit['content_hash'], str)
                    or type(unit['bytes']) is not int or unit['bytes'] < 0):
                raise ValueError('invalid unit measurement')
            entry['units'].append({k: unit[k] for k in ('id', 'content_hash', 'bytes')})
        for key in ('required_ids', 'supplied_ids', 'missing_required_ids'):
            ids = measurement.get(key, [])
            if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
                raise ValueError('invalid coverage IDs')
            entry[key] = sorted(set(ids))
        usage = measurement.get('runtime_usage')
        if isinstance(usage, dict):
            entry['runtime_usage'] = {k: v for k, v in usage.items() if k in {'input_tokens', 'output_tokens', 'cached_tokens', 'total_tokens'}
                                     and type(v) is int and v >= 0}
        if len(canonical(entry)) > 65536:
            raise ValueError('measurement exceeds bounded metadata size')
        return _append(root, entry)
    except Exception as exc:
        print('devflow: context telemetry gap: ' + str(exc)[:300], file=sys.stderr)
        return {'recorded': False, 'gap': str(exc)}


def explicit_runtime_usage(usage) -> dict:
    if not isinstance(usage, dict):
        return {}
    value = usage.get('total', usage)
    if not isinstance(value, dict):
        return {}
    aliases = {'inputTokens': 'input_tokens', 'outputTokens': 'output_tokens', 'cachedInputTokens': 'cached_tokens',
               'totalTokens': 'total_tokens', 'cache_read_input_tokens': 'cached_tokens'}
    return {aliases.get(k, k): v for k, v in value.items() if aliases.get(k, k) in {'input_tokens', 'output_tokens', 'cached_tokens', 'total_tokens'}
            and type(v) is int and v >= 0}


def record_context_view(root: Path, view: dict, *, operation_id: str, operation: str, **extra) -> dict:
    try:
        event = measure_context_view(view, operation_id=operation_id, operation=operation,
                                      duration_ms=extra.pop('duration_ms', 0))
        return record_context_measurement(root, {**event, **extra})
    except Exception as exc:
        print('devflow: context telemetry gap: ' + str(exc)[:300], file=sys.stderr)
        return {'recorded': False, 'gap': str(exc)}


def context_statistics(root: Path, scope: dict) -> dict:
    totals = Counter()
    outcomes, modes, seen_units, runtime_usage = Counter(), Counter(), set(), Counter()
    required, supplied, missing, seen_operations = set(), set(), set(), set()
    gaps, event_count, usage_events = [], 0, 0
    path = Path(root) / 'context-metrics.jsonl'
    if path.is_file():
        try:
            with path.open(encoding='utf-8') as stream:
                for index, line in enumerate(stream):
                    if index >= 100000 or len(line.encode('utf-8')) > 65536:
                        gaps.append('metadata scan limit reached; totals are partial')
                        break
                    event = json.loads(line)
                    if event.get('schema_version') != 1:
                        gaps.append('unsupported metric event')
                        continue
                    if any(event.get(key) != value for key, value in scope.items() if key in TEXT and value is not None):
                        continue
                    if event['operation_id'] in seen_operations:
                        continue
                    seen_operations.add(event['operation_id']); event_count += 1
                    totals.update({key: event.get(key, 0) for key in NUMBERS})
                    outcomes[event.get('cache_outcome', 'unknown')] += 1
                    modes[event.get('context_mode', 'unknown')] += 1
                    for unit in event.get('units', []):
                        if unit['content_hash'] in seen_units:
                            totals['repeated_content_bytes'] += unit['bytes']
                        seen_units.add(unit['content_hash'])
                    required.update(event.get('required_ids', [])); supplied.update(event.get('supplied_ids', []))
                    missing.update(event.get('missing_required_ids', []))
                    if event.get('runtime_usage'):
                        usage_events += 1
                        runtime_usage.update(event['runtime_usage'])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            gaps.append('metric input unavailable; totals are partial: ' + str(exc)[:200])
    bytes_emitted = totals['document_bytes'] + totals['envelope_bytes']
    return {'schema_version': 1, 'scope': scope, 'event_count': event_count, **dict(totals),
            'helper_calls': totals['helper_calls'], 'repeated_content_bytes': totals['repeated_content_bytes'],
            'cache_outcomes': dict(sorted(outcomes.items())), 'context_modes': dict(sorted(modes.items())),
            'known_native_text_bytes': totals['configuration_bytes'] + totals['turn_bytes'],
            'required_ids': sorted(required), 'supplied_ids': sorted(supplied), 'missing_required_ids': sorted(missing | (required - supplied)),
            'semantic_omissions': 'unknown', 'actual_tokens': dict(runtime_usage) if usage_events else None,
            'usage_source': 'explicit runtime observations; partial coverage' if usage_events else 'unavailable',
            'actual_cost': None, 'cost_reason': 'Use explicit priced usage reports; context bytes do not establish cost attribution.',
            'estimated_tokens': (bytes_emitted + 3) // 4, 'token_estimate_method': 'UTF-8 bytes divided by four; estimate only',
            'measurement_coverage': 'Known emitted text/metadata only; hidden host context, unrelated reads and conversation history are unknown.',
            'latency_coverage': 'Summed operation duration_ms; overlapping calls are not end-to-end workflow latency.', 'gaps': gaps}
