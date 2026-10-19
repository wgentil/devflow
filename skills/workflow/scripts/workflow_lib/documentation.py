"""Canonical documentation routing, deterministic generation and byte checks."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re

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
    return {'problems': sorted(set(problems)), 'unit_bytes': sizes, 'stage_load_bytes': loads,
            'entry_bytes': entry_sizes, 'aggregate_entry_bytes': total,
            'duplicate_prose_bytes': sum(len(p.encode('utf-8')) * (n - 1) for p, n in paragraphs.items() if n > 1)}
