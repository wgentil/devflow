"""Content-bound, complete GitHub pull-request review packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import quote


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _hash(value: object) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True, check=False)
    if result.returncode:
        raise ValueError('PR base or fork head is not locally available; fetch the exact commits before review')
    return result.stdout


def _snapshot_body(snapshot: dict) -> dict:
    required = ('pr_id', 'pr_number', 'owner', 'repo', 'base_branch', 'base_sha',
                'head_sha', 'title', 'body', 'changed_files', 'files', 'commits',
                'checks', 'comments', 'reviews', 'mergeable', 'governing_digest')
    if any(key not in snapshot for key in required):
        raise ValueError('PR snapshot is incomplete')
    if any(snapshot.get(key) is not True for key in
           ('files_complete', 'commits_complete', 'checks_complete',
            'comments_complete', 'reviews_complete')):
        raise ValueError('PR snapshot pagination or CI evidence is incomplete')
    if (type(snapshot['changed_files']) is not int or snapshot['changed_files'] < 1
            or not isinstance(snapshot['files'], list)
            or len(snapshot['files']) != snapshot['changed_files']
            or any(not isinstance(row, dict) or not isinstance(row.get('filename'), str)
                   for row in snapshot['files'])):
        raise ValueError('PR file enumeration is incomplete')
    names = [row['filename'] for row in snapshot['files']]
    if len(names) != len(set(names)):
        raise ValueError('PR file enumeration contains duplicates')
    if not isinstance(snapshot['checks'], list) or not snapshot['checks']:
        raise ValueError('PR CI evidence is missing')
    if not isinstance(snapshot['governing_digest'], str) or not snapshot['governing_digest']:
        raise ValueError('PR governing rules digest is missing')
    return {key: snapshot[key] for key in required}


def prepare_pr_review(run: dict, pr_snapshot: dict, repo: Path,
                      approved_spec: dict | None = None,
                      governing_inputs: dict | None = None) -> dict:
    """Build a full local diff and bind it to a complete hosted PR snapshot."""
    snapshot = _snapshot_body(pr_snapshot)
    pending = run.get('pending_pr', {})
    for key in ('pr_id', 'pr_number', 'owner', 'repo', 'base_branch', 'base_sha', 'head_sha'):
        if str(pending.get(key)) != str(snapshot[key]):
            raise ValueError('PR snapshot changed from the pending delivery identity')
    repo = Path(repo).expanduser().resolve()
    base, head = snapshot['base_sha'], snapshot['head_sha']
    _git(repo, 'cat-file', '-e', f'{base}^{{commit}}')
    _git(repo, 'cat-file', '-e', f'{head}^{{commit}}')
    if _git(repo, 'rev-parse', 'HEAD').decode().strip() != head:
        raise ValueError('local checkout is not at the exact PR head')
    if _git(repo, 'status', '--porcelain', '--untracked-files=all').strip():
        raise ValueError('PR review checkout has uncommitted changes')
    changed = sorted(path.decode('utf-8', errors='surrogateescape') for path in
                     _git(repo, 'diff', '--name-only', '--find-renames', '-z', base, head).split(b'\0') if path)
    hosted = sorted(row['filename'] for row in snapshot['files'])
    if changed != hosted:
        raise ValueError('PR hosted file enumeration is incomplete or differs from local full diff')
    full_diff = _git(repo, 'diff', '--binary', '--find-renames', base, head)
    batches = []
    for offset in range(0, len(changed), 20):
        paths = changed[offset:offset + 20]
        diff = _git(repo, 'diff', '--binary', '--find-renames', base, head, '--', *paths)
        batches.append({'files': paths, 'diff': diff.decode('utf-8', errors='replace'),
                        'diff_sha256': hashlib.sha256(diff).hexdigest()})
    commits = _git(repo, 'rev-list', '--reverse', f'{base}..{head}').decode().splitlines()
    if not commits or commits != [row.get('sha') for row in snapshot['commits']]:
        raise ValueError('PR commit enumeration is incomplete or differs from local history')
    plan = run.get('plan', {})
    body = {'schema_version': 1, 'run_id': run.get('id'), 'role': 'pr',
            'pr_id': snapshot['pr_id'], 'pr_number': snapshot['pr_number'],
            'owner': snapshot['owner'], 'repo': snapshot['repo'],
            'base_branch': snapshot['base_branch'], 'base_sha': base, 'head_sha': head,
            'location': str(repo), 'changed_files': changed, 'batches': batches,
            'full_diff': full_diff.decode('utf-8', errors='replace'),
            'full_diff_sha256': hashlib.sha256(full_diff).hexdigest(),
            'snapshot': snapshot, 'snapshot_hash': _hash(snapshot),
            'spec_hash': plan.get('spec_hash'), 'plan_hash': _hash(plan),
            'approved_spec': approved_spec or {},
            'governing_inputs': governing_inputs or {},
            'run_governing_digest': run.get('governing_digest'),
            'criteria': {item['id']: item.get('acceptance_criteria', [])
                         for item in plan.get('work_items', [])},
            'artifacts': run.get('artifacts', {}), 'verification_proofs': run.get('verification_proofs', {}),
            'prior_reviews': run.get('reviews', {}), 'prior_findings': run.get('pr_findings', []),
            'input_paths': changed}
    body['package_hash'] = _hash(body)
    return body


def validate_pr_snapshot(package: dict, live_snapshot: dict) -> None:
    """Fail closed if any hosted evidence or current governing input changed."""
    current = _snapshot_body(live_snapshot)
    if package.get('snapshot_hash') != _hash(current):
        raise ValueError('PR snapshot changed; prepare a fresh review package')
    unsigned = {key: value for key, value in package.items() if key != 'package_hash'}
    if package.get('package_hash') != _hash(unsigned):
        raise ValueError('PR review package content changed')


def current_pr_inputs(state_data: dict, run: dict, package: dict) -> bool:
    from .specs import content_hash
    spec = state_data.get('spec')
    approval = state_data.get('approval', {})
    governing = state_data.get('governing_input_receipt', {})
    return (isinstance(spec, dict) and approval.get('confirmed') is True
            and approval.get('content_hash') == content_hash(spec)
            and approval['content_hash'] == package.get('spec_hash')
            and spec == package.get('approved_spec')
            and governing == package.get('governing_inputs')
            and governing.get('effective_digest') == run.get('governing_digest'))


def read_pr_snapshot(client, pending: dict, governing_digest: str) -> dict:
    """Read all GitHub pages; a limit, truncation, or missing check blocks packaging."""
    owner, repo, number = pending['owner'], pending['repo'], pending['pr_number']
    prefix = f'/repos/{quote(owner, safe="")}/{quote(repo, safe="")}'
    pr = client.api('GET', f'{prefix}/pulls/{number}')
    if not isinstance(pr, dict) or str(pr.get('id')) != str(pending.get('pr_id')):
        raise ValueError('GitHub PR identity changed')

    def pages(path: str) -> list:
        rows = []
        for page in range(1, 101):
            separator = '&' if '?' in path else '?'
            batch = client.api('GET', f'{path}{separator}per_page=100&page={page}')
            if not isinstance(batch, list):
                raise ValueError('GitHub PR evidence page is invalid')
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise ValueError('GitHub PR evidence pagination is incomplete')

    files = pages(f'{prefix}/pulls/{number}/files')
    commits = pages(f'{prefix}/pulls/{number}/commits')
    comments = pages(f'{prefix}/issues/{number}/comments')
    comments.extend(pages(f'{prefix}/pulls/{number}/comments'))
    comments = [row for row in comments if '<!-- devflow-pr-review:' not in row.get('body', '')
                and '<!-- devflow-finding:' not in row.get('body', '')]
    reviews = pages(f'{prefix}/pulls/{number}/reviews')
    head = pr.get('head', {}).get('sha')
    if not isinstance(head, str) or not head:
        raise ValueError('GitHub PR head is missing')
    check_rows = []
    for page in range(1, 101):
        check_data = client.api('GET', f'{prefix}/commits/{head}/check-runs?per_page=100&page={page}')
        if not isinstance(check_data, dict) or not isinstance(check_data.get('check_runs'), list):
            raise ValueError('GitHub CI check evidence is invalid')
        batch = check_data['check_runs']
        check_rows.extend(batch)
        if len(batch) < 100:
            if check_data.get('total_count') != len(check_rows):
                raise ValueError('GitHub CI check enumeration is incomplete')
            break
    else:
        raise ValueError('GitHub CI check pagination is incomplete')
    statuses = pages(f'{prefix}/commits/{head}/statuses')
    seen_contexts = set()
    latest_statuses = []
    for status in statuses:
        context = status.get('context') if isinstance(status, dict) else None
        if context and context not in seen_contexts and context != 'devflow/pr-review':
            seen_contexts.add(context)
            latest_statuses.append(status)
    checks = [{'kind': 'check-run', 'name': row.get('name'), 'status': row.get('status'),
               'conclusion': row.get('conclusion'), 'id': row.get('id')}
              for row in check_rows if row.get('name') != 'devflow/pr-review']
    checks.extend({'kind': 'status', 'name': row['context'], 'status': 'completed',
                   'conclusion': 'success' if row.get('state') == 'success' else row.get('state'),
                   'id': row.get('id')} for row in latest_statuses)
    return {'pr_id': str(pr['id']), 'pr_number': pr['number'], 'owner': owner, 'repo': repo,
            'base_branch': pr.get('base', {}).get('ref'), 'base_sha': pr.get('base', {}).get('sha'),
            'head_sha': head, 'title': pr.get('title'), 'body': pr.get('body'),
            'changed_files': pr.get('changed_files'), 'files': files, 'files_complete': True,
            'commits': commits, 'commits_complete': True, 'checks': checks,
            'checks_complete': True, 'comments': comments, 'comments_complete': True,
            'reviews': reviews, 'reviews_complete': True, 'mergeable': pr.get('mergeable'),
            'governing_digest': governing_digest}


def record_pr_review(run: dict, package_hash: str, reviewer: dict, report: dict) -> dict:
    package = run.get('review_packages', {}).get(package_hash)
    if not package or package.get('role') != 'pr':
        raise ValueError('current PR review package is required')
    if report.get('package_hash') != package_hash or report.get('verdict') not in {
            'pass', 'changes-requested', 'human-decision-required', 'blocked'}:
        raise ValueError('PR report must bind the package and use a supported verdict')
    actor = reviewer.get('actor_id')
    prior = {value for value in run.get('actors', {}).values() if value}
    prior.update(run.get('implementer_actors', []))
    prior.update(row.get('actor_id') for entries in run.get('reviews', {}).values() for row in entries)
    if (reviewer.get('role') != 'pr' or not isinstance(actor, str) or not actor.strip()
            or actor in prior or not reviewer.get('invocation_ref')
            or reviewer.get('tool_available') is not True):
        raise ValueError('PR reviewer needs a distinct actor, real invocation, and available tooling')
    if sorted(report.get('reviewed_files', [])) != package['changed_files']:
        raise ValueError('PR reviewer must explicitly cover every changed file')
    findings = report.get('findings')
    if not isinstance(findings, list):
        raise ValueError('PR findings must be an array')
    ids = set()
    for finding in findings:
        if (not isinstance(finding, dict) or not isinstance(finding.get('id'), str)
                or not finding['id'] or finding['id'] in ids
                or finding.get('severity') not in {'critical', 'important', 'minor', 'info'}
                or finding.get('path') not in set(package['changed_files']) | {'PR'}
                or (finding.get('path') != 'PR' and (type(finding.get('line')) is not int or finding['line'] < 1))
                or not isinstance(finding.get('reason'), str) or not finding['reason'].strip()
                or not isinstance(finding.get('acceptance_condition'), str)
                or not finding['acceptance_condition'].strip()):
            raise ValueError('PR finding needs unique ID, severity, location, reason, and acceptance condition')
        ids.add(finding['id'])
        if report['verdict'] == 'human-decision-required' and not all(
                finding.get(key) for key in ('question', 'options', 'impact', 'recommendation', 'owner')):
            raise ValueError('human decision needs question, options, impact, recommendation, and owner')
        if report['verdict'] == 'human-decision-required' and (
                not isinstance(finding['options'], list) or len(finding['options']) < 2
                or any(not isinstance(option, dict) or not isinstance(option.get('choice'), str)
                       or not option['choice'].strip() or not isinstance(option.get('consequence'), str)
                       or not option['consequence'].strip() for option in finding['options'])
                or any(option.get('effect') not in {'accept', 'request-changes', 'reject'}
                       for option in finding['options'])
                or len({option['choice'] for option in finding['options']}) != len(finding['options'])):
            raise ValueError('human decision needs distinct choices and consequences')
    if report['verdict'] in {'changes-requested', 'human-decision-required'} and not findings:
        raise ValueError('nonpassing PR verdict needs findings')
    blockers = report.get('blockers', [])
    if (not isinstance(blockers, list) or any(
            not isinstance(row, dict) or not isinstance(row.get('reason'), str)
            or not row['reason'].strip() or not isinstance(row.get('next_action'), str)
            or not row['next_action'].strip() for row in blockers)
            or report['verdict'] == 'blocked' and not blockers):
        raise ValueError('blocked PR verdict needs reason and next action')
    if report['verdict'] == 'pass':
        if run.get('pr_rejected'):
            raise ValueError('human rejected this PR delivery; start a fresh run')
        if blockers:
            raise ValueError('passing PR review cannot have unresolved blockers')
        decisions = {(row.get('package_hash'), row.get('finding_id')): row.get('effect')
                     for row in run.get('pr_human_decisions', [])}
        unresolved = [finding.get('id')
                      for prior_review in run.get('reviews', {}).get('pr', [])
                      if prior_review.get('package_hash') == package_hash
                      and prior_review.get('verdict') == 'human-decision-required'
                      for finding in prior_review.get('findings', [])
                      if decisions.get((package_hash, finding.get('id'))) != 'accept']
        if unresolved:
            raise ValueError('human-required PR findings need accepting decisions before pass')
        checks = package.get('snapshot', {}).get('checks', [])
        if not checks or any(row.get('status') != 'completed'
                             or row.get('conclusion') not in ({'success'} if row.get('kind') == 'status'
                                                              else {'success', 'neutral', 'skipped'})
                             for row in checks):
            raise ValueError('PR CI must be complete and successful before pass')
        if package.get('snapshot', {}).get('mergeable') is not True:
            raise ValueError('PR mergeability is unknown or blocked')
        if any(row.get('severity') in {'critical', 'important'} for row in findings):
            raise ValueError('pass cannot contain unresolved blocking findings')
    body = {'schema_version': 1, 'package_hash': package_hash, 'role': 'pr',
            'actor_id': actor, 'invocation_ref': reviewer['invocation_ref'],
            'verdict': report['verdict'], 'findings': findings, 'blockers': blockers,
            'reviewed_files': sorted(report['reviewed_files'])}
    body['review_id'] = _hash(body)
    return body


def record_pr_human_decision(run: dict, package_hash: str, actor_id: str,
                             finding_id: str, choice: str, rationale: str) -> dict:
    package = run.get('review_packages', {}).get(package_hash)
    if not package or package.get('role') != 'pr' or not run.get('pending_pr'):
        raise ValueError('current PR package and pending PR are required')
    if any(str(run['pending_pr'].get(key)) != str(package.get(key)) for key in ('pr_id', 'head_sha')):
        raise ValueError('PR head changed; human decision needs a fresh review')
    latest_reviews = run.get('reviews', {}).get('pr', [])
    review = latest_reviews[-1] if latest_reviews else None
    if review and (review.get('package_hash') != package_hash
                   or review.get('verdict') != 'human-decision-required'):
        review = None
    finding = next((row for row in review.get('findings', []) if row.get('id') == finding_id), None) if review else None
    option = next((row for row in finding.get('options', []) if row.get('choice') == choice), None) if finding else None
    if not option:
        raise ValueError('human choice must answer a current review finding option')
    actors = set(run.get('actors', {}).values()) | set(run.get('implementer_actors', []))
    actors.update(row.get('actor_id') for row in run.get('reviews', {}).get('pr', []))
    if not isinstance(actor_id, str) or not actor_id.strip() or actor_id in actors:
        raise ValueError('human decision actor must be distinct from implementer and reviewer')
    if actor_id != finding.get('owner'):
        raise ValueError('human decision must be recorded by the named owner')
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError('human decision requires rationale')
    if any(row.get('package_hash') == package_hash and row.get('finding_id') == finding_id
           for row in run.get('pr_human_decisions', [])):
        raise ValueError('human decision for this finding already recorded')
    body = {'schema_version': 1, 'package_hash': package_hash, 'review_id': review['review_id'],
            'pr_id': package['pr_id'], 'head_sha': package['head_sha'],
            'finding_id': finding_id, 'actor_id': actor_id, 'choice': choice,
            'effect': option['effect'],
            'rationale': rationale.strip()}
    body['id'] = _hash(body)
    return body
