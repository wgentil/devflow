"""Visible repository specifications and exact-content pair receipts."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .specs import content_hash, render_spec, validate_spec
from .store import WorkflowError


def _paths(repo: Path, relative_json: str) -> tuple[Path, Path]:
    repo = Path(repo).resolve()
    path = Path(relative_json)
    if path.is_absolute() or '..' in path.parts or path.suffix != '.json':
        raise WorkflowError('SPEC_PATH_ESCAPE', 'specification must use a relative .json path within the repository')
    paths = (repo / path, repo / path.with_suffix('.md'))
    for target in paths:
        if not target.resolve().is_relative_to(repo) or any(part in {'.git', '.devflow'} for part in path.parts):
            raise WorkflowError('SPEC_PATH_ESCAPE', 'specification path escapes the visible repository')
        relative = target.relative_to(repo).as_posix()
        checked = subprocess.run(['git', '-C', str(repo), 'check-ignore', '--no-index', '--', relative],
                                 capture_output=True, text=True)
        if checked.returncode == 0:
            raise WorkflowError('SPEC_PATH_IGNORED', f'specification path is ignored: {relative}')
        if checked.returncode != 1:
            raise WorkflowError('SPEC_REPO_INVALID', 'specification repository must be a Git working tree')
    return paths


def _receipt(repo: Path, json_path: Path, md_path: Path, spec: dict, markdown: bytes) -> dict:
    return {'json_path': json_path.relative_to(repo).as_posix(),
            'markdown_path': md_path.relative_to(repo).as_posix(),
            'content_hash': content_hash(spec), 'markdown_hash': hashlib.sha256(markdown).hexdigest()}


def read_spec_pair(repo: Path, relative_json: str) -> dict:
    repo = Path(repo).resolve()
    json_path, md_path = _paths(repo, relative_json)
    try:
        raw = json_path.read_bytes()
        markdown = md_path.read_bytes()
    except FileNotFoundError as exc:
        raise WorkflowError('SPEC_PAIR_MISSING', 'both specification JSON and Markdown files are required') from exc
    except OSError as exc:
        raise WorkflowError('SPEC_PAIR_UNREADABLE', str(exc)) from exc
    try:
        spec = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise WorkflowError('SPEC_PAIR_INVALID', 'specification JSON is invalid') from exc
    validate_spec(spec)
    if markdown != render_spec(spec).encode('utf-8'):
        raise WorkflowError('SPEC_PAIR_MISMATCH', 'Markdown does not match the deterministic specification rendering')
    return {'spec': spec, **_receipt(repo, json_path, md_path, spec, markdown)}


def write_spec_pair(repo: Path, relative_json: str, spec: dict) -> dict:
    repo = Path(repo).resolve()
    validate_spec(spec)
    json_path, md_path = _paths(repo, relative_json)
    contents = (json.dumps(spec, ensure_ascii=False, sort_keys=True, indent=2) + '\n', render_spec(spec))
    temporary = []
    try:
        for target, content in zip((json_path, md_path), contents):
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=target.parent)
            temporary.append(name)
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        _paths(repo, relative_json)
        for name, target in zip(temporary, (json_path, md_path)):
            os.replace(name, target)
        result = read_spec_pair(repo, relative_json)
        return {key: value for key, value in result.items() if key != 'spec'}
    finally:
        for name in temporary:
            try:
                os.unlink(name)
            except FileNotFoundError:
                pass


def assert_repo_spec_approval(repo: Path, record: dict) -> dict:
    current = read_spec_pair(repo, record['json_path'])
    if any(current[key] != record.get(key) for key in ('json_path', 'markdown_path', 'content_hash', 'markdown_hash')):
        raise WorkflowError('SPEC_APPROVAL_STALE', 'repository specification pair changed since its receipt')
    return current
