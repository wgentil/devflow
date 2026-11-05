"""Declared protection inventory and exact Git/index/worktree observations."""
import hashlib
import base64
import os
from pathlib import Path
import stat
import subprocess
from .document_units import digest
from .store import WorkflowError


def _git(repo, *args):
    result = subprocess.run(['git', '--literal-pathspecs', *args], cwd=repo, capture_output=True, check=False)
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
                worktree = {'type': 'symlink', 'target': os.readlink(path), 'referent': _symlink_referent(repo,path)}
            elif stat.S_ISREG(info.st_mode):
                content=path.read_bytes()
                worktree = {'type': 'file', 'sha256': hashlib.sha256(content).hexdigest(),
                            'content_base64': base64.b64encode(content).decode('ascii'), 'executable': bool(info.st_mode & 0o111)}
            else:
                raise WorkflowError('INVALID_PROTECTION_INVENTORY', 'Declare individual regular files or symlinks; directories and special files need explicit file scope.')
        except FileNotFoundError:
            worktree = {'type': 'missing'}
        index = _git(repo, 'ls-files', '--stage', '-z', '--', name)
        commit = _git(repo, 'ls-tree', '-z', 'HEAD', '--', name)
        def preimages(raw, index_layer):
            images = []
            for record in raw.split(b'\0'):
                if not record: continue
                metadata = record.split(b'\t', 1)[0].split()
                oid = metadata[1 if index_layer else 2].decode('ascii')
                mode = metadata[0].decode('ascii')
                # Gitlinks identify another repository rather than a blob.
                content = None if mode == '160000' or set(oid) == {'0'} else _git(repo, 'cat-file', 'blob', oid)
                images.append({'mode': mode, 'object_id': oid,
                    'stage': metadata[2].decode('ascii') if index_layer else None,
                    'content_base64': base64.b64encode(content).decode('ascii') if content is not None else None})
            return images
        entries[name] = {'worktree': worktree, 'index': index.hex(), 'commit': commit.hex(),
            'index_preimages': preimages(index, True), 'commit_preimages': preimages(commit, False)}
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
        raise WorkflowError('PROTECTED_CHANGE_BLOCKED', 'Exact protected-change approval and independent review required.',
            {'observation_hash': expected, 'changed_paths': observation.get('changed_paths', [])[:100],
             'omitted_path_count': max(0, len(observation.get('changed_paths', []))-100)})
    return {'passed': True, 'observation_hash': expected}


def _symlink_referent(repo,path):
    pending=list(path.relative_to(repo).parts);cursor=repo;links=[]
    while pending:
        cursor=cursor/pending.pop(0)
        if cursor.is_symlink():
            if len(links)>=40:raise WorkflowError('PROTECTED_PATH_ESCAPE','Protected link chain is cyclic or too deep.')
            target=os.readlink(cursor)
            links.append({'path':cursor.relative_to(repo).as_posix(),'target':target})
            destination=Path(os.path.normpath(cursor.parent/target))
            if not destination.is_relative_to(repo):
                raise WorkflowError('PROTECTED_PATH_ESCAPE','Protected symlink referents must remain inside the declared repository.')
            pending=list(destination.relative_to(repo).parts)+pending;cursor=repo
    result={'resolved_path':cursor.relative_to(repo).as_posix(),'link_chain':links}
    try:info=cursor.lstat()
    except FileNotFoundError:return {**result,'type':'missing'}
    if not stat.S_ISREG(info.st_mode):raise WorkflowError('INVALID_PROTECTION_INVENTORY','Protected link must resolve to an individual regular file.')
    content=cursor.read_bytes()
    return {**result,'type':'file','sha256':hashlib.sha256(content).hexdigest(),
        'content_base64':base64.b64encode(content).decode('ascii'),'executable':bool(info.st_mode&0o111)}
