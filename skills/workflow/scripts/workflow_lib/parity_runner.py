"""Bounded executable comparison of legacy and replacement pilot behavior."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative(value: str) -> Path | None:
    path = Path(value)
    return path if value and not path.is_absolute() and '..' not in path.parts else None


def verify_pilot(pilot: dict, repository: Path, timeout: int) -> dict:
    """Run trusted commands in separate directories with matching fixture bytes.

    This is comparison setup, not a process sandbox: commands inherit the host
    environment and may access paths outside their working directory.
    """
    base = {'passed': False, 'failure': None, 'input_hashes': {},
            'output_hashes': {}, 'differences': [],
            'comparator_version': pilot.get('comparator', {}).get('version')}
    repository = Path(repository).resolve()
    if type(timeout) is not int or not 1 <= timeout <= 900:
        return {**base, 'failure': 'INVALID_TIMEOUT'}
    comparator = pilot.get('comparator', {})
    if comparator.get('version') != 1 or comparator.get('kind') not in {'exact-bytes', 'json-fields'}:
        return {**base, 'failure': 'INVALID_COMPARATOR'}
    ignored = comparator.get('ignore', [])
    if comparator['kind'] == 'json-fields':
        if not isinstance(ignored, list) or len(set(ignored)) != len(ignored) or not all(
                isinstance(value, str) and value and '.' not in value for value in ignored):
            return {**base, 'failure': 'INVALID_COMPARATOR'}
    elif ignored:
        return {**base, 'failure': 'INVALID_COMPARATOR'}
    fixtures = pilot.get('fixtures')
    if not isinstance(fixtures, list) or not fixtures:
        return {**base, 'failure': 'FIXTURE_REQUIRED'}
    contents = {}
    for row in fixtures:
        if not isinstance(row, dict) or not isinstance(row.get('path'), str):
            return {**base, 'failure': 'FIXTURE_INVALID'}
        relative = _relative(row['path'])
        if relative is None or relative.as_posix() in contents:
            return {**base, 'failure': 'FIXTURE_INVALID'}
        source = (repository / relative).resolve()
        if not source.is_relative_to(repository) or not source.is_file():
            return {**base, 'failure': 'FIXTURE_MISSING'}
        data = source.read_bytes()
        if len(data) > 4 * 1024 * 1024:
            return {**base, 'failure': 'FIXTURE_TOO_LARGE'}
        if _hash(data) != row.get('sha256'):
            return {**base, 'failure': 'FIXTURE_CHANGED'}
        contents[relative.as_posix()] = data
    base['input_hashes'] = {path: _hash(contents[path]) for path in sorted(contents)}
    for name in ('legacy', 'replacement'):
        command = pilot.get(name + '_argv')
        output = pilot.get(name + '_output_path')
        if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
            return {**base, 'failure': 'COMMAND_UNAVAILABLE'}
        if not isinstance(output, str) or _relative(output) is None:
            return {**base, 'failure': 'OUTPUT_PATH_INVALID'}
    outputs = {}
    with tempfile.TemporaryDirectory(prefix='devflow-parity-') as directory:
        for name in ('legacy', 'replacement'):
            cwd = Path(directory) / name
            cwd.mkdir()
            for relative, data in contents.items():
                target = cwd / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            try:
                result = subprocess.run(pilot[name + '_argv'], cwd=cwd, capture_output=True,
                                        timeout=timeout, check=False)
            except subprocess.TimeoutExpired:
                return {**base, 'failure': 'TIMEOUT'}
            except OSError:
                return {**base, 'failure': 'COMMAND_UNAVAILABLE'}
            if any(_hash((cwd / path).read_bytes()) != base['input_hashes'][path]
                   for path in contents if (cwd / path).is_file()):
                return {**base, 'failure': 'INPUT_MUTATED'}
            if any(not (cwd / path).is_file() for path in contents):
                return {**base, 'failure': 'INPUT_MUTATED'}
            if result.returncode != 0:
                return {**base, 'failure': 'COMMAND_FAILED'}
            target = (cwd / pilot[name + '_output_path']).resolve()
            if not target.is_relative_to(cwd.resolve()) or not target.is_file():
                return {**base, 'failure': 'OUTPUT_MISSING'}
            data = target.read_bytes()
            if len(data) > 4 * 1024 * 1024:
                return {**base, 'failure': 'OUTPUT_TOO_LARGE'}
            outputs[name] = data
            base['output_hashes'][name] = _hash(data)
    if comparator['kind'] == 'exact-bytes':
        equal = outputs['legacy'] == outputs['replacement']
        differences = [] if equal else ['bytes']
    else:
        try:
            left, right = (json.loads(outputs[name]) for name in ('legacy', 'replacement'))
        except (ValueError, UnicodeDecodeError):
            return {**base, 'failure': 'OUTPUT_INVALID'}
        if not isinstance(left, dict) or not isinstance(right, dict):
            return {**base, 'failure': 'OUTPUT_INVALID'}
        keys = sorted((set(left) | set(right)) - set(ignored))
        differences = [key for key in keys if left.get(key) != right.get(key)
                       or (key in left) != (key in right)]
        equal = not differences
    return {**base, 'passed': equal, 'failure': None if equal else 'OUTPUT_DIFFERENCE',
            'differences': differences}
