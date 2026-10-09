"""GitHub PR setup and later PR lifecycle commands."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from workflow_lib.github_pr import GithubClient
from workflow_lib.pr_setup import configure_pr_setup, inspect_pr_setup, verify_pr_setup
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


def _request(path: str) -> dict:
    try:
        request = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError('PR_SETUP_REQUEST_INVALID', 'read a valid PR setup request JSON file') from exc
    if not isinstance(request, dict) or not all(key in request for key in ('owner', 'repo', 'base', 'bypass_actors')):
        raise WorkflowError('PR_SETUP_REQUEST_INVALID', 'request needs owner, repo, base, and bypass actors')
    return request


def _hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def dispatch(parsed: argparse.Namespace) -> dict:
    request = _request(parsed.request_file)
    client = GithubClient()
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
