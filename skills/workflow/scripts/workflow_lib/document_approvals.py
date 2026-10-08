"""Live policy preflight and exact-diff human evidence; replay is filesystem free."""
from pathlib import Path
import base64
import difflib
import hashlib
import json
import subprocess
from uuid import uuid4

from .governing_docs import _git, _path, resolve_governing_docs, canonical_document_bytes
from .store import WorkflowError, read_state, transact


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _repository(data, repo_id):
    registered = data.get('repositories', {}).get(repo_id)
    if not registered:
        raise WorkflowError('REPO_NOT_FOUND', 'register the owning repository')
    return Path(registered['location']).resolve()


def _snapshot(repo, paths, data=None, repo_id=None):
    records = {}
    for path in sorted(set(paths)):
        target = _path(repo, path)
        previous = subprocess.run(['git', '-C', str(repo), 'show', f'HEAD:{path}'], capture_output=True, timeout=30)
        before = previous.stdout if previous.returncode == 0 else b''
        accepted = (data or {}).get('governing_input_receipt', {}).get('files', {}).get(str(repo_id) + ':' + path)
        before_exists = previous.returncode == 0
        if accepted:
            if 'content_base64' in accepted:
                before = base64.b64decode(accepted['content_base64'])
                before_exists = accepted.get('exists', True)
            elif _digest(before) != accepted['content_digest']:
                raise WorkflowError('GOVERNING_BASELINE_UNAVAILABLE', 'accepted before image is unavailable; do not approve an empty replacement diff')
        after = canonical_document_bytes(target.read_bytes(), baseline=before) if target.exists() else b''
        diff = ''.join(difflib.unified_diff(before.decode('utf-8', errors='surrogateescape').splitlines(True), after.decode('utf-8', errors='surrogateescape').splitlines(True),
                                          fromfile='a/' + path, tofile='b/' + path))
        records[path] = {'before_hash': _digest(before), 'after_hash': _digest(after),
                         'before_exists': before_exists, 'after_exists': target.exists(), 'diff': diff,
                         'before_content_base64': base64.b64encode(before).decode('ascii'),
                         'after_content_base64': base64.b64encode(after).decode('ascii')}
    return records


def propose_document_change(root: Path, repo_id: str, paths: list[str]) -> dict:
    state = read_state(root)
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) for p in paths):
        raise WorkflowError('INVALID_DOCUMENT_PROPOSAL', 'nonempty document paths are required')
    records = _snapshot(_repository(state['data'], repo_id), paths, state['data'], repo_id)
    proposal = {'repo_id': repo_id, 'files': records,
                'diff_digest': _digest(json.dumps(records, sort_keys=True).encode())}
    proposal['proposal_hash'] = _digest(json.dumps(proposal, sort_keys=True).encode())
    transact(root, state['version'], 'document-proposal:' + proposal['proposal_hash'],
             {'kind': 'document.proposed', 'payload': {'proposal': proposal}})
    return proposal


def approve_document_change(root: Path, proposal_hash: str, actor_id: str) -> dict:
    state = read_state(root)
    proposal = state['data'].get('document_proposals', {}).get(proposal_hash)
    if not proposal:
        raise WorkflowError('DOCUMENT_APPROVAL_REQUIRED', 'existing exact proposal and human actor are required')
    approval = {'proposal_hash': proposal_hash, 'repo_id': proposal['repo_id'], 'actor_id': actor_id,
                'diff_digest': proposal['diff_digest']}
    previous = state['operations'].get('document-approval:' + proposal_hash)
    if previous is not None:
        if previous['kind'] != 'document.approved' or previous['payload'] != {'approval': approval}:
            raise WorkflowError('OPERATION_CONFLICT', 'document approval retry differs from the committed request')
        return approval
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise WorkflowError('DOCUMENT_APPROVAL_REQUIRED', 'human actor is required')
    current = _snapshot(_repository(state['data'], proposal['repo_id']), list(proposal['files']), state['data'], proposal['repo_id'])
    if current != proposal['files']:
        raise WorkflowError('DOCUMENT_PROPOSAL_STALE', 'review a new exact diff before approval')
    transact(root, state['version'], 'document-approval:' + proposal_hash,
             {'kind': 'document.approved', 'payload': {'approval': approval}})
    return approval


def require_current_governing_inputs(root: Path, state: dict, phase: str) -> dict:
    data = state.get('data', state)
    pair = data.get('spec_pair')
    if not pair:
        return {}
    project_id = pair['repo_id']
    project = _repository(data, project_id)
    if not (project / 'docs/devflow-context.json').exists():
        if data.get('governing_input_receipt'):
            raise WorkflowError('GOVERNING_INPUT_DRIFT', 'governing manifest was removed')
        return {}
    try:
        manifest = json.loads((project / 'docs/devflow-context.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise WorkflowError('INVALID_GOVERNING_DOCS', 'cannot read project governing manifest') from exc
    if not isinstance(manifest, dict):
        raise WorkflowError('INVALID_GOVERNING_DOCS', 'project manifest must be an object')
    org = manifest.get('org')
    org_id = None
    if org is not None:
        if not isinstance(org, dict) or not all(isinstance(org.get(k), str) and org[k] for k in ('id', 'url')):
            raise WorkflowError('INVALID_GOVERNING_DOCS', 'organization requires stable id and Git URL')
        for key, registration in data.get('repositories', {}).items():
            location = Path(registration['location']).resolve()
            if key == org['id'] or str(location) == org['url'] or _git(location, 'remote', 'get-url', 'origin').stdout.strip() == org['url']:
                org_id = key
                break
        if org_id is None:
            raise WorkflowError('GOVERNING_SOURCE_UNAVAILABLE', 'register the organization checkout')
    org_repo = _repository(data, org_id) if org_id else None
    resolved = resolve_governing_docs(project, org_repo)
    decisions = manifest.get('irrelevance_decisions', [])
    if (not isinstance(decisions, list) or any(not isinstance(d, dict)
            or d.get('rule_id') not in resolved['rules'] or not isinstance(d.get('reason'), str)
            or not d['reason'].strip() for d in decisions)):
        raise WorkflowError('INVALID_GOVERNING_DOCS', 'irrelevance decisions require existing rule_id and reason')
    excluded = {d['rule_id'] for d in decisions}
    applicable = {k: v for k, v in resolved['rules'].items() if k not in excluded}
    semantic = {k: {field: v[field] for field in ('category', 'content', 'sealed')} for k, v in applicable.items()}
    effective_digest = _digest(json.dumps(semantic, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())
    validated_digest = data.get('plan_validation', {}).get('governing_digest')
    if data.get('plan_validation') and validated_digest != effective_digest and not data.get('governing_reassessment_required'):
        latest = read_state(root)
        transact(root, latest['version'], 'governing-reassessment:' + uuid4().hex,
                 {'kind': 'governing.reassessment.required', 'payload': {
                     'previous_digest': validated_digest, 'effective_digest': effective_digest}})
    sources = {project_id: (project, {'docs/devflow-context.json'})}
    if org_id:
        sources[org_id] = (org_repo, {'docs/devflow-org.json'})
    for rule in applicable.values():
        provenance = rule['provenance']
        owner = org_id if provenance['source'] == 'org' else project_id
        sources[owner][1].add(provenance['path'])
    files = {}
    for owner, (repo, paths) in sources.items():
        for path, record in _snapshot(repo, list(paths), data, owner).items():
            key = owner + ':' + path
            files[key] = {'repo_id': owner, 'path': path, 'content_digest': record['after_hash'],
                          'git_head': _git(repo, 'rev-parse', 'HEAD').stdout.strip(),
                          'content_base64': record['after_content_base64'], 'exists': record['after_exists']}
            changed = (record['before_hash'] != record['after_hash']
                       or record['before_exists'] != record['after_exists'])
            if changed:
                approved = any(p['repo_id'] == owner and path in p['files']
                    and p['files'][path] == record
                    and p['proposal_hash'] in data.get('document_approvals', {})
                    for p in data.get('document_proposals', {}).values())
                if not approved:
                    raise WorkflowError('DOCUMENT_APPROVAL_REQUIRED', 'governing edit requires separate exact-diff human approval',
                                        {'phase': phase, 'repo_id': owner, 'path': path})
    receipt = {'effective_digest': effective_digest, 'files': files,
               'applicable_rule_ids': sorted(applicable), 'irrelevance_decisions': manifest.get('irrelevance_decisions', [])}
    if receipt != data.get('governing_input_receipt'):
        latest = read_state(root)
        transact(root, latest['version'], 'governing-input:' + uuid4().hex,
                 {'kind': 'governing.inputs.recorded', 'payload': {'receipt': receipt}})
    latest = read_state(root)['data']
    if latest.get('governing_reassessment_required') and phase != 'plan-validation':
        raise WorkflowError('GOVERNING_REASSESSMENT_REQUIRED',
                            'approve changed documents, reassess plan and verification impact, then explicitly revalidate the plan')
    return receipt
