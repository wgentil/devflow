"""Advisory, exact-scope context checkpoints; no workflow state mutations."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from .context_artifacts import _read
from .document_units import digest
from .store import WorkflowError, _atomic_json

SCOPE_FIELDS = ('consumer_id', 'run_id', 'binding_id', 'session_id', 'revision', 'stage', 'role', 'task_ids')


def project_checkpoint(root: Path, full_view: dict, scope: dict, *, since: str | None = None,
                       recovery_reason: str | None = None) -> dict:
    scope = {key: scope.get(key) for key in SCOPE_FIELDS}
    scope['task_ids'] = sorted(set(scope.get('task_ids') or []))
    path = Path(root).resolve() / 'context-checkpoints'
    if path.is_symlink():
        raise WorkflowError('CONTEXT_CHECKPOINT_INVALID', 'checkpoint directory must remain in the selected control root')
    path.mkdir(parents=True, exist_ok=True)
    snapshot = {'schema_version': 1, 'scope': scope, 'view': full_view}
    identifier = digest(snapshot)
    prior = None
    reason = recovery_reason or ('FULL_REQUESTED' if not since else 'CHECKPOINT_UNAVAILABLE')
    if not scope['consumer_id']:
        reason = 'CONSUMER_ID_REQUIRED'
    elif since and not recovery_reason and isinstance(since, str) and re.fullmatch(r'[0-9a-f]{64}', since):
        try:
            candidate = _read(path / (since + '.json'))
            if digest(candidate) != since or candidate['schema_version'] != 1:
                raise ValueError('checkpoint identity mismatch')
            if not isinstance(candidate['view']['task_view']['units'], list):
                raise ValueError('checkpoint does not contain a full document view')
            if candidate['scope'] != scope:
                reason = 'SCOPE_CHANGED'
            else:
                prior = candidate['view']
        except (OSError, KeyError, ValueError, TypeError):
            reason = 'CHECKPOINT_UNAVAILABLE'
    _atomic_json(path / (identifier + '.json'), snapshot)
    result = deepcopy(full_view)
    result['context_mode'] = 'full'
    result['checkpoint'] = {'id': identifier, 'base_id': None, 'scope_hash': digest(scope), 'reason_code': reason}
    if prior is not None:
        old = {unit['id']: unit for unit in prior['task_view']['units']}
        new = {unit['id']: unit for unit in full_view['task_view']['units']}
        result['context_mode'] = 'delta'
        result['task_view'] = {key: deepcopy(value) for key, value in full_view['task_view'].items() if key != 'units'}
        result['task_view'].update(changed_units=[new[key] for key in new if old.get(key) != new[key]],
                                   removed_ids=sorted(old.keys() - new.keys()), unit_order=list(new))
        result['checkpoint'].update(base_id=since, reason_code='SAME_SCOPE_DELTA',
                                     base_document_hash=digest(prior['task_view']),
                                     current_document_hash=digest(full_view['task_view']))
    return result


def checkpoint_read(root: Path, view: dict, scope: dict, *, since: str | None = None,
                     full: bool = False, recovery_reason: str | None = None) -> dict:
    if since and (full or 'units' not in view['task_view']):
        raise WorkflowError('CONTEXT_OPTIONS_INVALID', 'since-checkpoint conflicts with full-context/reference output')
    result = project_checkpoint(root, view, scope, since=since,
                                 recovery_reason=recovery_reason or ('FULL_REQUESTED' if full else None))
    if view.get('budget', {}).get('max_bytes'):
        from .briefs import _size_and_estimate
        limit = view['budget']['max_bytes']
        _size_and_estimate(result, limit, view['budget'].get('optional_omitted', []))
        if result['budget']['serialized_bytes'] > limit:
            raise WorkflowError('CONTEXT_BUDGET_EXCEEDED', 'checkpoint envelope exceeds context budget', {
                'required_bytes': result['budget']['serialized_bytes'], 'max_bytes': limit,
                'action': 'Rescope or explicitly increase max-bytes.',
                'artifact_refs': [view['task_view'].get('artifact_ref')]})
    return result


def apply_context_delta(base: dict, delta: dict) -> dict:
    try:
        checkpoint = delta['checkpoint']
        if (delta['context_mode'] != 'delta' or base['checkpoint']['id'] != checkpoint['base_id']
                or base['checkpoint']['scope_hash'] != checkpoint['scope_hash']
                or digest(base['task_view']) != checkpoint['base_document_hash']):
            raise ValueError('delta base identity mismatch')
        units = {unit['id']: deepcopy(unit) for unit in base['task_view']['units']}
        for identifier in delta['task_view']['removed_ids']:
            units.pop(identifier)
        units.update({unit['id']: deepcopy(unit) for unit in delta['task_view']['changed_units']})
        order = delta['task_view']['unit_order']
        if len(order) != len(set(order)) or set(order) != set(units):
            raise ValueError('unit order does not match reconstructed units')
        view = {key: deepcopy(value) for key, value in delta['task_view'].items()
                if key not in {'changed_units', 'removed_ids', 'unit_order'}}
        view['units'] = [units[key] for key in order]
        if digest(view) != checkpoint['current_document_hash']:
            raise ValueError('delta reconstruction identity mismatch')
        return {**deepcopy(delta), 'task_view': view, 'context_mode': 'full'}
    except (KeyError, TypeError, ValueError) as exc:
        raise WorkflowError('CONTEXT_DELTA_INVALID', 'delta cannot reconstruct its exact current document view') from exc
