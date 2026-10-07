"""Versioned stage and source-profile catalog validation."""
from __future__ import annotations


def validate_catalog(catalog: dict, profiles: dict) -> dict:
    errors = []
    if not isinstance(catalog, dict) or catalog.get('version') != 1:
        errors.append('catalog version must be 1')
    stages = catalog.get('stages', []) if isinstance(catalog, dict) else []
    if not isinstance(stages, list): stages = []; errors.append('stages must be an array')
    ids = [s.get('id') for s in stages if isinstance(s, dict)]
    if len(ids) != len(stages) or len(set(ids)) != len(ids): errors.append('stage IDs must be unique')
    graph = {s.get('id'): s.get('prerequisites', []) for s in stages if isinstance(s, dict)}
    for key, deps in graph.items():
        if not isinstance(deps, list) or any(dep not in graph for dep in deps): errors.append(f'undefined prerequisite for {key}')
    visiting, done = set(), set()
    def visit(key):
        if key in visiting: errors.append('stage dependency cycle'); return
        if key in done: return
        visiting.add(key)
        for dep in graph.get(key, []):
            if dep in graph: visit(dep)
        visiting.discard(key); done.add(key)
    for key in graph: visit(key)
    registered = profiles.get('profiles', {}) if isinstance(profiles, dict) else {}
    requested = catalog.get('profiles', []) if isinstance(catalog, dict) else []
    if any(value not in registered for value in requested): errors.append('undefined profile identifier')
    return {'valid': not errors, 'errors': errors}
