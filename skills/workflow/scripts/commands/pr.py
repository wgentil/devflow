"""GitHub PR setup and later PR lifecycle commands."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from workflow_lib.github_pr import GithubClient
from workflow_lib.pr_setup import configure_pr_setup, inspect_pr_setup, verify_pr_setup
from workflow_lib.pr_delivery import open_pr_delivery, reconcile_pr_delivery
from workflow_lib.store import WorkflowError, read_state, transact


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


def dispatch(parsed: argparse.Namespace) -> dict:
    request = _request(parsed.request_file)
    client = GithubClient()
    if parsed.pr_command == 'open':
        return _open(parsed, request, client)
    if not all(key in request for key in ('owner', 'repo', 'base', 'bypass_actors')):
        raise WorkflowError('PR_SETUP_REQUEST_INVALID', 'setup request needs owner, repo, base, and bypass actors')
    if parsed.pr_command == 'inspect':
        return inspect_pr_setup(client, request['owner'], request['repo'], request['base'])
    root = Path(parsed.root).expanduser().resolve()
    operation_id = parsed.operation_id
    request_hash = _hash(request)
    state = read_state(root)
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
        latest = read_state(root)
        if latest['data']['pr_setup'][operation_id]['status'] != status:
            transact(root, latest['version'], f'pr-setup-{status}:{operation_id}',
                     {'kind': 'domain.pr.setup-finish', 'payload': {'request': {
                         'operation_id': operation_id, 'request_hash': request_hash,
                         'status': status, 'error_code': exc.code}}})
        raise
    latest = read_state(root)
    transact(root, latest['version'], f'pr-setup-verified:{operation_id}',
             {'kind': 'domain.pr.setup-finish', 'payload': {'request': {
                 'operation_id': operation_id, 'request_hash': request_hash,
                 'status': 'verified', 'receipt': result}}})
    return result


def _open(parsed: argparse.Namespace, request: dict, client: GithubClient) -> dict:
    root = Path(parsed.root).expanduser().resolve()
    try:
        manifest = json.loads(Path(parsed.manifest_file).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError('PR_MANIFEST_INVALID', 'read a verified delivery manifest JSON file') from exc
    state = read_state(root)
    run = state['data'].get('runs', {}).get(parsed.run_id)
    if not run:
        raise WorkflowError('RUN_NOT_FOUND', 'PR opening needs an active DevFlow run')
    setup = state['data'].get('pr_setup', {}).get(request.get('setup_operation_id'), {})
    if setup.get('status') != 'verified' or not isinstance(setup.get('receipt'), dict):
        raise WorkflowError('PR_SETUP_REQUIRED', 'verified GitHub ruleset setup is required')
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
        latest = read_state(root)
        if latest['data']['runs'][parsed.run_id]['pr_open']['status'] != status:
            transact(root, latest['version'], f'pr-open-{status}:{parsed.operation_id}',
                     {'kind': 'domain.pr.open-finish', 'payload': {'request': {
                         'run_id': parsed.run_id, 'operation_id': parsed.operation_id,
                         'request_hash': request_hash, 'status': status, 'error_code': code}}})
        raise
    latest = read_state(root)
    transact(root, latest['version'], f'pr-open-verified:{parsed.operation_id}',
             {'kind': 'domain.pr.open-finish', 'payload': {'request': {
                 'run_id': parsed.run_id, 'operation_id': parsed.operation_id,
                 'request_hash': request_hash, 'status': 'verified', 'receipt': result}}})
    return result
