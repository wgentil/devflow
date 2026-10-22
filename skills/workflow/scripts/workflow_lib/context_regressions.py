"""Offline context fixtures sharing the production selectors, views and recovery."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time

from .context_checkpoints import project_checkpoint, apply_context_delta
from .context_metrics import measure_context_view
from .document_units import canonical
from .native_runtime import invocation_context
from .task_views import build_task_view
from .store import WorkflowError


def evaluate_context_regression(observed: dict, policy: dict) -> list[str]:
    problems = []
    for key, limit in policy['budgets'].items():
        if type(observed.get(key)) is not int or observed[key] > limit:
            problems.append(key + ': budget exceeded or measurement unavailable')
    for key in ('dependency_complete', 'reconstruction_matches', 'warm_hit', 'dependency_change_rebuilt', 'compaction_full', 'handoff_full'):
        if observed.get(key) is not True:
            problems.append(key + ': required behavior missing')
    for key in ('missing_ids', 'missing_facts'):
        if observed.get(key) != []:
            problems.append(key + ': required facts missing')
    if observed.get('delta_bytes', 0) >= observed.get('full_bytes', 0):
        problems.append('delta must be strictly smaller than the equivalent full view')
    if observed.get('full_bytes', 0) >= observed.get('baseline_full_fact_bytes', 0):
        problems.append('full view must reduce the explicitly equivalent full-fact fixture baseline')
    return problems


def check_context_regressions(fixture_root: Path) -> dict:
    start = time.monotonic()
    fixture_root = Path(fixture_root).resolve()
    policy = json.loads((fixture_root / 'policy.json').read_text(encoding='utf-8'))
    if policy.get('schema_version') != 1:
        raise WorkflowError('CONTEXT_FIXTURE_INVALID', 'unsupported fixture policy')
    spec = {'mode': 'new', 'requirements': [{'id': 'R1', 'title': 'Unicode request', 'text': 'Accept Unicode input for user.',
        'acceptance_criteria': ['A user name satisfies the selected schema'], 'provenance': {'kind': 'authored'}}]}
    run = {'id': 'fixture', 'plan': {'work_items': [{'id': 'W1', 'requirement_ids': ['R1']}]}}
    envelope = {'run_id': 'fixture', 'stage': 'implementation', 'blockers': ['full configured checks remain required']}
    scope = {'consumer_id': 'fixture-consumer', 'run_id': 'fixture', 'binding_id': 'binding', 'session_id': 'session',
             'revision': 1, 'stage': 'implementation', 'role': 'implementer', 'task_ids': ['W1']}
    selection = {'spec': spec, 'item_ids': ['W1'], 'stage': 'implementation',
        'governing': {'G1': {'source_id': 'rules', 'selector': {'kind': 'markdown', 'heading': ['Fixture rules', 'G1: Required constraints']}}},
        'documents': [{'source_id': 'guide'}, {'source_id': 'contract', 'selector': {'kind': 'json-pointer', 'pointer': '/request'}}]}
    with tempfile.TemporaryDirectory(prefix='devflow-context-regression-') as directory:
        root = Path(directory)
        repo, control = root / 'repo', root / 'control'
        repo.mkdir()
        paths = {'guide': 'guide.md', 'rules': 'rules.md', 'contract': 'contract.json', 'schema': 'schema.json'}
        for path in paths.values():
            source = fixture_root / path
            if source.is_symlink() or not source.resolve().is_relative_to(fixture_root):
                raise WorkflowError('CONTEXT_FIXTURE_INVALID', 'fixture source must remain within fixture root')
            (repo / path).write_bytes(source.read_bytes())
        sources = {sid: {'root': str(repo), 'path': path} for sid, path in paths.items()}
        build = lambda: build_task_view(run, envelope, selection, sources, {}, root=control, max_bytes=15000)
        cold = build()
        warm = build()
        # Unrelated repository change must leave reusable required content warm.
        (repo / 'unrelated.txt').write_text('unrelated', encoding='utf-8')
        unrelated = build()
        base = project_checkpoint(control, warm, scope)
        unchanged = project_checkpoint(control, unrelated, scope, since=base['checkpoint']['id'])
        reconstructed = apply_context_delta(base, unchanged)
        (repo / 'schema.json').write_text('{"User":{"type":"string","minLength":2}}', encoding='utf-8')
        changed = build()
        current = project_checkpoint(control, changed, scope, since=base['checkpoint']['id'])
        changed_rebuilt = apply_context_delta(base, current)
        compaction = project_checkpoint(control, changed, scope, since=base['checkpoint']['id'], recovery_reason='compaction')
        handoff = project_checkpoint(control, changed, {**scope, 'revision': 2, 'session_id': 'destination'}, since=base['checkpoint']['id'])
        units = cold['task_view']['units']
        text = '\n'.join(unit['content'] for unit in units)
        unit_ids = {u['id'] for u in units}
        sources_seen = {u['source_id'] for u in units}
        edges = cold['task_view']['dependencies']
        baseline = deepcopy(cold)
        for unit in baseline['task_view']['units']:
            if unit['source_id'] in paths:
                unit['content'] = (repo / paths[unit['source_id']]).read_text(encoding='utf-8')
        baseline['specification_json'] = spec
        native = invocation_context({'host': 'codex', 'actor_id': 'fixture'}, 'implementation', cold, 'Implement fixture', 20000)
        metric = measure_context_view(cold, operation_id='fixture', operation='offline')
        hashes = [unit['content_hash'] for unit in metric['units']]
        observed = {'full_bytes': len(canonical(cold)), 'delta_bytes': len(canonical(unchanged)),
            'baseline_full_fact_bytes': len(canonical(baseline)) * 2,
            'cold_retrieval_calls': cold['task_view']['retrieval_calls'], 'warm_retrieval_calls': warm['task_view']['retrieval_calls'],
            'duplicate_content_bytes': sum(u['bytes'] for i, u in enumerate(metric['units']) if hashes.index(u['content_hash']) < i),
            'native_context_copies': (native['configuration_text'] + native['prompt']).count('Keep every applicable constraint'),
            'missing_ids': sorted(set(policy['required_ids']) - set(cold['task_view']['required_ids'])),
            'missing_facts': [fact for fact in policy['required_facts'] if fact not in text],
            'dependency_complete': set(policy['required_source_ids']).issubset(sources_seen) and all(set(deps).issubset(unit_ids) for deps in edges.values()),
            'reconstruction_matches': reconstructed['task_view'] == unrelated['task_view'] and changed_rebuilt['task_view'] == changed['task_view'],
            'warm_hit': warm['task_view']['cache_outcome'] == 'hit' and unrelated['task_view']['cache_outcome'] == 'hit',
            'dependency_change_rebuilt': changed['task_view']['cache_outcome'] == 'miss' and changed['task_view']['source_hashes']['schema'] != cold['task_view']['source_hashes']['schema'],
            'compaction_full': compaction['context_mode'] == 'full', 'handoff_full': handoff['context_mode'] == 'full',
            'latency_ms': round((time.monotonic() - start) * 1000, 3)}
    problems = evaluate_context_regression(observed, policy)
    return {'passed': not problems, 'problems': problems, 'observed': observed, 'policy': policy,
        'baseline_scope': 'Equivalent full-fact fixture with whole sources, JSON+Markdown spec and duplicate native context; not old incomplete helper output.',
        'measurement_limits': 'Offline bytes and selector/cache reads only; latency is informational, tokens/cost/semantic omissions remain unknown.'}
