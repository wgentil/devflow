"""Scoped source indexing and durable content-bound cache reuse."""
import json
from pathlib import Path
from .journal import add_journal_options, commit
from workflow_lib.ingestion import ingest_sources
from workflow_lib.evidence import repository_fingerprint
from workflow_lib.store import read_state, WorkflowError


def register_commands(parser):
    command = parser.add_parser('ingest')
    command.add_argument('--repo-json')
    command.add_argument('--repo-id')
    command.add_argument('--scope', action='append', required=True)
    command.add_argument('--profile-json', required=True)
    add_journal_options(command)


def dispatch(parsed):
    profile = json.loads(Path(parsed.profile_json).read_text())
    if not parsed.root:
        if not parsed.repo_json:
            raise WorkflowError('INVALID_INPUT', 'read-only indexing requires --repo-json')
        return ingest_sources(json.loads(Path(parsed.repo_json).read_text()), parsed.scope, profile, {})
    state = read_state(Path(parsed.root))
    repository = state['data'].get('repositories', {}).get(parsed.repo_id)
    if repository is None:
        raise WorkflowError('REPOSITORY_NOT_REGISTERED', 'indexing requires a registered --repo-id')
    scope = {'repo_id': parsed.repo_id, 'scope': parsed.scope, 'profile': profile}
    previous = state['operations'].get(parsed.operation_id)
    if previous is not None:
        stored = previous['payload'].get('request', {})
        if previous['kind'] != 'domain.ingest.record' or any(stored.get(k) != v for k, v in scope.items()):
            raise WorkflowError('OPERATION_CONFLICT', 'indexing operation ID belongs to another scope')
        return {**state['data']['domain_receipts'][parsed.operation_id], 'replayed': True, 'state_version': state['version']}
    fingerprint = repository_fingerprint(Path(repository['location']))
    cache = dict(state['data'].get('ingestion_cache', {}))
    index = ingest_sources(repository, parsed.scope, profile, cache)
    if repository_fingerprint(Path(repository['location'])) != fingerprint:
        raise WorkflowError('SOURCE_CHANGED', 'repository changed during indexing')
    parsed.expected_version = state['version'] if parsed.expected_version is None else parsed.expected_version
    return commit(parsed, 'domain.ingest.record', {**scope, 'index': index, 'cache': cache, 'repository_fingerprint': fingerprint})
