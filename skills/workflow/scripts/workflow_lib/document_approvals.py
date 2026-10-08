"""Live policy preflight and exact-diff human evidence; replay is filesystem free."""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess
from uuid import uuid4

from .governing_docs import _git, _path, resolve_governing_docs
from .store import WorkflowError, read_state, transact


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _repository(data, repo_id):
    registered = data.get('repositories', {}).get(repo_id)
    if not registered:
        raise WorkflowError('REPO_NOT_FOUND', 'register the owning repository')
    return Path(registered['location']).resolve()


def _snapshot(repo, paths):
    records = {}
    for path in sorted(set(paths)):
        target = _path(repo, path)
        after = target.read_bytes() if target.exists() else b''
        previous = subprocess.run(['git', '-C', str(repo), 'show', f'HEAD:{path}'], capture_output=True, timeout=30)
        before = previous.stdout if previous.returncode == 0 else b''
        diff = ''.join(difflib.unified_diff(before.decode('utf-8', errors='surrogateescape').splitlines(True), after.decode('utf-8', errors='surrogateescape').splitlines(True),
                                          fromfile='a/' + path, tofile='b/' + path))
        records[path] = {'before_hash': _digest(before), 'after_hash': _digest(after),
                         'before_exists': previous.returncode == 0, 'after_exists': target.exists(), 'diff': diff}
    return records


def propose_document_change(root: Path, repo_id: str, paths: list[str]) -> dict:
    state = read_state(root)
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) for p in paths):
        raise WorkflowError('INVALID_DOCUMENT_PROPOSAL', 'nonempty document paths are required')
    records = _snapshot(_repository(state['data'], repo_id), paths)
    proposal = {'repo_id': repo_id, 'files': records,
                'diff_digest': _digest(json.dumps(records, sort_keys=True).encode())}
    proposal['proposal_hash'] = _digest(json.dumps(proposal, sort_keys=True).encode())
    transact(root, state['version'], 'document-proposal:' + proposal['proposal_hash'],
             {'kind': 'document.proposed', 'payload': {'proposal': proposal}})
    return proposal


def approve_document_change(root: Path, proposal_hash: str, actor_id: str) -> dict:
    state = read_state(root)
    proposal = state['data'].get('document_proposals', {}).get(proposal_hash)
    if not proposal or not isinstance(actor_id, str) or not actor_id.strip():
        raise WorkflowError('DOCUMENT_APPROVAL_REQUIRED', 'existing exact proposal and human actor are required')
    current = _snapshot(_repository(state['data'], proposal['repo_id']), list(proposal['files']))
    if current != proposal['files']:
        raise WorkflowError('DOCUMENT_PROPOSAL_STALE', 'review a new exact diff before approval')
    approval = {'proposal_hash': proposal_hash, 'repo_id': proposal['repo_id'], 'actor_id': actor_id,
                'diff_digest': proposal['diff_digest']}
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
        manifest = json.loads((project / 'docs/devflow-context.json').read_text())
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
    sources = {project_id: (project, {'docs/devflow-context.json'})}
    if org_id:
        sources[org_id] = (org_repo, {'docs/devflow-org.json'})
    for rule in applicable.values():
        provenance = rule['provenance']
        owner = org_id if provenance['source'] == 'org' else project_id
        sources[owner][1].add(provenance['path'])
    files = {}
    previous = data.get('governing_input_receipt', {}).get('files', {})
    for owner, (repo, paths) in sources.items():
        for path, record in _snapshot(repo, list(paths)).items():
            key = owner + ':' + path
            files[key] = {'repo_id': owner, 'path': path, 'content_digest': record['after_hash'],
                          'git_head': _git(repo, 'rev-parse', 'HEAD').stdout.strip()}
            changed = (record['before_hash'] != record['after_hash'] or not record['before_exists']
                       or key in previous and previous[key]['content_digest'] != record['after_hash'])
            if changed:
                approved = any(p['repo_id'] == owner and path in p['files']
                    and p['files'][path]['after_hash'] == record['after_hash']
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
    return receipt
