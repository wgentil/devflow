"""Live source/protection observation. Never called by historical reducers."""

from .action_policy import enforcement_version
from pathlib import Path
from .document_units import digest
from .store import WorkflowError


def source_observation(subject: dict) -> dict:
    from .evidence import repository_fingerprint
    repositories = subject.get('repositories', {})
    if not repositories:
        raise WorkflowError('SOURCE_OBSERVATION_REQUIRED', 'Registered repositories required for current source identity.')
    snapshots = {key: repository_fingerprint(Path(row['location'])) for key,row in repositories.items()}
    return {'snapshots': snapshots, 'source_identity': digest(snapshots)}


def assert_source_current(subject: dict) -> None:
    if enforcement_version(subject) is None: return
    observed = source_observation(subject)
    if observed['source_identity'] != subject.get('source_identity'):
        raise WorkflowError('SOURCE_BINDING_STALE', 'Observe current source and renew affected evidence before acceptance.')


def assert_protection_current(subject: dict) -> dict:
    if enforcement_version(subject) is None: return {}
    from .protected_changes import observe_protected_changes, validate_protected_changes
    protections = subject.get('protected_inventories')
    if not isinstance(protections, dict) or set(protections) != set(subject.get('repositories', {})):
        raise WorkflowError('PROTECTION_INVENTORY_REQUIRED', 'Declare the governing protection inventory for every repository.')
    observations = {}
    for key,row in protections.items():
        observations[key] = observe_protected_changes(Path(subject['repositories'][key]['location']), row['inventory'], row['baseline'])
    from .protection_receipts import make_receipts
    return make_receipts(subject, observations, live=True)
