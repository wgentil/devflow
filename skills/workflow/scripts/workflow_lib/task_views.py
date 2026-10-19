"""Complete task context, composed only after live input and ownership checks."""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .briefs import _size_and_estimate
from .context_artifacts import resolve_cached_units, store_context_artifact
from .document_units import canonical, digest, document_path, select_document_units
from .documentation import load_documentation_policy
from .specs import content_hash, render_spec, validate_spec
from .store import WorkflowError, read_state

PACKAGE_ROOT = Path(__file__).resolve().parents[4]


def governing_selections(receipt: dict, repositories: dict) -> tuple[dict, dict]:
    """Reconstruct only applicable rule selectors from a freshly checked receipt."""
    files = receipt.get('files', {})
    manifests, raw = [], {}
    try:
        for file in files.values():
            text = base64.b64decode(file['content_base64'], validate=True).decode('utf-8')
            raw[(file['repo_id'], file['path'])] = text
            if file['path'] in {'docs/devflow-context.json', 'docs/devflow-org.json'}:
                manifests.append((file['repo_id'], json.loads(text), file['path'].endswith('context.json')))
        candidates = {}
        for repo_id, manifest, local in sorted(manifests, key=lambda m: m[2]):
            for document in manifest['documents']:
                for rid in document['rule_ids']:
                    candidates[rid] = (repo_id, document)
        selections, sources = {}, {}
        for rid in receipt.get('applicable_rule_ids', []):
            repo_id, document = candidates[rid]
            path = document['path']
            text = raw[(repo_id, path)]
            sid = f'governing:{repo_id}:{path}'
            sources[sid] = {'root': repositories[repo_id]['location'], 'path': path,
                            'git_head': next(f.get('git_head') for f in files.values() if f['repo_id'] == repo_id and f['path'] == path)}
            selector = {'kind': 'whole'}
            if Path(path).suffix.lower() == '.md':
                # Receipt rule extraction uses exactly these level-two stable-ID headings.
                heading = re.search(r'^## (' + re.escape(rid) + r': .+)$', text, re.M)
                if not heading:
                    raise ValueError('missing governing heading')
                from .document_units import markdown_section
                # Include ancestor headings when present; use the same fence-aware parser.
                ancestors = []
                for line in text[:heading.start()].splitlines():
                    if re.match(r'^# [^#]', line):
                        ancestors = [line[2:].strip()]
                selector = {'kind': 'markdown', 'heading': ancestors + [heading[1]]}
                markdown_section(text, selector['heading'])
            selections[rid] = {'source_id': sid, 'selector': selector,
                               'category': document['category'], 'sealed': rid in document.get('sealed_rule_ids', [])}
        # Register all approved machine-readable files for safe relative reference closure.
        for file in files.values():
            if Path(file['path']).suffix.lower() == '.json' and file['path'] not in {'docs/devflow-context.json', 'docs/devflow-org.json'}:
                sid = f"governing:{file['repo_id']}:{file['path']}"
                sources.setdefault(sid, {'root': repositories[file['repo_id']]['location'], 'path': file['path'], 'git_head': file.get('git_head')})
        from .governing_docs import canonical_document_bytes
        for sid, source in sources.items():
            expected = raw[(next(f['repo_id'] for f in files.values()
                                  if sid == f"governing:{f['repo_id']}:{f['path']}"), source['path'])].encode('utf-8')
            current = document_path(source).read_bytes()
            if canonical_document_bytes(current, baseline=expected) != expected:
                raise WorkflowError('CONTEXT_SOURCE_CHANGED', 'governing source changed after live preflight')
            source['content_hash'] = hashlib.sha256(current).hexdigest()
        return selections, sources
    except (KeyError, TypeError, ValueError, UnicodeError, OSError) as exc:
        raise WorkflowError('CONTEXT_GOVERNING_INCOMPLETE', 'applicable governing receipt cannot be projected completely') from exc


def build_task_view(run: dict, envelope: dict, selection: dict, sources: dict, policy: dict, *,
                    root: Path | None, max_bytes: int = 20000, representation: str = 'markdown',
                    output_mode: str = 'full') -> dict:
    if type(max_bytes) is not int or max_bytes <= 0 or representation not in {'markdown', 'json'} or output_mode not in {'full', 'refs'}:
        raise WorkflowError('CONTEXT_OPTIONS_INVALID', 'positive byte budget and supported representation/output mode required')
    spec = selection.get('spec')
    if not isinstance(spec, dict):
        raise WorkflowError('CONTEXT_SPEC_MISSING', 'current validated specification is required')
    validate_spec(spec)
    items = {item['id']: item for item in run.get('plan', {}).get('work_items', [])}
    selected_ids = selection.get('item_ids', [])
    if any(i not in items for i in selected_ids):
        raise WorkflowError('CONTEXT_TASK_MISSING', 'selected task is absent from the plan')
    required_requirements = sorted({rid for i in selected_ids for rid in items[i].get('requirement_ids', [])})
    if not selected_ids:
        required_requirements = sorted(r['id'] for r in spec['requirements'])
    requirement_map = {r['id']: r for r in spec['requirements']}
    if set(required_requirements) - requirement_map.keys():
        raise WorkflowError('CONTEXT_REQUIREMENT_MISSING', 'task references missing specification requirements')
    subset = {**spec, 'requirements': [requirement_map[rid] for rid in required_requirements]}
    spec_content = render_spec(subset) if representation == 'markdown' else canonical(subset).decode('utf-8')
    spec_unit = {'id': 'specification', 'source_id': 'specification', 'content': spec_content,
                 'content_hash': hashlib.sha256(spec_content.encode('utf-8')).hexdigest(),
                 'source_hash': content_hash(spec), 'reasons': ['task-requirements'], 'requirement_ids': required_requirements}
    governing = selection.get('governing', {})
    documents = selection.get('documents', [])
    mandatory = [dict(document) for document in documents if document.get('required', True)]
    mandatory.extend({'source_id': rule['source_id'], 'selector': rule.get('selector'), 'reason': 'governing:' + rid}
                     for rid, rule in sorted(governing.items()))
    optional = [document for document in documents if not document.get('required', True)]

    def resolve(selections):
        request = {'sources': sources, 'selections': selections, 'policy': policy}
        if root is not None:
            return resolve_cached_units(root, request)
        return {**select_document_units(sources, selections, policy), 'cache_outcome': 'disabled', 'source_provenance': {}}

    selected = resolve(mandatory)
    required_document_ids = {d['source_id'] for d in mandatory if not str(d.get('reason', '')).startswith('governing:')}
    required_ids = sorted(set(required_requirements) | set(governing) | required_document_ids)
    task = {'schema_version': 1, 'representation': representation, 'required_ids': required_ids,
            'units': [spec_unit, *selected['units']], 'dependencies': selected['dependencies'],
            'source_hashes': {'specification': content_hash(spec), **selected['source_hashes']},
            'source_provenance': selected['source_provenance'], 'governing': governing,
            'coverage': {'supplied_ids': required_ids, 'missing_ids': [], 'semantic_omissions': 'unknown'},
            'measurement_coverage': 'Emitted context only; hidden host instructions, unrelated reads and history are unknown.',
            'cache_outcome': selected['cache_outcome'], 'retrieval_calls': selected['retrieval_calls']}
    omitted = list(envelope.get('budget', {}).get('optional_omitted', []))
    for document in optional:
        try:
            extra = resolve([document])
            candidate = deepcopy(task)
            present = {u['id'] for u in candidate['units']}
            candidate['units'].extend(u for u in extra['units'] if u['id'] not in present)
            candidate['dependencies'].update(extra['dependencies'])
            candidate['source_hashes'].update(extra['source_hashes'])
            projected = _size_and_estimate({**deepcopy(envelope), 'task_view': candidate}, max_bytes, omitted)
            if projected['budget']['serialized_bytes'] > max_bytes:
                raise WorkflowError('CONTEXT_OPTIONAL_OVERFLOW', 'optional document exceeds load budget')
            task = candidate
        except WorkflowError:
            omitted.append(document['source_id'])
    refs = store_context_artifact(root, task, {'builder': 1, 'policy': digest(policy), 'run_id': run['id'],
        'stage': selection.get('stage'), 'items': sorted(selected_ids)}) if root is not None else {}
    task.update(refs)
    if output_mode == 'refs':
        if root is None:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'reference output needs a selected control root')
        task = {key: task[key] for key in ('schema_version', 'artifact_id', 'artifact_ref', 'required_ids', 'coverage', 'representation')}
        task['inspection'] = 'context-artifact inspect --root CONTROL --id ' + refs['artifact_id']
    result = _size_and_estimate({**deepcopy(envelope), 'task_view': task}, max_bytes, omitted)
    if result['budget']['serialized_bytes'] > max_bytes:
        raise WorkflowError('CONTEXT_BUDGET_EXCEEDED', 'mandatory task context exceeds max_bytes', {
            'required_bytes': result['budget']['serialized_bytes'], 'max_bytes': max_bytes,
            'artifact_refs': refs or {sid: source['path'] for sid, source in sources.items()},
            'action': 'Rescope the task or explicitly increase the context byte budget; do not truncate required facts.'})
    return result


def prepare_task_view(root: Path, run: dict, envelope: dict, item_ids: list[str], *, stage: str = 'implementation',
                      max_bytes: int = 20000, representation: str = 'markdown', output_mode: str = 'full') -> dict:
    """Live entry point shared by run and host reads; caches never bypass preflight."""
    from .repo_input_gate import require_current_inputs
    state = read_state(root)
    require_current_inputs(root, state, 'context-preparation', run['id'])
    data = read_state(root)['data']
    spec = data['spec']
    if run.get('plan', {}).get('spec_hash') != content_hash(spec):
        raise WorkflowError('PLAN_STALE', 'task context requires the currently approved plan specification')
    policy = load_documentation_policy(PACKAGE_ROOT)
    stage = {'build': 'implementation', 'verification': 'implementation', 'branch-review': 'review'}.get(stage, stage)
    if stage not in policy['stage_reads']:
        raise WorkflowError('CONTEXT_STAGE_UNAVAILABLE', 'stage has no declared documentation read route')
    governing, sources = governing_selections(data.get('governing_input_receipt', {}), data.get('repositories', {}))
    sources.update({sid: {'root': str(PACKAGE_ROOT), 'path': source['path']} for sid, source in policy['sources'].items()})
    selection = {'spec': spec, 'item_ids': item_ids, 'stage': stage, 'governing': governing,
                 'documents': [{'source_id': sid} for sid in policy['stage_reads'][stage]]}
    view = build_task_view(run, envelope, selection, sources, policy, root=root, max_bytes=max_bytes,
                           representation=representation, output_mode=output_mode)
    if data.get('spec_pair'):
        from .repo_specs import assert_repo_spec_approval
        pair = data['spec_pair']
        assert_repo_spec_approval(Path(data['repositories'][pair['repo_id']]['location']), pair)
    return view
