"""Open and reconcile a GitHub PR without treating creation as delivery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

from .delivery import _manifest_body, verify_delivery
from .gates import gate_status
from .store import WorkflowError


STATUS_CONTEXT = 'devflow/pr-review'


def _hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def _preflight(run: dict, manifest: dict, request: dict) -> tuple[str, str, str]:
    if manifest.get('outcome') != 'pull-request':
        raise ValueError('PR opening requires a pull-request delivery manifest')
    manifest_hash = manifest.get('manifest_hash')
    verification = manifest.get('verification', {})
    gate_run = {key: value for key, value in run.items() if key not in {'pr_open', 'pending_pr'}}
    if (not manifest_hash or _hash(_manifest_body(manifest)) != manifest_hash
            or verification.get('passed') is not True
            or verification.get('manifest_hash') != manifest_hash
            or run.get('id') != manifest.get('run_id') or run.get('status') != 'active'
            or _hash(run.get('plan', {})) != manifest.get('plan_hash')
            or gate_status(gate_run).get('stage') != 'delivery'):
        raise ValueError('PR delivery requires a fresh verified exact-head manifest')
    if verify_delivery(gate_run, manifest, manifest_hash, manifest.get('repositories', {})) != manifest:
        raise ValueError('PR delivery verification changed before provider write')
    authorization = request.get('authorization', {})
    if (not isinstance(authorization, dict) or authorization.get('approved') is not True
            or not isinstance(authorization.get('actor_id'), str) or not authorization['actor_id'].strip()
            or authorization.get('manifest_hash') != manifest_hash
            or authorization.get('action') != 'delivery.pull-request'):
        raise ValueError('PR creation needs explicit manifest-bound authorization')
    setup = request.get('setup', {})
    owner, repo, base = request.get('owner'), request.get('repo'), request.get('base_branch')
    if (not isinstance(setup, dict) or setup.get('verified') is not True
            or setup.get('owner') != owner or setup.get('repo') != repo
            or setup.get('base') != base or setup.get('context') != STATUS_CONTEXT
            or type(setup.get('ruleset_id')) is not int):
        raise ValueError('verified GitHub PR ruleset setup is required')
    if any(not isinstance(value, str) or not value.strip() for value in
           (owner, repo, base, request.get('head_branch'), request.get('title'))):
        raise ValueError('PR request needs repository, branches, and title')
    repositories = manifest.get('repositories', {})
    if len(repositories) != 1:
        raise ValueError('one GitHub PR must target exactly one DevFlow repository')
    record = next(iter(repositories.values()))
    if record.get('head') != verification.get('repository_fingerprints', {}).get(next(iter(repositories)), {}).get('head'):
        raise ValueError('PR head differs from verified delivery manifest')
    location = Path(record.get('location', ''))
    remotes = subprocess.run(['git', 'remote', '-v'], cwd=location, capture_output=True,
                             text=True, check=False)
    if remotes.returncode:
        raise ValueError('cannot inspect the PR repository remotes')
    identities = set()
    for line in remotes.stdout.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        match = re.fullmatch(r'(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([^/]+)/([^/]+?)(?:\.git)?', parts[1])
        if match:
            identities.add((match.group(1).lower(), match.group(2).lower()))
    if (owner.lower(), repo.lower()) not in identities:
        raise ValueError('requested GitHub repository does not match any local remote')
    return owner, repo, record['head']


def _pr_path(owner: str, repo: str, request: dict) -> str:
    return (f'/repos/{quote(owner, safe="")}/{quote(repo, safe="")}/pulls?state=open'
            f'&head={quote(owner + ":" + request["head_branch"], safe="")}'
            f'&base={quote(request["base_branch"], safe="")}')


def _current_pr(client, owner: str, repo: str, request: dict) -> dict | None:
    listed = client.api('GET', _pr_path(owner, repo, request))
    if not isinstance(listed, list) or len(listed) > 1:
        raise WorkflowError('PR_IDENTITY_AMBIGUOUS', 'GitHub PR lookup is incomplete or ambiguous')
    if not listed:
        return None
    number = listed[0].get('number') if isinstance(listed[0], dict) else None
    if type(number) is not int or number <= 0:
        raise WorkflowError('PR_IDENTITY_AMBIGUOUS', 'GitHub PR number is missing')
    return client.api('GET', f'/repos/{owner}/{repo}/pulls/{number}')


def _checked_pr(pr: dict, owner: str, repo: str, request: dict, head_sha: str) -> dict:
    if (not isinstance(pr, dict) or type(pr.get('number')) is not int
            or pr.get('state') != 'open' or str(pr.get('id', '')).strip() == ''
            or pr.get('base', {}).get('ref') != request['base_branch']
            or pr.get('head', {}).get('sha') != head_sha):
        raise WorkflowError('PR_HEAD_STALE', 'GitHub PR is not open on the verified target and head')
    base_sha = pr.get('base', {}).get('sha')
    url = pr.get('html_url')
    if not isinstance(base_sha, str) or not base_sha or not isinstance(url, str) or not url.startswith(
            f'https://github.com/{owner}/{repo}/pull/'):
        raise WorkflowError('PR_IDENTITY_AMBIGUOUS', 'GitHub PR base or URL is invalid')
    return {'status': 'pending-review', 'pr_id': str(pr['id']), 'pr_number': pr['number'],
            'url': url, 'owner': owner, 'repo': repo, 'base_branch': request['base_branch'],
            'base_sha': base_sha, 'head_sha': head_sha}


def _pending_status(client, owner: str, repo: str, head_sha: str, *, write: bool) -> bool:
    path = f'/repos/{owner}/{repo}/commits/{head_sha}/statuses?per_page=100'
    statuses = client.api('GET', path)
    if not isinstance(statuses, list) or len(statuses) >= 100:
        raise WorkflowError('PR_STATUS_UNVERIFIED', 'GitHub status history is incomplete')
    latest = next((status for status in statuses if isinstance(status, dict)
                   and status.get('context') == STATUS_CONTEXT), None)
    if latest and latest.get('state') == 'pending':
        return True
    if not write:
        return False
    response = client.api('POST', f'/repos/{owner}/{repo}/statuses/{head_sha}',
                          {'state': 'pending', 'context': STATUS_CONTEXT,
                           'description': 'DevFlow independent PR review pending'})
    if not isinstance(response, dict) or response.get('state') != 'pending' or response.get('context') != STATUS_CONTEXT:
        raise WorkflowError('GITHUB_WRITE_UNCERTAIN', 'pending PR status was not confirmed')
    return True


def open_pr_delivery(run: dict, verified_manifest: dict, request: dict, client) -> dict:
    owner, repo, head_sha = _preflight(run, verified_manifest, request)
    pr = _current_pr(client, owner, repo, request)
    if pr is None:
        created = client.api('POST', f'/repos/{owner}/{repo}/pulls',
                             {'title': request['title'], 'body': request.get('body', ''),
                              'head': request['head_branch'], 'base': request['base_branch']})
        number = created.get('number') if isinstance(created, dict) else None
        if type(number) is not int or number <= 0:
            raise WorkflowError('GITHUB_WRITE_UNCERTAIN', 'created PR identity could not be confirmed')
        pr = client.api('GET', f'/repos/{owner}/{repo}/pulls/{number}')
    result = _checked_pr(pr, owner, repo, request, head_sha)
    if not _pending_status(client, owner, repo, head_sha, write=True):
        raise WorkflowError('PR_STATUS_UNVERIFIED', 'pending PR status is unavailable')
    result['manifest_hash'] = verified_manifest['manifest_hash']
    return result


def reconcile_pr_delivery(run: dict, verified_manifest: dict, request: dict, client,
                          *, ensure_pending: bool = False) -> dict:
    owner, repo, head_sha = _preflight(run, verified_manifest, request)
    pr = _current_pr(client, owner, repo, request)
    if pr is None:
        raise WorkflowError('PR_OUTCOME_UNCERTAIN', 'no matching GitHub PR was found')
    result = _checked_pr(pr, owner, repo, request, head_sha)
    if not _pending_status(client, owner, repo, head_sha, write=ensure_pending):
        raise WorkflowError('PR_STATUS_UNVERIFIED', 'pending status is not yet visible on GitHub')
    result['manifest_hash'] = verified_manifest['manifest_hash']
    return result
