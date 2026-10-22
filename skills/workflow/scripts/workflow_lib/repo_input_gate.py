"""Live specification preflight; journal replay never calls this module."""
from pathlib import Path
from uuid import uuid4

from .repo_specs import _paths, assert_repo_spec_approval, write_spec_pair
from .specs import content_hash
from .store import WorkflowError, read_state, transact


def require_current_spec(root: Path, state: dict, phase: str) -> dict:
    data = state.get('data', state)
    pair = data.get('spec_pair')
    approval = data.get('approval') or {}
    if not pair:
        spec = data.get('spec')
        if not spec or not approval.get('confirmed') or approval.get('content_hash') != content_hash(spec):
            raise WorkflowError('SPEC_NOT_APPROVED', 'approve the current specification before new work', {'phase': phase})
        return {'content_hash': content_hash(spec), 'source': 'legacy-journal'}
    if data.get('spec_approval_invalidated'):
        raise WorkflowError('SPEC_APPROVAL_STALE', 'observed specification drift requires explicit reapproval', {'phase': phase})
    try:
        registered = data.get('repositories', {}).get(pair['repo_id'])
        if not registered:
            raise WorkflowError('REPO_NOT_FOUND', 'specification repository is no longer registered')
        current = assert_repo_spec_approval(Path(registered['location']), pair)
        if not approval.get('confirmed') or any(approval.get(key) != value for key, value in pair.items()):
            raise WorkflowError('SPEC_NOT_APPROVED', 'approve the repository specification pair before new work')
    except WorkflowError as exc:
        # Persist the observation, not filesystem-dependent replay logic. Approval itself
        # remains historical evidence; only a new approval clears this marker.
        if exc.code != 'SPEC_NOT_APPROVED':
            latest = read_state(root)
            if latest['data'].get('spec_pair') == pair and not latest['data'].get('spec_approval_invalidated'):
                transact(root, latest['version'], 'spec-drift:' + uuid4().hex,
                         {'kind': 'spec.invalidated', 'payload': {'spec_approval_invalidated': {'phase': phase, 'code': exc.code}}})
        raise
    return {key: value for key, value in current.items() if key != 'spec'} | {'repo_id': pair['repo_id']}


def migrate_legacy_spec(root: Path, repo_id: str, relative_json: str, operation_id: str) -> dict:
    state = read_state(root)
    previous = state['operations'].get(operation_id)
    if previous:
        payload = previous['payload']
        if previous['kind'] != 'spec.migrated' or payload['spec_pair']['repo_id'] != repo_id or payload['spec_pair']['json_path'] != relative_json:
            raise WorkflowError('OPERATION_CONFLICT', 'migration operation ID belongs to another request')
        return payload['spec_pair']
    data = state['data']
    if data.get('spec_pair') or not isinstance(data.get('spec'), dict):
        raise WorkflowError('LEGACY_SPEC_REQUIRED', 'migration requires explicit legacy journal specification content')
    registered = data.get('repositories', {}).get(repo_id)
    if not registered:
        raise WorkflowError('REPO_NOT_FOUND', 'register the target repository before migration')
    repo = Path(registered['location'])
    paths = _paths(repo, relative_json)
    if any(path.exists() or path.is_symlink() for path in paths):
        raise WorkflowError('SPEC_TARGET_EXISTS', 'migration never overwrites either existing target file')
    pair = {'repo_id': repo_id, **write_spec_pair(repo, relative_json, data['spec'], overwrite=False)}
    transact(root, state['version'], operation_id, {'kind': 'spec.migrated', 'payload': {
        'spec_pair': pair, 'approval': None, 'spec_approval_invalidated': None}})
    return pair


def require_current_inputs(root: Path, state: dict, phase: str, run_id: str | None = None) -> dict:
    """Compatibility wrapper; callers needing refreshed state use preflight_inputs."""
    return preflight_inputs(root,state,phase,run_id)['inputs']


def preflight_inputs(root: Path, state: dict, phase: str, run_id: str | None = None) -> dict:
    """Validate once and carry transaction-returned authority through owned writes."""
    import time
    from .document_approvals import preflight_governing_inputs
    started=time.monotonic()
    spec=require_current_spec(root,state,phase)
    governed=preflight_governing_inputs(root,state,phase)
    state=governed['state'];governing=governed['receipt'];data=state.get('data',state)
    pair=data.get('spec_pair');grounding={}
    if pair:
        registered=data.get('repositories',{}).get(pair['repo_id'])
        if registered and (Path(registered['location'])/'docs/devflow-context.json').is_file():
            from .ground_interview import require_ground_interview
            grounding=require_ground_interview(Path(registered['location']))
    if run_id and governing:
        run=data.get('runs',{}).get(run_id)
        if run and run.get('governing_digest')!=governing['effective_digest']:
            raise WorkflowError('RUN_GOVERNING_INPUTS_STALE',
                'This run uses prior governing inputs; preserve it for audit and start a fresh run from the reassessed plan.')
    return {'state':state,'inputs':{'spec':spec,'governing':governing,'grounding':grounding},
            'timing':{'preflight_ms':max(0,int((time.monotonic()-started)*1000))}}
