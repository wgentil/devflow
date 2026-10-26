"""GitHub PR setup and later PR lifecycle commands."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity

from workflow_lib.github_pr import GithubClient
from workflow_lib.pr_setup import configure_pr_setup, inspect_pr_setup, verify_pr_setup, _matches
from workflow_lib.pr_delivery import open_pr_delivery, reconcile_pr_delivery, refresh_pr_delivery
from workflow_lib.pr_reviews import (read_pr_snapshot, validate_pr_snapshot,
                                     current_pr_inputs, _hash as review_hash)
from workflow_lib.pr_reporting import publish_pr_review, complete_pr_delivery, _latest_status, _paths
from workflow_lib.host_completion import package_current
from workflow_lib.store import WorkflowError, transact


def register_commands(parser: argparse.ArgumentParser) -> None:
    command = parser.add_parser('pr')
    actions = command.add_subparsers(dest='pr_command', required=True)
    for name in ('setup', 'inspect'):
        action = actions.add_parser(name)
        action.add_argument('--request-file', required=True)
        if name == 'setup':
            action.add_argument('--root', required=True)
            action.add_argument('--operation-id', required=True)
    opening = actions.add_parser('open')
    opening.add_argument('--root', required=True)
    opening.add_argument('--run-id', required=True)
    opening.add_argument('--manifest-file', required=True)
    opening.add_argument('--request-file', required=True)
    opening.add_argument('--operation-id', required=True)
    rework = actions.add_parser('rework')
    rework.add_argument('--root', required=True)
    rework.add_argument('--run-id', required=True)
    rework.add_argument('--review-id', required=True)
    rework.add_argument('--direction-file')
    rework.add_argument('--operation-id', required=True)
    sync = actions.add_parser('sync')
    sync.add_argument('--root', required=True)
    sync.add_argument('--run-id', required=True)
    sync.add_argument('--operation-id', required=True)
    refresh = actions.add_parser('refresh')
    refresh.add_argument('--root', required=True)
    refresh.add_argument('--run-id', required=True)
    refresh.add_argument('--manifest-file', required=True)
    refresh.add_argument('--operation-id', required=True)
    for name in ('publish', 'complete'):
        action = actions.add_parser(name)
        action.add_argument('--root', required=True)
        action.add_argument('--run-id', required=True)
        action.add_argument('--review-id', required=True)
        action.add_argument('--operation-id', required=True)


def _request(path: str) -> dict:
    try:
        request = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError('PR_SETUP_REQUEST_INVALID', 'read a valid PR setup request JSON file') from exc
    if not isinstance(request, dict):
        raise WorkflowError('PR_REQUEST_INVALID', 'request file must contain an object')
    return request


def _hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def _verify_live_policy(client: GithubClient, state_data: dict, setup_id: str | None) -> dict:
    setup = state_data.get('pr_setup', {}).get(setup_id, {})
    receipt = setup.get('receipt', {})
    if setup.get('status') != 'verified' or not isinstance(receipt, dict):
        raise WorkflowError('PR_SETUP_REQUIRED', 'verified GitHub PR setup is required')
    observed = inspect_pr_setup(client, receipt.get('owner'), receipt.get('repo'), receipt.get('base'))
    if (not observed.get('configured') or observed.get('ruleset_id') != receipt.get('ruleset_id')
            or not _matches(observed.get('ruleset'), receipt['base'], receipt.get('bypass_actors', []))):
        raise WorkflowError('PR_SETUP_STALE', 'GitHub required PR status policy changed; reconcile setup')
    return receipt


def dispatch(parsed: argparse.Namespace) -> dict:
    client = GithubClient()
    if parsed.pr_command == 'sync':
        return _sync(parsed, client)
    if parsed.pr_command == 'rework':
        root = Path(parsed.root).expanduser().resolve()
        state = read_command(root, parsed, family='pr')
        direction = _request(parsed.direction_file) if parsed.direction_file else None
        response = transact(root, state['version'], parsed.operation_id,
            {'kind': 'domain.pr.rework', 'payload': {'request': {
                'run_id': parsed.run_id, 'review_id': parsed.review_id,
                'direction': direction}}})
        return {**response['state']['data']['domain_receipts'][parsed.operation_id],
                'state_version': response['state']['version'], 'replayed': response['replayed']}
    if parsed.pr_command == 'refresh':
        return _refresh(parsed, client)
    if parsed.pr_command in {'publish', 'complete'}:
        return _review_delivery(parsed, client)
    request = _request(parsed.request_file)
    if parsed.pr_command == 'open':
        return _open(parsed, request, client)
    if not all(key in request for key in ('owner', 'repo', 'base', 'bypass_actors')):
        raise WorkflowError('PR_SETUP_REQUEST_INVALID', 'setup request needs owner, repo, base, and bypass actors')
    if parsed.pr_command == 'inspect':
        return inspect_pr_setup(client, request['owner'], request['repo'], request['base'])
    root = Path(parsed.root).expanduser().resolve()
    operation_id = parsed.operation_id
    request_hash = _hash(request)
    state = read_command(root, parsed, family='pr')
    prior = state['data'].get('pr_setup', {}).get(operation_id)
    if prior and prior['request_hash'] != request_hash:
        raise WorkflowError('OPERATION_CONFLICT', 'PR setup operation ID belongs to different input')
    if prior and prior['status'] == 'verified':
        return {**prior['receipt'], 'replayed': True}
    if prior and prior['status'] == 'failed':
        raise WorkflowError('PR_SETUP_FAILED', 'use a new operation ID after correcting setup inputs')
    if not prior:
        state = transact(root, state['version'], f'pr-setup-start:{operation_id}',
                         {'kind': 'domain.pr.setup-start', 'payload': {'request': {
                             'operation_id': operation_id, 'request_hash': request_hash,
                             'setup_request': request}}})['state']
    try:
        if prior:
            result = verify_pr_setup(client, request['owner'], request['repo'], request['base'],
                                     request['bypass_actors'])
        else:
            result = configure_pr_setup(client, request['owner'], request['repo'], request['base'],
                                        request['bypass_actors'])
    except WorkflowError as exc:
        status = 'uncertain' if exc.code in {'GITHUB_WRITE_UNCERTAIN', 'PR_RULESET_UNVERIFIED',
                                           'GITHUB_UNAVAILABLE', 'PR_SETUP_UNCERTAIN'} else 'failed'
        latest = read_command(root, parsed, family='pr')
        if latest['data']['pr_setup'][operation_id]['status'] != status:
            transact(root, latest['version'], f'pr-setup-{status}:{operation_id}',
                     {'kind': 'domain.pr.setup-finish', 'payload': {'request': {
                         'operation_id': operation_id, 'request_hash': request_hash,
                         'status': status, 'error_code': exc.code}}})
        raise
    latest = read_command(root, parsed, family='pr')
    transact(root, latest['version'], f'pr-setup-verified:{operation_id}',
             {'kind': 'domain.pr.setup-finish', 'payload': {'request': {
                 'operation_id': operation_id, 'request_hash': request_hash,
                 'status': 'verified', 'receipt': result}}})
    return result


def _sync(parsed: argparse.Namespace, client: GithubClient) -> dict:
    root = Path(parsed.root).expanduser().resolve()
    state = read_command(root, parsed, family='pr')
    run = state['data'].get('runs', {}).get(parsed.run_id)
    pending = run.get('pending_pr') if run else None
    if not pending or run.get('status') != 'active' or run.get('pr_rework') or run.get('pr_rejected'):
        raise WorkflowError('PR_SYNC_UNAVAILABLE', 'active pending PR outside rework is required')
    previous = state['operations'].get(parsed.operation_id)
    if previous:
        if previous.get('kind') != 'domain.pr.rework':
            raise WorkflowError('OPERATION_CONFLICT', 'PR sync operation ID belongs to another action')
        return {**state['data']['domain_receipts'][parsed.operation_id], 'replayed': True}
    pr = client.api('GET', f'/repos/{pending["owner"]}/{pending["repo"]}/pulls/{pending["pr_number"]}')
    if (not isinstance(pr, dict) or str(pr.get('id')) != str(pending['pr_id'])
            or pr.get('state') != 'open' or pr.get('base', {}).get('ref') != pending['base_branch']):
        raise WorkflowError('PR_IDENTITY_STALE', 'hosted PR identity or target changed')
    observed_head = pr.get('head', {}).get('sha')
    observed_base = pr.get('base', {}).get('sha')
    if (not observed_head or not observed_base
            or observed_head == pending['head_sha'] and observed_base == pending['base_sha']):
        raise WorkflowError('PR_SYNC_NOT_NEEDED', 'hosted PR head and base have not changed')
    response = transact(root, state['version'], parsed.operation_id,
        {'kind': 'domain.pr.rework', 'payload': {'request': {
            'run_id': parsed.run_id, 'reason': 'external-update',
            'observed_head': observed_head, 'observed_base': observed_base}}})
    return {**response['state']['data']['domain_receipts'][parsed.operation_id],
            'state_version': response['state']['version'], 'replayed': response['replayed']}


def _refresh(parsed: argparse.Namespace, client: GithubClient) -> dict:
    root = Path(parsed.root).expanduser().resolve()
    state = read_command(root, parsed, family='pr')
    run = state['data'].get('runs', {}).get(parsed.run_id)
    if not run:
        raise WorkflowError('RUN_NOT_FOUND', 'PR refresh needs an active run')
    _verify_live_policy(client, state['data'], run.get('pending_pr', {}).get('setup_operation_id'))
    try:
        manifest = json.loads(Path(parsed.manifest_file).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError('PR_MANIFEST_INVALID', 'read a verified delivery manifest JSON file') from exc
    previous = state['operations'].get(parsed.operation_id)
    if previous:
        if previous.get('kind') != 'domain.pr.refresh':
            raise WorkflowError('OPERATION_CONFLICT', 'PR refresh operation ID belongs to another action')
        receipt = previous['payload']['request']['receipt']
        if receipt.get('manifest_hash') != manifest.get('manifest_hash'):
            raise WorkflowError('OPERATION_CONFLICT', 'PR refresh operation belongs to another manifest')
        return {**receipt, 'replayed': True}
    receipt = refresh_pr_delivery(run, manifest, client)
    response = transact(root, state['version'], parsed.operation_id,
        {'kind': 'domain.pr.refresh', 'payload': {'request': {
            'run_id': parsed.run_id, 'receipt': receipt}}})
    return {**receipt, 'state_version': response['state']['version'], 'replayed': response['replayed']}


def _review_delivery(parsed: argparse.Namespace, client: GithubClient) -> dict:
    root = Path(parsed.root).expanduser().resolve()
    state = read_command(root, parsed, family='pr')
    run = state['data'].get('runs', {}).get(parsed.run_id)
    if not run or not run.get('pending_pr'):
        raise WorkflowError('PR_NOT_OPEN', 'pending PR is required')
    previous = state['operations'].get(parsed.operation_id)
    if previous:
        expected_kind = ('domain.pr.review-published' if parsed.pr_command == 'publish'
                         else 'domain.pr.delivered')
        record = previous.get('payload', {}).get('request', {})
        result = record.get('receipt', record.get('delivery', {}))
        if (previous.get('kind') != expected_kind or record.get('run_id') != parsed.run_id
                or result.get('review_id') != parsed.review_id):
            raise WorkflowError('OPERATION_CONFLICT', 'PR operation ID belongs to different input')
        return {**result, 'replayed': True}
    _verify_live_policy(client, state['data'], run['pending_pr'].get('setup_operation_id'))
    review = next((row for row in run.get('reviews', {}).get('pr', [])
                   if row.get('review_id') == parsed.review_id), None)
    if not review:
        raise WorkflowError('PR_REVIEW_REQUIRED', 'recorded PR review is required')
    package = run.get('review_packages', {}).get(review['package_hash'])
    if not package or not package_current(run, package) or not current_pr_inputs(state['data'], run, package):
        raise WorkflowError('PR_REVIEW_STALE', 'PR package or local head changed')
    if (not run.get('reviews', {}).get('pr')
            or run['reviews']['pr'][-1]['review_id'] != parsed.review_id):
        raise WorkflowError('PR_REVIEW_STALE', 'only the latest PR review may be published')
    snapshot = read_pr_snapshot(client, run['pending_pr'],
                                review_hash(state['data'].get('governing_input_receipt', {})))
    validate_pr_snapshot(package, snapshot)
    if parsed.pr_command == 'publish':
        decisions = run.get('pr_human_decisions', [])
        receipt = publish_pr_review(client, package, review, decisions)
        after = read_pr_snapshot(client, run['pending_pr'],
                                 review_hash(state['data'].get('governing_input_receipt', {})))
        validate_pr_snapshot(package, after)
        response = transact(root, state['version'], parsed.operation_id,
            {'kind': 'domain.pr.review-published', 'payload': {'request': {
                'run_id': parsed.run_id, 'receipt': receipt}}})
        return {**receipt, 'state_version': response['state']['version'], 'replayed': response['replayed']}
    receipt = next((row for row in reversed(run.get('pr_publications', []))
                    if row.get('review_id') == parsed.review_id and row.get('state') == 'success'), None)
    if not receipt:
        raise WorkflowError('PR_STATUS_REQUIRED', 'confirmed successful PR status is required')
    prefix, _ = _paths(package)
    latest = _latest_status(client, prefix, package['head_sha'])
    if (not latest or latest.get('state') != 'success' or latest.get('url') != receipt['status_url']
            or latest.get('description') != f'DevFlow pass; package {package["package_hash"][:12]}'):
        raise WorkflowError('PR_STATUS_STALE', 'GitHub required status is not the confirmed current success')
    delivery = complete_pr_delivery(run, package, review, receipt)
    response = transact(root, state['version'], parsed.operation_id,
        {'kind': 'domain.pr.delivered', 'payload': {'request': {
            'run_id': parsed.run_id, 'delivery': delivery}}})
    return {**delivery, 'state_version': response['state']['version'], 'replayed': response['replayed']}


def _open(parsed: argparse.Namespace, request: dict, client: GithubClient) -> dict:
    root = Path(parsed.root).expanduser().resolve()
    try:
        manifest = json.loads(Path(parsed.manifest_file).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError('PR_MANIFEST_INVALID', 'read a verified delivery manifest JSON file') from exc
    state = read_command(root, parsed, family='pr')
    run = state['data'].get('runs', {}).get(parsed.run_id)
    if not run:
        raise WorkflowError('RUN_NOT_FOUND', 'PR opening needs an active DevFlow run')
    setup = state['data'].get('pr_setup', {}).get(request.get('setup_operation_id'), {})
    if setup.get('status') != 'verified' or not isinstance(setup.get('receipt'), dict):
        raise WorkflowError('PR_SETUP_REQUIRED', 'verified GitHub ruleset setup is required')
    _verify_live_policy(client, state['data'], request.get('setup_operation_id'))
    request_hash = _hash(request)
    prior = run.get('pr_open')
    if prior and prior['status'] == 'failed' and prior.get('operation_id') != parsed.operation_id:
        prior = None
    if prior and (prior.get('operation_id') != parsed.operation_id or prior.get('request_hash') != request_hash
                  or prior.get('manifest_hash') != manifest.get('manifest_hash')):
        raise WorkflowError('OPERATION_CONFLICT', 'PR opening already belongs to different input')
    if prior and prior['status'] == 'verified':
        return {**run['pending_pr'], 'replayed': True}
    if prior and prior['status'] == 'failed':
        raise WorkflowError('PR_OPEN_FAILED', 'correct the PR request before starting a new operation')
    provider_request = {**request, 'setup': setup['receipt']}
    if not prior:
        state = transact(root, state['version'], f'pr-open-start:{parsed.operation_id}',
                         {'kind': 'domain.pr.open-start', 'payload': {'request': {
                             'run_id': parsed.run_id, 'operation_id': parsed.operation_id,
                             'request_hash': request_hash, 'manifest_hash': manifest.get('manifest_hash')}}})['state']
        run = state['data']['runs'][parsed.run_id]
    try:
        if prior:
            result = reconcile_pr_delivery(run, manifest, provider_request, client, ensure_pending=True)
        else:
            result = open_pr_delivery(run, manifest, provider_request, client)
    except (WorkflowError, ValueError) as exc:
        code = exc.code if isinstance(exc, WorkflowError) else 'PR_OPEN_INVALID'
        status = ('uncertain' if code in {'GITHUB_WRITE_UNCERTAIN', 'GITHUB_UNAVAILABLE',
                                        'PR_STATUS_UNVERIFIED', 'PR_OUTCOME_UNCERTAIN'} else 'failed')
        latest = read_command(root, parsed, family='pr')
        if latest['data']['runs'][parsed.run_id]['pr_open']['status'] != status:
            transact(root, latest['version'], f'pr-open-{status}:{parsed.operation_id}',
                     {'kind': 'domain.pr.open-finish', 'payload': {'request': {
                         'run_id': parsed.run_id, 'operation_id': parsed.operation_id,
                         'request_hash': request_hash, 'status': status, 'error_code': code}}})
        raise
    latest = read_command(root, parsed, family='pr')
    result['setup_operation_id'] = request['setup_operation_id']
    transact(root, latest['version'], f'pr-open-verified:{parsed.operation_id}',
             {'kind': 'domain.pr.open-finish', 'payload': {'request': {
                 'run_id': parsed.run_id, 'operation_id': parsed.operation_id,
                 'request_hash': request_hash, 'status': 'verified', 'receipt': result}}})
    return result
