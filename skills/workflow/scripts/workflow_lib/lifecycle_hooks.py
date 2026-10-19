"""Portable bounded lifecycle operations, separate from workflow authorization."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import time

from .context_artifacts import inspect_context_artifact, store_context_artifact
from .document_units import canonical, digest
from .process_transport import JsonLineProcess
from .store import WorkflowError

WORKER_PATH = Path(__file__).resolve().parents[1] / 'context_hooks.py'
OPERATIONS = {'prepare-context', 'invalidate-context', 'plan-validation', 'digest-verification', 'check-context-regressions'}


def _finish(body, name, request, started, deadline_seconds, max_bytes, required):
    body = dict(body)
    body.update(hook=name, elapsed_ms=max(0, int((time.monotonic() - started) * 1000)),
                limits={'deadline_seconds': deadline_seconds, 'max_bytes': max_bytes},
                request_hash=digest(request), output_bytes=0)
    body.setdefault('source_hashes', {})
    body.setdefault('configuration_hash', None)
    body.setdefault('artifact_refs', [])
    if body['status'] != 'allow':
        body['status'] = 'block' if required else 'advisory-error'
        if isinstance(request, dict) and isinstance(request.get('result'), dict):
            body['original_result'] = {k: v for k, v in request['result'].items()
                                       if k in {'passed', 'status', 'exit_code', 'failure', 'attempt_id', 'token'}}
    for _ in range(10):
        size = len(canonical(body))
        if body['output_bytes'] == size:
            break
        body['output_bytes'] = size
    return body


def run_lifecycle_hook(name: str, request: dict, *, deadline_seconds: float = 5,
                       max_bytes: int = 8192, required: bool = False) -> dict:
    started = time.monotonic()
    body = {'status': 'block', 'reason_code': 'HOOK_INPUT_INVALID'}
    valid = (name in OPERATIONS and isinstance(request, dict)
             and type(deadline_seconds) in (int, float) and math.isfinite(deadline_seconds) and 0 < deadline_seconds <= 3600
             and type(max_bytes) is int and 1024 <= max_bytes <= 1024 * 1024)
    if valid:
        try:
            # The transport is bounded independently of the smaller inline result budget.
            with JsonLineProcess([sys.executable, '-B', str(WORKER_PATH)], WORKER_PATH.parent,
                                 max(262144, max_bytes + 64)) as worker:
                worker.send({'name': name, 'request': request, 'max_bytes': max_bytes,
                             'deadline_seconds': deadline_seconds}, max(0.001, deadline_seconds - (time.monotonic() - started)))
                body = worker.next(max(0.001, deadline_seconds - (time.monotonic() - started)))
            if not isinstance(body, dict) or body.get('status') not in {'allow', 'block', 'advisory-error'} or not isinstance(body.get('reason_code'), str):
                raise ValueError('invalid hook response')
            if len(canonical(body)) > max_bytes:
                body = {'status': 'block', 'reason_code': 'HOOK_OUTPUT_OVERFLOW'}
        except TimeoutError:
            body = {'status': 'block', 'reason_code': 'HOOK_DEADLINE_EXCEEDED'}
        except (ValueError, EOFError, OSError, RuntimeError, TypeError):
            body = {'status': 'block', 'reason_code': 'HOOK_OUTPUT_INVALID'}
    result = _finish(body, name, request, started, deadline_seconds, max_bytes, required)
    if valid and result['output_bytes'] > max_bytes:
        result = _finish({'status': 'block', 'reason_code': 'HOOK_OUTPUT_OVERFLOW'}, name, request,
                          started, deadline_seconds, max_bytes, required)
    return result


def execute_hook(name: str, request: dict, *, max_bytes: int, deadline_seconds: float) -> dict:
    """Worker-only allowlist. No arbitrary argv, native launch or gate mutations."""
    if name not in OPERATIONS or not isinstance(request, dict) or not isinstance(request.get('root'), str):
        raise WorkflowError('HOOK_INPUT_INVALID', 'known hook and selected control root are required')
    root = Path(request['root']).expanduser().resolve()
    source_hashes, config_hash = {}, request.get('policy_hash')
    if name == 'prepare-context':
        from .store import read_state
        from .task_views import prepare_task_view, PACKAGE_ROOT
        from .documentation import load_documentation_policy
        data = read_state(root)['data']
        run = data.get('runs', {}).get(request.get('run_id'))
        if not run:
            raise WorkflowError('RUN_NOT_FOUND', 'context preparation needs a current run')
        result = prepare_task_view(root, run, request.get('envelope', {}), request.get('item_ids', []),
            stage=request.get('stage', 'implementation'), max_bytes=request.get('context_max_bytes', 20000),
            representation=request.get('representation', 'markdown'), output_mode=request.get('output_mode', 'full'))
        source_hashes = result['task_view'].get('source_hashes', {})
        config_hash = digest(load_documentation_policy(PACKAGE_ROOT))
    elif name == 'invalidate-context':
        from .context_artifacts import invalidate_context_artifacts
        if not isinstance(request.get('observed_sources'), dict) or not isinstance(config_hash, str):
            raise WorkflowError('HOOK_INPUT_INVALID', 'source identities and policy hash are required')
        source_hashes = request['observed_sources']
        result = invalidate_context_artifacts(root, source_hashes, config_hash)
    elif name == 'plan-validation':
        from .validation_plans import plan_validation
        result = plan_validation(request.get('changed_paths', []), request.get('configuration'),
                                   observed_config_hash=request.get('observed_config_hash'))
        config_hash = result.get('configuration_hash')
    elif name == 'digest-verification':
        from .failure_digests import build_failure_digest
        result = build_failure_digest(request.get('result', {}), request.get('artifacts', {}),
            max_bytes=max_bytes - 1024, deadline=time.monotonic() + deadline_seconds)
        source_hashes = result.get('source_hashes', {})
    else:
        from .context_regressions import check_context_regressions
        result = check_context_regressions(Path(request['fixture_root']))
    body = {'status': 'allow', 'reason_code': 'HOOK_COMPLETE', 'result': result,
            'source_hashes': source_hashes, 'configuration_hash': config_hash, 'artifact_refs': []}
    if len(canonical(body)) > max_bytes - 768:
        ref = store_context_artifact(root, result, {'hook': name, 'request_hash': digest(request)})
        # Keep current control-state decisions visible beside the complete artifact.
        envelope = {k: v for k, v in result.items() if k not in {'task_view', 'budget', 'units', 'content', 'stdout', 'stderr'}}
        body['result'] = {**envelope, 'full_result_artifact_id': ref['artifact_id']}
        body['artifact_refs'] = [ref]
        if len(canonical(body)) > max_bytes - 768:
            raise WorkflowError('HOOK_OUTPUT_OVERFLOW', 'mandatory hook control envelope exceeds output budget', {'artifact_refs': [ref]})
    return body


def prepared_context(root: Path, run: dict, envelope: dict, item_ids: list[str], *, stage: str,
                      max_bytes: int = 20000, representation: str = 'markdown', output_mode: str = 'full') -> dict:
    response = run_lifecycle_hook('prepare-context', {'root': str(Path(root).resolve()), 'run_id': run['id'],
        'envelope': envelope, 'item_ids': item_ids, 'stage': stage, 'context_max_bytes': max_bytes,
        'representation': representation, 'output_mode': output_mode}, required=True)
    if response['status'] != 'allow':
        raise WorkflowError(response['reason_code'], 'required context preparation failed', {
            'hook': response, **response.get('details', {})})
    result = response['result']
    if result.get('full_result_artifact_id'):
        result = inspect_context_artifact(root, result['full_result_artifact_id'])
    return result
