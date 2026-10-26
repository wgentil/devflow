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
from .store import WorkflowError

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
                selector = {'kind': 'governing-rule', 'rule_id': rid}
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


def _spec_content(subset,representation):
    if representation=='json':
        content=canonical(subset).decode('utf-8')
        requirements=canonical(subset['requirements']).decode('utf-8')
        return content,len(canonical(requirements))-2
    content=render_spec(subset)
    extras={k:v for k,v in subset.items() if k not in {'mode','title','requirements','diagrams'}}
    requirement_extras={r['id']:{k:v for k,v in r.items() if k not in {'id','title','text','acceptance_criteria','provenance'}} for r in subset['requirements']}
    requirement_extras={k:v for k,v in requirement_extras.items() if v}
    if requirement_extras:extras['requirement_metadata']=requirement_extras
    if extras:content+='\n## Shared specification facts\n\n```json\n'+canonical(extras).decode('utf-8')+'\n```\n'
    prefix=render_spec({'mode':subset['mode'],'requirements':[]})
    requirement_bytes=sum(len(canonical(render_spec({'mode':subset['mode'],'requirements':[r]})[len(prefix):]))-2 for r in subset['requirements'])
    return content,requirement_bytes


def context_component_bytes(envelope:dict,task:dict,*,optional_slices=())->dict:
    """Partition actual wire bytes; punctuation and binding metadata remain explicit."""
    total=len(canonical({**envelope,'task_view':task}))
    parts={k:0 for k in ('requirements','shared_spec','governing','stage_documents','control_envelope','artifact_references','optional','serialization_overhead')}
    governed={v['source_id'] for v in task.get('governing',{}).values()}
    for unit in task.get('units',[]):
        size=len(canonical(unit))
        if unit.get('source_id')=='specification':
            requirements=unit.get('requirement_content_bytes',0)
            parts['requirements']+=requirements;parts['shared_spec']+=size-requirements
        elif unit.get('required') is False:parts['optional']+=size
        elif unit.get('source_id') in governed:parts['governing']+=size
        else:parts['stage_documents']+=size
    parts['control_envelope']=sum(len(canonical({k:v}))-2 for k,v in envelope.items() if k!='budget')
    context=envelope.get('context',{})
    optional_bytes=sum(len(canonical({key:context.get(field,{})[key]}))-2
        for key in set(optional_slices) for field in ('values','provenance') if key in context.get(field,{}))
    parts['optional']+=optional_bytes;parts['control_envelope']-=optional_bytes
    parts['artifact_references']=sum(len(canonical({k:task[k]}))-2 for k in ('artifact_id','artifact_ref','content_bytes','inspection') if k in task)
    parts['serialization_overhead']=total-sum(parts.values())
    parts['serialized_bytes']=total
    return parts


def _measure_view(envelope,task,max_bytes,omitted,*,optional_slices=()):
    value=_size_and_estimate({**deepcopy(envelope),'task_view':deepcopy(task)},max_bytes,omitted)
    for _ in range(20):
        parts=context_component_bytes({k:v for k,v in value.items() if k!='task_view'},value['task_view'],optional_slices=optional_slices)
        value['budget']['component_bytes']=parts
        size=len(canonical(value));value['budget'].update(serialized_bytes=size,estimated_tokens=(size+3)//4)
        if (parts==context_component_bytes({k:v for k,v in value.items() if k!='task_view'},value['task_view'],optional_slices=optional_slices)
                and size==len(canonical(value))):return value
    raise WorkflowError('CONTEXT_ACCOUNTING_INVALID','Context byte accounting did not converge.')


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
    spec_content,requirement_bytes = _spec_content(subset,representation)
    spec_unit = {'id': 'specification', 'source_id': 'specification', 'content': spec_content,
                 'required':True,'requirement_content_bytes':requirement_bytes,
                 'content_hash': hashlib.sha256(spec_content.encode('utf-8')).hexdigest(),
                 'source_hash': selection.get('spec_hash',content_hash(spec)), 'reasons': ['task-requirements'], 'requirement_ids': required_requirements}
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
    if root is not None:
        from .context_artifacts import invalidate_context_artifacts
        invalidate_context_artifacts(root, selected['source_hashes'], digest(policy))
    required_document_ids = {d['source_id'] for d in mandatory if not str(d.get('reason', '')).startswith('governing:')}
    required_ids = sorted(set(required_requirements) | set(governing) | required_document_ids)
    task = {'schema_version': 1, 'representation': representation, 'required_ids': required_ids,
            'units': [spec_unit, *[{**u,'required':True} for u in selected['units']]], 'dependencies': selected['dependencies'],
            'source_hashes': {'specification': selection.get('spec_hash',content_hash(spec)), **selected['source_hashes']},
            'source_provenance': selected['source_provenance'], 'governing': governing,
            'coverage': {'supplied_ids': required_ids, 'missing_ids': [], 'semantic_omissions': 'unknown'},
            'measurement_coverage': 'Emitted context only; hidden host instructions, unrelated reads and history are unknown.',
            'cache_outcome': selected['cache_outcome'], 'retrieval_calls': selected['retrieval_calls']}
    envelope=deepcopy(envelope)
    optional_slices=selection.get('optional_slices',[])
    omitted = list(envelope.get('budget', {}).get('optional_omitted', []))
    def preview_task(candidate):
        preview=deepcopy(candidate)
        if root is not None:
            preview.update(artifact_id='0'*64,artifact_ref=str(Path(root).resolve()/'context-artifacts'/('0'*64+'.json')),content_bytes=len(canonical(candidate)))
            if output_mode=='refs':
                preview={key:preview[key] for key in ('schema_version','artifact_id','artifact_ref','required_ids','coverage','representation')}
                preview['inspection']='context-artifact inspect --root CONTROL --id '+'0'*64
        return preview
    # Envelope slices must fit alongside mandatory units, not just by themselves.
    for key in optional_slices:
        projected=_measure_view(envelope,preview_task(task),max_bytes,omitted,optional_slices=optional_slices)
        if projected['budget']['serialized_bytes']<=max_bytes:break
        context=envelope.get('context',{})
        if key in context.get('values',{}):
            context['values'].pop(key);context.get('provenance',{}).pop(key,None)
            if key not in omitted:omitted.append(key)
    for document in optional:
        try:
            extra = resolve([document])
            candidate = deepcopy(task)
            present = {u['id'] for u in candidate['units']}
            candidate['units'].extend({**u,'required':False} for u in extra['units'] if u['id'] not in present)
            candidate['dependencies'].update(extra['dependencies'])
            candidate['source_hashes'].update(extra['source_hashes'])
            projected = _measure_view(envelope,preview_task(candidate),max_bytes,omitted,optional_slices=optional_slices)
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
    result = _measure_view(envelope,task,max_bytes,omitted,optional_slices=optional_slices)
    if result['budget']['serialized_bytes'] > max_bytes:
        raise WorkflowError('CONTEXT_BUDGET_EXCEEDED', 'mandatory task context exceeds max_bytes', {
            'required_bytes': result['budget']['serialized_bytes'], 'max_bytes': max_bytes,
            'phase':'composition','component_bytes':result['budget']['component_bytes'],
            'artifact_refs': refs or {sid: source['path'] for sid, source in sources.items()},
            'action': 'Rescope the task or explicitly increase the context byte budget; do not truncate required facts.'})
    return result


def prepare_task_view(root: Path, run: dict, envelope: dict, item_ids: list[str], *, stage: str = 'implementation',
                      max_bytes: int = 20000, representation: str = 'markdown', output_mode: str = 'full', state: dict | None = None) -> dict:
    """Safe direct entry; authoritative preflight remains outside composition."""
    from .context_preparation import prepare_context,compose_prepared,assert_preparation_current,finish_prepared
    prepared=prepare_context(root,run,envelope,item_ids,stage=stage,state=state,max_bytes=max_bytes,representation=representation,output_mode=output_mode)
    result=compose_prepared(prepared.payload)
    assert_preparation_current(root,prepared,prepared._state)
    return finish_prepared(prepared,result)
