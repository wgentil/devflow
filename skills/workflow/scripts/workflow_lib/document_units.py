"""Exact document projections and complete, registered dependency closure."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

from .git_paths import resolve_repo_path
from .store import WorkflowError


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def document_path(source: dict) -> Path:
    try:
        root = Path(source['root']).resolve()
        relative = source['path']
        target = resolve_repo_path(root, relative)
        for path in (Path(relative), target.relative_to(root)):
            if any(part in {'.git', '.devflow'} for part in path.parts):
                raise ValueError('private source path')
        lexical = root / relative
        if any(p.is_symlink() for p in (lexical, *lexical.parents) if p.is_relative_to(root)):
            raise ValueError('symlink source path')
        # Package fixtures may be plain directories; registered Git sources obey ignore policy.
        if (root / '.git').exists():
            result = subprocess.run(['git', '-C', str(root), 'check-ignore', '--no-index', '--', relative],
                                    capture_output=True, timeout=5)
            if result.returncode != 1:
                raise ValueError('ignored or unavailable source path')
        return target
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        raise WorkflowError('CONTEXT_SOURCE_INVALID', 'source must be visible within its registered repository') from exc


def markdown_section(text: str, heading: list[str]) -> str:
    if not isinstance(heading, list) or not heading or any(not isinstance(v, str) or not v for v in heading):
        raise WorkflowError('CONTEXT_SELECTOR_INVALID', 'Markdown selection needs an exact heading path')
    lines = text.splitlines(keepends=True)
    headings = []
    stack = []
    fence = None
    for index, line in enumerate(lines):
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line.rstrip('\r\n'))
        if marker:
            token, tail = marker.groups()
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not tail.strip():
                fence = None
            continue
        if fence:
            continue
        match = re.match(r'^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*(?:\r?\n)?$', line)
        if match:
            level, title = len(match[1]), match[2]
            stack = [(depth, name) for depth, name in stack if depth < level]
            stack.append((level, title))
            headings.append((index, level, [name for _, name in stack]))
    matches = [entry for entry in headings if entry[2] == heading]
    if len(matches) != 1:
        raise WorkflowError('CONTEXT_SECTION_UNAVAILABLE', 'Markdown heading is missing or ambiguous', {'heading': heading})
    start, level, _ = matches[0]
    end = next((index for index, depth, _ in headings if index > start and depth <= level), len(lines))
    return ''.join(lines[start:end])


def json_pointer(value, pointer: str):
    if not isinstance(pointer, str) or pointer and not pointer.startswith('/'):
        raise WorkflowError('CONTEXT_SELECTOR_INVALID', 'JSON Pointer must be empty or start with /')
    try:
        for token in pointer.split('/')[1:] if pointer else []:
            if re.search(r'~(?![01])', token):
                raise ValueError('invalid JSON Pointer escape')
            token = token.replace('~1', '/').replace('~0', '~')
            if isinstance(value, list):
                if not re.fullmatch(r'0|[1-9][0-9]*', token):
                    raise ValueError('invalid array index')
                value = value[int(token)]
            elif isinstance(value, dict):
                value = value[token]
            else:
                raise ValueError('pointer traverses a scalar')
        return value
    except (KeyError, IndexError, ValueError) as exc:
        raise WorkflowError('CONTEXT_POINTER_UNAVAILABLE', 'JSON Pointer cannot be resolved') from exc


def _references(value):
    if isinstance(value, dict):
        if any(k in value for k in ('$dynamicRef', '$recursiveRef')):
            raise WorkflowError('CONTEXT_DEPENDENCY_UNSUPPORTED', 'dynamic/recursive references require whole supported dependency semantics')
        if '$ref' in value:
            if not isinstance(value['$ref'], str):
                raise WorkflowError('CONTEXT_DEPENDENCY_UNSUPPORTED', '$ref must be a string')
            yield value['$ref']
        for child in value.values():
            yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def select_document_units(sources: dict, selections: list[dict], policy: dict) -> dict:
    units, hashes, edges, loaded, files = {}, {}, {}, {}, {}
    path_ids = {}
    for sid, source in sources.items():
        # Build the registration map without repeatedly running Git for unused
        # sections. Selected sources are independently checked before every read.
        try:
            target = resolve_repo_path(Path(source['root']), source['path'])
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowError('CONTEXT_SOURCE_INVALID', 'invalid registered source path') from exc
        path_ids.setdefault(str(target), []).append(sid)

    def visit(sid, selector, reason):
        if sid not in sources:
            raise WorkflowError('CONTEXT_REQUIRED_SOURCE_MISSING', f'required source {sid} is not registered')
        definition = policy.get('sources', {}).get(sid, {})
        selector = selector or definition.get('selector') or {'kind': 'whole'}
        uid = sid + '#' + digest(selector)[:16]
        if uid in units:
            units[uid]['reasons'] = sorted(set(units[uid]['reasons'] + [reason]))
            return uid
        path = document_path(sources[sid])
        if sid not in loaded:
            try:
                if str(path) not in files:
                    raw = path.read_bytes()
                    files[str(path)] = (raw, raw.decode('utf-8'))
                raw, text = files[str(path)]
            except (OSError, UnicodeError) as exc:
                raise WorkflowError('CONTEXT_REQUIRED_SOURCE_MISSING', f'cannot read required source {sid}') from exc
            hashes[sid] = hashlib.sha256(raw).hexdigest()
            expected = sources[sid].get('content_hash')
            if expected and expected != hashes[sid]:
                raise WorkflowError('CONTEXT_SOURCE_CHANGED', f'required source {sid} changed')
            loaded[sid] = text
        text = loaded[sid]
        kind = selector.get('kind')
        value = None
        if path.suffix.lower() == '.json':
            try:
                value = json.loads(text)
            except ValueError as exc:
                raise WorkflowError('CONTEXT_SOURCE_INVALID', f'invalid JSON source {sid}') from exc
        if kind == 'whole':
            content = text
        elif kind == 'markdown' and path.suffix.lower() == '.md':
            content = markdown_section(text, selector.get('heading'))
        elif kind == 'json-pointer' and path.suffix.lower() == '.json':
            value = json_pointer(value, selector.get('pointer', ''))
            content = canonical(value).decode('utf-8')
        else:
            raise WorkflowError('CONTEXT_SELECTOR_UNSUPPORTED', f'unsupported selector for {sid}')
        units[uid] = {'id': uid, 'source_id': sid, 'selector': selector, 'content': content,
                      'content_hash': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                      'source_hash': hashes[sid], 'path': sources[sid]['path'], 'reasons': [reason]}
        edges[uid] = []
        for dependency in definition.get('dependencies', []):
            edges[uid].append(visit(dependency, None, 'dependency:' + uid))
        if value is not None:
            for ref in _references(value):
                parsed = urlsplit(ref)
                if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment and not unquote(parsed.fragment).startswith('/'):
                    raise WorkflowError('CONTEXT_DEPENDENCY_UNSUPPORTED', f'unsupported reference {ref}')
                target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
                ids = path_ids.get(str(target), [])
                if not ids:
                    raise WorkflowError('CONTEXT_DEPENDENCY_UNREGISTERED', f'unregistered reference {ref}')
                target_sid = sid if sid in ids else sorted(ids)[0]
                dep_selector = {'kind': 'json-pointer', 'pointer': unquote(parsed.fragment)}
                edges[uid].append(visit(target_sid, dep_selector, 'reference:' + uid))
        edges[uid] = sorted(set(edges[uid]))
        return uid

    for selection in selections:
        visit(selection['source_id'], selection.get('selector'), selection.get('reason', 'required'))
    return {'units': [units[k] for k in sorted(units)], 'dependencies': dict(sorted(edges.items())),
            'required_ids': sorted({u['source_id'] for u in units.values()}), 'source_hashes': dict(sorted(hashes.items())),
            'retrieval_calls': len(files)}
