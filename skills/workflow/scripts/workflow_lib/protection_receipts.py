"""Compact protected-content receipts, validated without live reads during replay."""
from copy import deepcopy
from .document_units import digest
from .protected_changes import validate_protected_changes
from .store import WorkflowError


def _require(ok, message):
    if not ok: raise WorkflowError('PROTECTION_RECEIPT_REQUIRED', message)


def independent_dispositions(subject: dict, hashes: set[str], *, live: bool) -> list[dict]:
    from .stored_records import require_package
    from .review_enforcement import review_bindings_current
    implementers = set(subject.get('implementer_actors', [])) | {subject.get('actors', {}).get('implementer')}
    accepted = []
    for rows in subject.get('reviews', {}).values():
        for review in rows:
            relevant = [d for d in review.get('protected_dispositions', []) if d.get('observation_hash') in hashes]
            if not relevant: continue
            if (not review.get('actor_id') or review['actor_id'] in implementers or not review.get('invocation_ref')
                    or review.get('fresh') is False or review.get('verdict') not in {'pass', 'request-changes', 'block'}): continue
            package = require_package(subject.get('review_packages', {}).get(review.get('package_hash')))
            if not package or package.get('source_identity') != subject.get('source_identity'): continue
            if subject.get('review_contract_hash'):
                from .session_evidence import package_current
                if not package_current(subject,package):continue
                observations=package.get('protection_observations',{})
                if not all(d['observation_hash'] in {o['observation_hash'] for o in observations.values()} for d in relevant):continue
                if live:
                    from .enforcement_live import protection_observations
                    if observations!=protection_observations(subject):continue
            elif live:
                from .host_completion import package_current
                if not package_current(subject, package): continue
            elif not review_bindings_current(subject, package, live=False): continue
            accepted.extend({**d, 'actor_id': review['actor_id'], 'invocation_ref': review['invocation_ref'],
                'implementer_actor': subject.get('actors', {}).get('implementer')} for d in relevant)
    return accepted


def make_receipts(subject: dict, observations: dict, *, live: bool) -> dict:
    required = {o['observation_hash'] for o in observations.values() if o.get('changed_paths') or o.get('inventory_changed')}
    independent = independent_dispositions(subject, required, live=live)
    receipts = {}
    for repo_id, observation in observations.items():
        validate_protected_changes(observation, subject.get('protected_authorizations', []), independent)
        inventory = subject['protected_inventories'][repo_id]
        receipts[repo_id] = {'schema_version': 1, 'repo_id': repo_id,
            'inventory_hash': digest(inventory['inventory']), 'baseline_hash': digest(inventory['baseline']),
            'observation_hash': observation['observation_hash'], 'after_hash': digest(observation['after'])}
    return receipts


def _unchanged(inventory: dict, baseline: dict) -> dict:
    combined = {**inventory, 'paths': sorted(set(inventory['paths']) | set(baseline['inventory']['paths']))}
    after = {**deepcopy(baseline), 'inventory': combined, 'inventory_hash': digest(combined)}
    observation = {'schema_version': 1, 'baseline_hash': digest(baseline), 'before': baseline,
        'after': after, 'inventory_changed': digest(inventory) != baseline['inventory_hash'], 'changed_paths': []}
    observation['observation_hash'] = digest(observation)
    return observation


def validate_receipts(subject: dict, receipts: dict) -> None:
    inventories = subject.get('protected_inventories', {})
    _require(isinstance(receipts, dict) and bool(inventories)
        and set(receipts) == set(inventories) == set(subject.get('repositories', {})),
        'Receipts must cover every declared repository protection inventory.')
    observations = {}
    for repo_id, receipt in receipts.items():
        _require(isinstance(receipt, dict) and receipt.get('schema_version') == 1 and receipt.get('repo_id') == repo_id,
            'Versioned repository protection receipt required.')
        row = inventories[repo_id]
        _require(receipt.get('inventory_hash') == digest(row['inventory'])
            and receipt.get('baseline_hash') == digest(row['baseline']), 'Current governing inventory and retained baseline required.')
        observation = _unchanged(row['inventory'], row['baseline'])
        if receipt.get('observation_hash') != observation['observation_hash']:
            proposal = subject.get('protected_change_proposals', {}).get(receipt.get('observation_hash'), {})
            _require(proposal.get('repo_id') == repo_id, 'Exact retained protected-change proposal required.')
            observation = proposal.get('observation', {})
            _require(observation.get('before') == row['baseline'], 'Proposal must retain the current baseline.')
        _require(receipt.get('observation_hash') == observation.get('observation_hash')
            and receipt.get('after_hash') == digest(observation.get('after')), 'Exact protected-content observation required.')
        observations[repo_id] = observation
    _require(make_receipts(subject, observations, live=False) == receipts, 'Protection receipt differs from current authorization and review.')


def validate_diagnostic_observations(subject,observations):
    inventories=subject.get('protected_inventories',{})
    _require(isinstance(observations,dict) and bool(inventories) and set(observations)==set(inventories)==set(subject.get('repositories',{})),
             'Diagnostic observations must cover every declared protection inventory.')
    for repo_id,observation in observations.items():
        row=inventories[repo_id]
        _require(observation.get('before')==row['baseline'] and observation.get('baseline_hash')==digest(row['baseline'])
                 and observation.get('after',{}).get('inventory_hash')==digest(row['inventory'])
                 and observation.get('observation_hash')==digest({k:v for k,v in observation.items() if k!='observation_hash'}),
                 'Exact protected observation required for diagnostic review; it is not an approval receipt.')
