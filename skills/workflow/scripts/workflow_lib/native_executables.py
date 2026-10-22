"""Resolve known Windows host shims without evaluating batch/shell text."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

PACKAGES = {'codex': '@openai/codex', 'claude': '@anthropic-ai/claude-code'}


def resolve_native_argv(argv: list[str], *, platform_name: str | None = None) -> list[str]:
    platform_name = os.name if platform_name is None else platform_name
    if platform_name != 'nt' or not argv:
        return list(argv)
    requested = Path(argv[0])
    host = requested.stem.lower()
    if host not in PACKAGES:
        return list(argv)
    if requested.parent != Path('.') or requested.is_absolute():
        executable = requested
    else:
        located = shutil.which(argv[0])
        if not located:
            raise OSError(f'{host} executable is unavailable')
        executable = Path(located)
    if not executable.is_file():
        raise OSError(f'{host} executable is unavailable')
    if executable.suffix.lower() == '.exe':
        return [str(executable.resolve()), *argv[1:]]
    if executable.suffix.lower() not in {'.cmd', '.bat'}:
        raise OSError(f'{host} needs a native executable or recognized npm launcher')
    # Read package metadata, never the wrapper's command text.
    candidates = [executable.parent / 'node_modules' / PACKAGES[host]]
    if executable.parent.name.lower() == '.bin':
        candidates.append(executable.parent.parent / PACKAGES[host])
    matches = []
    for package in candidates:
        manifest = package / 'package.json'
        if not manifest.is_file():
            continue
        try:
            metadata = json.loads(manifest.read_text(encoding='utf-8'))
            if not isinstance(metadata, dict) or metadata.get('name') != PACKAGES[host]:
                raise ValueError('unexpected package identity')
            declared = metadata.get('bin')
            entry_name = declared.get(host) if isinstance(declared, dict) else declared
            if not isinstance(entry_name, str) or not entry_name:
                raise ValueError('missing host entry point')
            entry = (package / entry_name).resolve()
            if not entry.is_relative_to(package.resolve()) or not entry.is_file():
                raise ValueError('host entry point is missing or outside its package')
            matches.append(entry)
        except (OSError, ValueError, TypeError) as exc:
            raise OSError(f'{host} npm package entry is unavailable or invalid') from exc
    if len(matches) != 1:
        raise OSError(f'{host} npm package entry is missing or ambiguous')
    entry = matches[0]
    if entry.suffix.lower() == '.exe':
        return [str(entry), *argv[1:]]
    if entry.suffix.lower() not in {'.js', '.cjs', '.mjs'}:
        raise OSError(f'{host} npm entry is not a supported executable or JavaScript file')
    node = shutil.which('node.exe')
    if not node or Path(node).suffix.lower() != '.exe' or not Path(node).is_file():
        raise OSError(f'{host} npm installation requires a native Node executable')
    return [str(Path(node).resolve()), str(entry), *argv[1:]]
