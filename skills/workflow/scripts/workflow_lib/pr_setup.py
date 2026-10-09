"""Reconcile the dedicated GitHub ruleset for DevFlow PR reviews."""

from __future__ import annotations

import re
from urllib.parse import quote

from .store import WorkflowError

RULESET_NAME = 'DevFlow PR review'
STATUS_CONTEXT = 'devflow/pr-review'


def _repo_path(owner: str, repo: str) -> str:
    if any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', value)
           for value in (owner, repo)):
        raise WorkflowError('PR_REPOSITORY_INVALID', 'GitHub owner and repository names are required')
    return f'/repos/{owner}/{repo}'


def _branch(base: str) -> str:
    if not isinstance(base, str) or not base or base.startswith('/') or '..' in base.split('/'):
        raise WorkflowError('PR_BASE_INVALID', 'target branch is invalid')
    return f'refs/heads/{base}'


def _rulesets(client, owner: str, repo: str) -> tuple[str, list[dict]]:
    path = _repo_path(owner, repo) + '/rulesets'
    listed = []
    for page in range(1, 101):
        batch = client.api('GET', f'{path}?per_page=100&page={page}')
        if not isinstance(batch, list):
            raise WorkflowError('GITHUB_RESPONSE_INVALID', 'ruleset listing must be an array')
        listed.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise WorkflowError('PR_RULESET_LIST_INCOMPLETE', 'ruleset listing may be incomplete')
    matches = [rule for rule in listed if isinstance(rule, dict) and rule.get('name') == RULESET_NAME
               and rule.get('source_type', 'Repository') == 'Repository']
    if len(matches) > 1:
        raise WorkflowError('PR_RULESET_CONFLICT', 'multiple DevFlow PR rulesets exist')
    return path, matches


def _resolve_actors(client, owner: str, actors: list[dict]) -> list[dict]:
    if not isinstance(actors, list) or not actors:
        raise WorkflowError('PR_BYPASS_ACTOR_INVALID', 'choose at least one trusted direct-push bypass actor')
    resolved = []
    for actor in actors:
        if not isinstance(actor, dict) or actor.get('actor_type') not in {'User', 'Team'}:
            raise WorkflowError('PR_BYPASS_ACTOR_INVALID', 'bypass actors must name a GitHub user or team')
        if actor['actor_type'] == 'User':
            login = actor.get('login')
            if not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9-]+', login):
                raise WorkflowError('PR_BYPASS_ACTOR_INVALID', 'user bypass actor needs a login')
            observed = client.api('GET', f'/users/{quote(login)}')
        else:
            slug = actor.get('slug')
            if not isinstance(slug, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', slug):
                raise WorkflowError('PR_BYPASS_ACTOR_INVALID', 'team bypass actor needs a slug')
            observed = client.api('GET', f'/orgs/{quote(owner)}/teams/{quote(slug)}')
        identifier = observed.get('id') if isinstance(observed, dict) else None
        if type(identifier) is not int or identifier <= 0:
            raise WorkflowError('PR_BYPASS_ACTOR_INVALID', 'bypass actor could not be resolved')
        resolved.append({'actor_id': identifier, 'actor_type': actor['actor_type'], 'bypass_mode': 'always'})
    if len({(actor['actor_type'], actor['actor_id']) for actor in resolved}) != len(resolved):
        raise WorkflowError('PR_BYPASS_ACTOR_INVALID', 'duplicate bypass actor')
    return sorted(resolved, key=lambda actor: (actor['actor_type'], actor['actor_id']))


def _required_rule() -> dict:
    return {'type': 'required_status_checks', 'parameters': {
        'strict_required_status_checks_policy': True,
        'required_status_checks': [{'context': STATUS_CONTEXT}]}}


def _desired(base: str, actors: list[dict]) -> dict:
    return {'name': RULESET_NAME, 'target': 'branch', 'enforcement': 'active',
            'bypass_actors': actors,
            'conditions': {'ref_name': {'include': [_branch(base)], 'exclude': []}},
            'rules': [_required_rule()]}


def _matches(rule: dict, base: str, actors: list[dict] | None = None) -> bool:
    if not isinstance(rule, dict):
        return False
    checks = [value for value in rule.get('rules', []) if isinstance(value, dict)
              and value.get('type') == 'required_status_checks']
    actual_actors = rule.get('bypass_actors', [])
    return (rule.get('name') == RULESET_NAME and rule.get('target') == 'branch'
            and rule.get('enforcement') == 'active'
            and rule.get('conditions', {}).get('ref_name', {}).get('include') == [_branch(base)]
            and len(checks) == 1 and checks[0] == _required_rule()
            and (actors is None or sorted(actual_actors, key=lambda actor: (actor.get('actor_type'), actor.get('actor_id'))) == actors))


def inspect_pr_setup(client, owner: str, repo: str, base: str) -> dict:
    path, matches = _rulesets(client, owner, repo)
    if not matches:
        return {'configured': False, 'owner': owner, 'repo': repo, 'base': base, 'ruleset_id': None}
    identifier = matches[0].get('id')
    if type(identifier) is not int or identifier <= 0:
        raise WorkflowError('GITHUB_RESPONSE_INVALID', 'ruleset ID is invalid')
    observed = client.api('GET', f'{path}/{identifier}')
    return {'configured': _matches(observed, base), 'owner': owner, 'repo': repo,
            'base': base, 'ruleset_id': identifier, 'ruleset': observed}


def configure_pr_setup(client, owner: str, repo: str, base: str,
                       bypass_actors: list[dict]) -> dict:
    actors = _resolve_actors(client, owner, bypass_actors)
    path, matches = _rulesets(client, owner, repo)
    desired = _desired(base, actors)
    if matches:
        identifier = matches[0].get('id')
        if type(identifier) is not int or identifier <= 0:
            raise WorkflowError('GITHUB_RESPONSE_INVALID', 'ruleset ID is invalid')
        detail_path = f'{path}/{identifier}'
        prior = client.api('GET', detail_path)
        if not _matches(prior, base, actors):
            client.api('PUT', detail_path, desired)
    else:
        created = client.api('POST', path, desired)
        identifier = created.get('id') if isinstance(created, dict) else None
        if type(identifier) is not int or identifier <= 0:
            raise WorkflowError('PR_RULESET_UNVERIFIED', 'GitHub did not return a ruleset ID')
        detail_path = f'{path}/{identifier}'
    observed = client.api('GET', detail_path)
    if not _matches(observed, base, actors):
        raise WorkflowError('PR_RULESET_UNVERIFIED', 'GitHub ruleset readback differs from requested PR policy')
    return {'verified': True, 'ruleset_id': identifier, 'owner': owner, 'repo': repo,
            'base': base, 'context': STATUS_CONTEXT, 'bypass_actors': actors}


def verify_pr_setup(client, owner: str, repo: str, base: str,
                    bypass_actors: list[dict]) -> dict:
    actors = _resolve_actors(client, owner, bypass_actors)
    observed = inspect_pr_setup(client, owner, repo, base)
    if not observed['configured'] or not _matches(observed.get('ruleset'), base, actors):
        raise WorkflowError('PR_SETUP_UNCERTAIN', 'GitHub policy is not yet verified; inspect before retrying a write')
    return {'verified': True, 'ruleset_id': observed['ruleset_id'], 'owner': owner,
            'repo': repo, 'base': base, 'context': STATUS_CONTEXT, 'bypass_actors': actors}
