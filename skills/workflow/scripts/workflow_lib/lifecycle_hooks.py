"""Portable bounded lifecycle operations, separate from workflow authorization."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import time
from uuid import uuid4

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


def _dispatch_worker(name: str, request: dict, *, deadline_seconds: float = 5,
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
            body = {'status': 'block', 'reason_code': 'HOOK_DEADLINE_EXCEEDED', 'details': {'phase': 'worker', 'action': 'Retry from current inputs; retain diagnostics if bounded composition still times out.'}}
        except (ValueError, EOFError, OSError, RuntimeError, TypeError):
            body = {'status': 'block', 'reason_code': 'HOOK_OUTPUT_INVALID'}
    result = _finish(body, name, request, started, deadline_seconds, max_bytes, required)
    if valid and result['output_bytes'] > max_bytes:
        result = _finish({'status': 'block', 'reason_code': 'HOOK_OUTPUT_OVERFLOW'}, name, request,
                          started, deadline_seconds, max_bytes, required)
    if isinstance(request, dict) and isinstance(request.get('root'), str):
        from .context_metrics import record_context_measurement
        identifier = request.get('operation_id')
        identifier = identifier if isinstance(identifier, str) else uuid4().hex
        record_context_measurement(Path(request['root']), {'operation_id': identifier + ':hook:' + name,
            'operation': 'hook.' + name, 'run_id': request.get('run_id'), 'stage': request.get('stage'),
            'helper_calls': 1, 'duration_ms': result['elapsed_ms'], 'envelope_bytes': result['output_bytes']})
    return result


def execute_hook(name: str, request: dict, *, max_bytes: int, deadline_seconds: float) -> dict:
    """Worker-only allowlist. No arbitrary argv, native launch or gate mutations."""
    if name not in OPERATIONS or not isinstance(request, dict) or not isinstance(request.get('root'), str):
        raise WorkflowError('HOOK_INPUT_INVALID', 'known hook and selected control root are required')
    root = Path(request['root']).expanduser().resolve()
    source_hashes, config_hash = {}, request.get('policy_hash')
    if name == 'prepare-context':
        from .context_transport import load_preparation
        from .context_preparation import compose_prepared
        reference=request.get('preparation_ref')
        if not isinstance(reference,dict):raise WorkflowError('HOOK_INPUT_INVALID','Parent-prepared scoped context is required.')
        payload=load_preparation(root,reference,request.get('binding_hash'))
        result=compose_prepared(payload)
        source_hashes=result['task_view'].get('source_hashes',{})
        config_hash=digest(payload['policy'])
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


def _prepared_response(root,prepared,*,deadline_seconds=5,max_bytes=8192,required=True):
    from .context_transport import store_preparation,remove_preparation
    from .context_preparation import assert_preparation_current,finish_prepared
    assert_preparation_current(root,prepared,prepared._state,phase='preflight')
    reference=store_preparation(root,prepared)
    try:
        response=_dispatch_worker('prepare-context',{'root':str(Path(root).resolve()),'run_id':prepared.scope['run_id'],
            'preparation_ref':reference,'binding_hash':prepared.binding_hash},deadline_seconds=deadline_seconds,max_bytes=max_bytes,required=required)
        if response['status']=='allow':
            result=response['result']
            if result.get('full_result_artifact_id'):result=inspect_context_artifact(root,result['full_result_artifact_id'])
            assert_preparation_current(root,prepared,prepared._state)
            result=finish_prepared(prepared,result,response.get('elapsed_ms',0))
            if response['result'].get('full_result_artifact_id'):
                ref=store_context_artifact(root,result,{'hook':'prepare-context','binding_hash':prepared.binding_hash})
                response['result']={**{k:v for k,v in response['result'].items() if k!='preparation'},
                    'full_result_artifact_id':ref['artifact_id'],'preparation':result['preparation']}
                response['artifact_refs']=[ref]
            else:response['result']=result
            for _ in range(10):
                size=len(canonical(response))
                if size==response['output_bytes']:break
                response['output_bytes']=size
            if len(canonical(response))>max_bytes:
                raise WorkflowError('HOOK_OUTPUT_OVERFLOW','Prepared hook control envelope exceeds its output bound.')
        return response
    finally:remove_preparation(root,reference)


def run_lifecycle_hook(name: str, request: dict, *, deadline_seconds: float=5,max_bytes: int=8192,required: bool=False)->dict:
    if name!='prepare-context' or not isinstance(request,dict):
        return _dispatch_worker(name,request,deadline_seconds=deadline_seconds,max_bytes=max_bytes,required=required)
    started=time.monotonic()
    try:
        from .storage_access import read_current
        from .context_preparation import prepare_context
        root=Path(request['root']).resolve();state=read_current(root,run_id=request.get('run_id'),binding_id=request.get('envelope',{}).get('binding_id'));run=state['data'].get('runs',{}).get(request.get('run_id'))
        if not run:raise WorkflowError('RUN_NOT_FOUND','Context preparation needs a current run.')
        prepared=prepare_context(root,run,request.get('envelope',{}),request.get('item_ids',[]),stage=request.get('stage','implementation'),
            state=state,max_bytes=request.get('context_max_bytes',20000),representation=request.get('representation','markdown'),output_mode=request.get('output_mode','full'))
        try:return _prepared_response(root,prepared,deadline_seconds=deadline_seconds,max_bytes=max_bytes,required=required)
        finally:prepared.release()
    except (WorkflowError,KeyError,OSError,TypeError,ValueError) as exc:
        return _finish({'status':'block','reason_code':getattr(exc,'code','HOOK_INPUT_INVALID'),'details':getattr(exc,'details',{})},name,request,started,deadline_seconds,max_bytes,required)


def prepared_context(root: Path, run: dict, envelope: dict, item_ids: list[str], *, stage: str,
                      max_bytes: int=20000,representation: str='markdown',output_mode: str='full',state: dict|None=None,prepared=None,on_prepared=None)->dict:
    from .context_preparation import prepare_context,_require,normalize_stage,_accept_run,PreparedContext
    _require(not (prepared is not None and state is not None),'Supply state or prepared context, not both.')
    owns_preparation=prepared is None
    if prepared is None:prepared=prepare_context(root,run,envelope,item_ids,stage=stage,state=state,max_bytes=max_bytes,representation=representation,output_mode=output_mode)
    else:
        _require(isinstance(prepared,PreparedContext),'An internal prepared context object is required.')
        _accept_run(prepared._state['data']['runs'][run['id']],run)
        _require(prepared.scope['stage']==normalize_stage(stage) and prepared.scope['attempt_id']==(run.get('active_attempt') or {}).get('token'),'Prepared task stage or attempt differs.')
        _require(prepared.payload['envelope']=={**envelope,'preparation':prepared.payload['envelope']['preparation']}
            and prepared.scope['run_id']==run['id'] and prepared.scope['item_ids']==item_ids
            and prepared.scope['context_max_bytes']==max_bytes and prepared.scope['representation']==representation and prepared.scope['output_mode']==output_mode,
            'Prepared scope differs from this context request.')
    try:
        response=_prepared_response(root,prepared)
        if response['status']!='allow':raise WorkflowError(response['reason_code'],'Required context preparation failed.',{'phase':'composition','hook':response,**response.get('details',{})})
        result=response['result']
        if result.get('full_result_artifact_id'):result=inspect_context_artifact(root,result['full_result_artifact_id'])
        from .context_preparation import assert_preparation_current
        assert_preparation_current(root,prepared,prepared._state)
        if on_prepared is not None:
            on_prepared(prepared)
            owns_preparation=False # The internal dispatcher now owns its lease.
        return result
    finally:
        if owns_preparation:prepared.release()


def verification_projection(root: Path, result: dict, *, report_format: str = 'json') -> dict:
    original = result.get('proof', result)
    response = run_lifecycle_hook('digest-verification', {'root': str(Path(root).resolve()),
        'result': {**original, 'report_format': report_format}, 'artifacts': {'root': str(Path(root).resolve())}})
    return {**result, 'failure_digest': response}
