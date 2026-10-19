"""Canonical documentation routing, deterministic generation and byte checks."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .document_units import select_document_units
from .store import WorkflowError

BUDGETS = {'entry_bytes', 'aggregate_entry_bytes', 'common_bytes', 'domain_bytes', 'initial_load_bytes'}


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def load_documentation_policy(package_root: Path) -> dict:
    try:
        value = json.loads((Path(package_root) / 'definitions/documentation.json').read_text(encoding='utf-8'), object_pairs_hook=_unique_pairs)
        if type(value.get('schema_version')) is not int or value['schema_version'] != 1:
            raise ValueError('unsupported documentation policy version')
        sources, stages, budgets = value['sources'], value['stage_reads'], value['budgets']
        if not isinstance(sources, dict) or not sources or not isinstance(stages, dict) or not stages:
            raise ValueError('source and stage registries are required')
        if not BUDGETS.issubset(budgets) or any(type(v) is not int or v <= 0 for v in budgets.values()):
            raise ValueError('positive integer byte budgets required')
        for sid, source in sources.items():
            if not sid or not isinstance(source.get('path'), str) or not source['path']:
                raise ValueError('source ID and path required')
            if source.get('classification') not in {'active', 'history'} or not isinstance(source.get('selector'), dict):
                raise ValueError('source selector/classification required')
            deps = source.get('dependencies')
            if not isinstance(deps, list) or any(dep not in sources for dep in deps):
                raise ValueError('unknown source dependency')
        if any(not isinstance(ids, list) or not ids or any(sid not in sources for sid in ids) for ids in stages.values()):
            raise ValueError('unknown or empty stage read route')
        if not isinstance(value.get('history'), list) or any(not isinstance(p, str) for p in value['history']):
            raise ValueError('history path patterns required')
        return value
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise WorkflowError('DOCUMENTATION_POLICY_INVALID', str(exc)) from exc


def navigation(policy: dict, stage: str) -> str:
    lines = ['<!-- devflow:routes:' + stage + ' -->']
    for sid in policy['stage_reads'][stage]:
        source = policy['sources'][sid]
        selector = source['selector']
        section = ' → ' + ' / '.join(selector['heading']) if selector['kind'] == 'markdown' else ''
        lines.append(f"- `{sid}`: `{source['path']}`{section}")
    return '\n'.join(lines + ['<!-- /devflow:routes -->'])


def discover_documentation(package_root: Path, *, include_history: bool = False, required_ids: list[str] | None = None) -> dict:
    policy = load_documentation_policy(package_root)
    known_paths = {source['path'] for source in policy['sources'].values()}
    for pattern in policy['history']:
        for path in sorted(Path(package_root).glob(pattern)):
            if path.is_file() and path.suffix.lower() in {'.md', '.json'}:
                relative = path.relative_to(package_root).as_posix()
                if relative not in known_paths:
                    policy['sources']['history:' + relative] = {'path': relative, 'selector': {'kind': 'whole'},
                        'dependencies': [], 'classification': 'history'}
    required = set()
    def visit(sid):
        if sid not in policy['sources']:
            raise WorkflowError('CONTEXT_REQUIRED_SOURCE_MISSING', f'unknown documentation ID {sid}')
        if sid in required:
            return
        required.add(sid)
        for dependency in policy['sources'][sid]['dependencies']:
            visit(dependency)
    for sid in required_ids or []:
        visit(sid)
    selected, excluded = {}, []
    for sid, source in sorted(policy['sources'].items()):
        if source['classification'] == 'history' and not include_history and sid not in required:
            excluded.append(sid)
        else:
            selected[sid] = source
    from .document_units import digest
    return {'sources': selected, 'excluded_ids': excluded, 'include_history': include_history,
            'required_ids': sorted(required), 'policy_hash': digest(policy)}


def check_documentation(package_root: Path, *, check_generated: bool = True) -> dict:
    root = Path(package_root)
    policy = load_documentation_policy(root)
    sources = {sid: {'root': str(root), 'path': definition['path']} for sid, definition in policy['sources'].items()}
    problems, sizes, loads = [], {}, {}
    paragraphs = Counter()
    for sid in sources:
        try:
            selected = select_document_units(sources, [{'source_id': sid}], policy)
            for unit in selected['units']:
                size = len(unit['content'].encode('utf-8'))
                sizes[unit['id']] = size
                limit = policy['budgets']['common_bytes' if unit['source_id'] == 'common' else 'domain_bytes']
                if size > limit:
                    problems.append(f"{unit['id']} exceeds {limit} bytes: {size}")
        except WorkflowError as exc:
            problems.append(f'{sid}: {exc.code}: {exc}')
    for stage, ids in policy['stage_reads'].items():
        try:
            selected = select_document_units(sources, [{'source_id': sid} for sid in ids], policy)
            loads[stage] = sum(len(u['content'].encode('utf-8')) for u in selected['units'])
            if loads[stage] > policy['budgets']['initial_load_bytes']:
                problems.append(f'{stage} initial load exceeds budget: {loads[stage]}')
        except WorkflowError as exc:
            problems.append(f'{stage}: {exc.code}')
    entries = sorted(root.glob('skills/*/SKILL.md'))
    entry_sizes = {p.relative_to(root).as_posix(): len(p.read_bytes()) for p in entries}
    for path, size in entry_sizes.items():
        if size > policy['budgets']['entry_bytes']:
            problems.append(f'{path} entry exceeds budget: {size}')
    total = sum(entry_sizes.values())
    if total > policy['budgets']['aggregate_entry_bytes']:
        problems.append(f'aggregate skill entries exceed budget: {total}')
    baseline = policy.get('baseline', {}).get('aggregate_entry_bytes')
    if baseline and total > baseline // 2:
        problems.append('aggregate skill entries exceed the required 50% reduction')
    for entry in entries:
        text = entry.read_text(encoding='utf-8')
        front = re.match(r'^---\n(.*?)\n---\n', text, re.S)
        if not front or not re.search(r'^name: ' + re.escape(entry.parent.name) + r'\s*$', front[1], re.M) or not re.search(r'^description: \S', front[1], re.M):
            problems.append(f'{entry.relative_to(root)} invalid skill metadata')
        elif (len(entry.parent.name) > 64 or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', entry.parent.name)
              or len(re.search(r'^description: (.+)$', front[1], re.M)[1]) > 1024
              or re.search(r'^description: .*([<>]|\[TODO:)', front[1], re.M)):
            problems.append(f'{entry.relative_to(root)} invalid skill name/description')
        route = policy['stage_reads'].get(entry.parent.name, [])
        if 'skill.' + entry.parent.name not in route or 'common' not in route:
            problems.append(f'{entry.relative_to(root)} missing required stage reads')
    for path in sorted({root / s['path'] for s in policy['sources'].values()}):
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        for paragraph in re.split(r'\n\s*\n', text):
            normalized = ' '.join(paragraph.split())
            if len(normalized.encode('utf-8')) >= 200:
                paragraphs[normalized] += 1
        if check_generated:
            for match in re.finditer(r'<!-- devflow:routes:([^ >]+) -->.*?<!-- /devflow:routes -->', text, re.S):
                stage = match[1]
                if stage not in policy['stage_reads'] or match[0] != navigation(policy, stage):
                    problems.append(f'{path.relative_to(root)} generated routes drifted: {stage}')
    documents = set(root.glob('*.md')) | set(root.glob('docs/**/*.md')) | set(root.glob('skills/**/*.md'))
    documents.update(root / source['path'] for source in policy['sources'].values() if source['path'].endswith('.md'))
    problems.extend(_check_links(root, documents))
    quick = root / 'docs/quick-start.md'
    if quick.is_file():
        text = quick.read_text(encoding='utf-8')
        if len(quick.read_bytes()) > 4096 or len(text.split()) > 350:
            problems.append('quick start exceeds 350 words or 4096 UTF-8 bytes')
    result = {'problems': sorted(set(problems)), 'unit_bytes': sizes, 'stage_load_bytes': loads,
            'entry_bytes': entry_sizes, 'aggregate_entry_bytes': total,
            'duplicate_prose_bytes': sum(len(p.encode('utf-8')) * (n - 1) for p, n in paragraphs.items() if n > 1)}
    if check_generated and policy.get('generated_report'):
        try:
            actual = json.loads((root / policy['generated_report']).read_text(encoding='utf-8'))
            if actual != size_report(result, policy):
                result['problems'].append('generated size/duplication report drifted')
        except (OSError, ValueError):
            result['problems'].append('generated size/duplication report missing or invalid')
    return result


def size_report(result: dict, policy: dict) -> dict:
    return {'schema_version': 1, 'baseline': policy.get('baseline', {}), **{key: value for key, value in result.items() if key != 'problems'}}


def _anchors(text):
    result, counts, fence = set(), Counter(), None
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if match:
            if fence is None:
                fence = match[1]
            elif match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            continue
        if fence:
            continue
        heading = re.match(r'^#{1,6}\s+(.+?)(?:\s+#+)?$', line)
        if heading:
            slug = re.sub(r'[^\w -]', '', heading[1].lower()).replace(' ', '-')
            result.add(slug + ('-' + str(counts[slug]) if counts[slug] else ''))
            counts[slug] += 1
        result.update(re.findall(r'<a\s+(?:id|name)=[\"\']([^\"\']+)', line))
    return result


def _check_links(root, documents):
    problems, anchors = [], {}
    for path in sorted(documents):
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        # Inline Markdown links; source/selector paths are checked separately.
        for match in re.finditer(r'\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+[\"\'][^)]*)?\)', text):
            target = match[1].strip('<>')
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            destination = (path.parent / unquote(url.path)).resolve() if url.path else path.resolve()
            if not destination.exists():
                problems.append(f'{path.relative_to(root)} broken link: {target}')
            elif url.fragment and destination.is_file() and destination.suffix == '.md':
                if destination not in anchors:
                    anchors[destination] = _anchors(destination.read_text(encoding='utf-8'))
                if unquote(url.fragment) not in anchors[destination]:
                    problems.append(f'{path.relative_to(root)} broken link anchor: {target}')
    return problems
