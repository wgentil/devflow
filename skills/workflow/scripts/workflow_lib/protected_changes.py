"""Declared protection inventory and exact Git/index/worktree observations."""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
from .document_units import digest
from .store import WorkflowError


def _git(repo, *args):
    result = subprocess.run(['git', *args], cwd=repo, capture_output=True, check=False)
    if result.returncode: raise WorkflowError('PROTECTION_OBSERVATION_FAILED', result.stderr.decode('utf-8', 'replace'))
    return result.stdout


def snapshot_protected(repo: Path, inventory: dict) -> dict:
    repo = Path(repo).resolve()
    paths = inventory.get('paths')
    if not isinstance(paths, list) or any(not isinstance(p, str) or not p or Path(p).is_absolute() or '..' in Path(p).parts for p in paths):
        raise WorkflowError('INVALID_PROTECTION_INVENTORY', 'Declare repository-relative protected paths.')
    entries = {}
    for name in sorted(set(paths)):
        path = repo / name
        if not path.parent.resolve().is_relative_to(repo):
            raise WorkflowError('PROTECTED_PATH_ESCAPE', 'Protected parent leaves the repository.')
        try:
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                worktree = {'type': 'symlink', 'target': os.readlink(path)}
            elif stat.S_ISREG(info.st_mode):
                worktree = {'type': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'executable': bool(info.st_mode & 0o111)}
            else:
                worktree = {'type': 'other', 'mode': info.st_mode}
        except FileNotFoundError:
            worktree = {'type': 'missing'}
        entries[name] = {'worktree': worktree,
            'index': _git(repo, 'ls-files', '--stage', '-z', '--', name).hex(),
            'commit': _git(repo, 'ls-tree', '-z', 'HEAD', '--', name).hex()}
    return {'schema_version': 1, 'inventory': inventory, 'inventory_hash': digest(inventory), 'entries': entries}


def observe_protected_changes(repo: Path, inventory: dict, baseline: dict) -> dict:
    combined = {**inventory, 'paths': sorted(set(inventory.get('paths', [])) | set(baseline['inventory']['paths']))}
    current = snapshot_protected(repo, combined)
    changed = [name for name in current['entries'] if current['entries'][name] != baseline['entries'].get(name)]
    observation = {'schema_version': 1, 'baseline_hash': digest(baseline), 'before': baseline,
        'after': current, 'inventory_changed': digest(inventory) != baseline['inventory_hash'],
        'changed_paths': changed}
    observation['observation_hash'] = digest(observation)
    return observation


def validate_protected_changes(observation: dict, authorizations: list[dict], reviews: list[dict]) -> dict:
    expected = digest({k:v for k,v in observation.items() if k != 'observation_hash'})
    if expected != observation.get('observation_hash'):
        raise WorkflowError('PROTECTED_CHANGE_BLOCKED', 'Observation hash mismatch.')
    if not observation.get('changed_paths') and not observation.get('inventory_changed'):
        return {'passed': True, 'observation_hash': expected}
    approvals = [a for a in authorizations if a.get('approved') is True and a.get('observation_hash') == expected
                 and a.get('actor_id') and a.get('reason')]
    independent = [r for r in reviews if r.get('observation_hash') == expected and r.get('verdict') == 'pass'
                   and r.get('actor_id') and r.get('implementer_actor') and r['actor_id'] != r['implementer_actor']
                   and r.get('invocation_ref')]
    if not approvals or not independent:
        raise WorkflowError('PROTECTED_CHANGE_BLOCKED', 'Exact protected-change approval and independent review required.')
    return {'passed': True, 'observation_hash': expected}
