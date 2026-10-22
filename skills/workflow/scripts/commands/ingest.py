"""Scoped source indexing and durable content-bound cache reuse."""
import json
from pathlib import Path
from .journal import add_journal_options, commit
from workflow_lib.ingestion import ingest_sources, project_source_index
from workflow_lib.documentation import load_documentation_policy
from workflow_lib.evidence import repository_fingerprint
from workflow_lib.store import read_state, WorkflowError


def register_commands(parser):
    command = parser.add_parser('ingest')
    command.add_argument('--repo-json')
    command.add_argument('--repo-id')
    command.add_argument('--scope', action='append', required=True)
    command.add_argument('--profile-json', required=True)
    command.add_argument('--include-history', action='store_true')
    command.add_argument('--required-path', action='append', default=[])
    command.add_argument('--output-mode', choices=('full', 'refs'), default='full')
    add_journal_options(command)


def dispatch(parsed):
    profile = json.loads(Path(parsed.profile_json).read_text(encoding='utf-8'))
    policy = load_documentation_policy(Path(__file__).resolve().parents[4])
    discovery = {'include_history': parsed.include_history, 'required_paths': sorted(set(parsed.required_path))}
    selection = {'history': policy['history'], **discovery}
    if not parsed.root:
        if not parsed.repo_json:
            raise WorkflowError('INVALID_INPUT', 'read-only indexing requires --repo-json')
        if parsed.output_mode == 'refs':
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'reference indexing requires a selected control root')
        return ingest_sources(json.loads(Path(parsed.repo_json).read_text(encoding='utf-8')), parsed.scope, profile, {}, selection_policy=selection)
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
        if stored.get('discovery_options', discovery) != discovery:
            raise WorkflowError('OPERATION_CONFLICT', 'indexing operation ID belongs to another selection')
        result = {**state['data']['domain_receipts'][parsed.operation_id], 'replayed': True, 'state_version': state['version']}
        return _project(result, parsed)
    required = [f['path'] for f in state['data'].get('governing_input_receipt', {}).get('files', {}).values() if f['repo_id'] == parsed.repo_id]
    selection['required_paths'] = sorted(set(selection['required_paths'] + required))
    scope.update(selection_policy=selection, discovery_options=discovery)
    fingerprint = repository_fingerprint(Path(repository['location']))
    cache = dict(state['data'].get('ingestion_cache', {}))
    index = ingest_sources(repository, parsed.scope, profile, cache, selection_policy=selection)
    if repository_fingerprint(Path(repository['location'])) != fingerprint:
        raise WorkflowError('SOURCE_CHANGED', 'repository changed during indexing')
    parsed.expected_version = state['version'] if parsed.expected_version is None else parsed.expected_version
    return _project(commit(parsed, 'domain.ingest.record', {**scope, 'index': index, 'cache': cache, 'repository_fingerprint': fingerprint}), parsed)


def _project(result, parsed):
    if parsed.output_mode == 'full':
        return result
    if 'sources' in result:
        return project_source_index(result, Path(parsed.root))
    if 'index' in result:
        return {**result, 'index': project_source_index(result['index'], Path(parsed.root))}
    if 'index_id' in result:
        index = read_state(Path(parsed.root))['data']['source_indexes'][result['index_id']]
        return {**result, 'index': project_source_index(index, Path(parsed.root))}
    return result
