"""Live bindings for declared verification inputs, including ignored files and links."""
import hashlib
import os
from pathlib import Path
import stat
from .store import WorkflowError


def capture_input_bindings(repo: Path, paths: list[str]) -> dict:
    repo = Path(repo).resolve()
    bindings = {}
    for name in paths:
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise WorkflowError('INVALID_TEST_INPUT', 'Verification inputs must stay inside the repository.')
        path = repo / relative
        resolved = path.resolve()
        if not resolved.is_relative_to(repo) or not resolved.is_file():
            raise WorkflowError('INVALID_TEST_INPUT', 'Declared verification input is missing or leaves the repository.')
        info = path.lstat()
        kind = 'symlink' if stat.S_ISLNK(info.st_mode) else 'file' if stat.S_ISREG(info.st_mode) else 'other'
        if kind == 'other': raise WorkflowError('INVALID_TEST_INPUT', 'Regular files or confined symlinks required.')
        binding = {'type': kind, 'resolved_path': resolved.relative_to(repo).as_posix(),
                   'sha256': hashlib.sha256(resolved.read_bytes()).hexdigest(), 'executable': bool(info.st_mode & 0o111)}
        if kind == 'symlink': binding['link_target'] = os.readlink(path)
        bindings[name] = binding
    return bindings


def proof_inputs_current(subject: dict, proof: dict) -> bool:
    contract = proof.get('integrity', {}).get('contract', {})
    hashes, expected = contract.get('input_hashes'), contract.get('input_bindings')
    if not isinstance(hashes, dict) or not hashes or not isinstance(expected, dict) or set(expected) != set(hashes): return False
    repository = subject.get('repositories', {}).get(proof.get('repo_id'), {})
    if not repository.get('location'): return False
    try:
        current = capture_input_bindings(Path(repository['location']), list(hashes))
        return current == expected and all(current[name]['sha256'] == value for name,value in hashes.items())
    except (OSError, ValueError, WorkflowError): return False
