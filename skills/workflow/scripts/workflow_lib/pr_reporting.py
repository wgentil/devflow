"""Idempotent GitHub PR report and exact-head terminal receipt."""

from __future__ import annotations

from urllib.parse import quote


CONTEXT = 'devflow/pr-review'


def _paths(package: dict) -> tuple[str, str]:
    owner = quote(package['owner'], safe='')
    repo = quote(package['repo'], safe='')
    prefix = f'/repos/{owner}/{repo}'
    return prefix, f'{prefix}/pulls/{package["pr_number"]}'


def _latest_status(client, prefix: str, head: str) -> dict | None:
    statuses = client.api('GET', f'{prefix}/commits/{head}/statuses?per_page=100')
    if not isinstance(statuses, list):
        raise ValueError('GitHub PR status history is invalid')
    return next((row for row in statuses if row.get('context') == CONTEXT), None)


def _pages(client, path: str) -> list:
    rows = []
    for page in range(1, 101):
        batch = client.api('GET', f'{path}?per_page=100&page={page}')
        if not isinstance(batch, list):
            raise ValueError('GitHub PR report history page is invalid')
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise ValueError('GitHub PR report history pagination is incomplete')


def publish_pr_review(client, package: dict, verdict: dict, decisions: list[dict]) -> dict:
    if verdict.get('package_hash') != package.get('package_hash') or not verdict.get('review_id'):
        raise ValueError('PR verdict does not bind the review package')
    if verdict.get('verdict') == 'pass':
        if any(row.get('package_hash') == package['package_hash'] and not row.get('choice') for row in decisions):
            raise ValueError('unresolved human decision blocks success')
        state = 'success'
    elif verdict.get('verdict') == 'human-decision-required':
        state = 'pending'
    elif verdict.get('verdict') in {'changes-requested', 'blocked'}:
        state = 'failure'
    else:
        raise ValueError('unsupported PR verdict')
    prefix, pull = _paths(package)
    marker = f'<!-- devflow-pr-review:{package["package_hash"]}:{verdict["review_id"]} -->'
    comments = _pages(client, f'{prefix}/issues/{package["pr_number"]}/comments')
    summary = next((row for row in comments if marker in row.get('body', '')), None)
    if summary is None:
        lines = [marker, f'DevFlow PR review: **{verdict["verdict"]}**',
                 f'Package `{package["package_hash"]}`; head `{package["head_sha"]}`.',
                 f'Files reviewed: {len(verdict.get("reviewed_files", []))}.']
        for finding in verdict.get('findings', []):
            lines.append(f'- {finding["id"]}: {finding["reason"]} ({finding["path"]})')
            if verdict['verdict'] == 'human-decision-required':
                options = '; '.join(f'{row["choice"]}: {row["consequence"]}' for row in finding['options'])
                lines.append(f'  Decision: {finding["question"]} Options: {options}. '
                             f'Impact: {finding["impact"]}. Recommendation: {finding["recommendation"]}. '
                             f'Owner: {finding["owner"]}.')
        for blocker in verdict.get('blockers', []):
            lines.append(f'- Blocked: {blocker["reason"]} Next: {blocker["next_action"]}')
        summary = client.api('POST', f'{prefix}/issues/{package["pr_number"]}/comments',
                             {'body': '\n'.join(lines)})
        if marker not in summary.get('body', ''):
            raise ValueError('GitHub PR summary write was not confirmed')
    inline = _pages(client, f'{pull}/comments')
    for finding in verdict.get('findings', []):
        if finding.get('path') == 'PR' or finding.get('severity') not in {'critical', 'important'}:
            continue
        finding_marker = f'<!-- devflow-finding:{package["package_hash"]}:{finding["id"]} -->'
        if any(finding_marker in row.get('body', '') for row in inline):
            continue
        body = f'{finding_marker}\n{finding["reason"]}\nAcceptance: {finding["acceptance_condition"]}'
        row = client.api('POST', f'{pull}/comments', {'body': body,
            'commit_id': package['head_sha'], 'path': finding['path'],
            'line': finding['line'], 'side': 'RIGHT'})
        if finding_marker not in row.get('body', ''):
            raise ValueError('GitHub PR inline comment write was not confirmed')
        inline.append(row)
    latest = _latest_status(client, prefix, package['head_sha'])
    description = f'DevFlow {verdict["verdict"]}; package {package["package_hash"][:12]}'
    if not latest or latest.get('state') != state or latest.get('description') != description:
        latest = client.api('POST', f'{prefix}/statuses/{package["head_sha"]}',
            {'state': state, 'context': CONTEXT, 'description': description,
             'target_url': summary.get('html_url')})
        if latest.get('state') != state or latest.get('context') != CONTEXT:
            raise ValueError('GitHub PR status write was not confirmed')
    return {'state': state, 'package_hash': package['package_hash'],
            'review_id': verdict['review_id'], 'pr_id': package['pr_id'],
            'head_sha': package['head_sha'], 'base_sha': package['base_sha'],
            'status_url': latest.get('url'), 'summary_url': summary.get('html_url')}


def complete_pr_delivery(run: dict, package: dict, verdict: dict, receipt: dict) -> dict:
    pending = run.get('pending_pr', {})
    if run.get('status') != 'active' or not pending:
        raise ValueError('active pending PR delivery is required')
    if (receipt.get('state') != 'success' or verdict.get('verdict') != 'pass'
            or not receipt.get('status_url') or receipt.get('package_hash') != package.get('package_hash')
            or receipt.get('review_id') != verdict.get('review_id')
            or any(str(receipt.get(key)) != str(package.get(key)) for key in ('pr_id', 'head_sha', 'base_sha'))
            or any(str(pending.get(key)) != str(package.get(key)) for key in ('pr_id', 'head_sha', 'base_sha'))):
        raise ValueError('confirmed exact-head GitHub PR success is required')
    if not any(row.get('review_id') == verdict.get('review_id')
               for row in run.get('reviews', {}).get('pr', [])):
        raise ValueError('current independent PR verdict is not recorded')
    if run['reviews']['pr'][-1].get('review_id') != verdict.get('review_id'):
        raise ValueError('latest PR review must be the passing verdict')
    return {'outcome': 'pull-request', 'manifest_hash': pending['manifest_hash'],
            'pr_id': package['pr_id'], 'pr_number': package['pr_number'],
            'url': pending.get('url'), 'head_sha': package['head_sha'],
            'base_sha': package['base_sha'], 'package_hash': package['package_hash'],
            'review_id': verdict['review_id'], 'status_url': receipt['status_url']}
