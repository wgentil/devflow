"""Explicit entity read/write scopes for operational and reducer views."""
from dataclasses import dataclass

GLOBAL_KEYS = ('resolved_context', 'resolved_context_source_hash', 'artifacts', 'authorization_scope', 'unresolved_findings', 'spec', 'spec_pair', 'approval', 'spec_approval_invalidated', 'plan', 'plan_validation',
    'repositories', 'context', 'context_hash', 'governing_input_receipt', 'governing_reassessment_required',
    'current_source_indexes', 'snapshot_hash', 'snapshot_valid', 'migration',
    'model_policy', 'routing_policy', 'maintenance_policy')


@dataclass(frozen=True)
class EntityQuery:
    namespace: str
    filters: tuple = ()


@dataclass(frozen=True)
class ReadScope:
    run_ids: tuple = ()
    global_keys: tuple = GLOBAL_KEYS
    namespaces: tuple = ()
    entity_keys: tuple = ()
    queries: tuple = ()
    operation_ids: tuple = ()
    active_runs: bool = False
    full: bool = False
    full_packages: bool = False
    run_view: str | None = None
    history_all: bool = False
    usage_run_ids: tuple = ()


CORE_KINDS = frozenset(('context.resolution.recorded', 'acceptance.recorded', 'authorization.recorded', 'delivery.recorded',
    'document.approved', 'document.proposed', 'finding.parked', 'finding.resolved', 'finding.waived',
    'governing.inputs.recorded', 'governing.reassessment.required', 'plan.validated',
    'review.adjudicated', 'review.package.prepared', 'review.recorded', 'run.attempt.abandoned',
    'run.attempt.issued', 'run.discarded', 'run.item.amended', 'run.result.recorded',
    'run.reverification.started', 'run.started', 'test.change.applied', 'test.change.applying',
    'test.change.approved', 'test.change.proposed', 'verification.recorded', 'verification.typed.recorded'))
# Complete current-business namespaces are explicit; none implicitly loads all runs/operations.
DOMAIN_NAMESPACES = {
    'issues': ('issues', 'snapshots', 'groups', 'group_revisions', 'issue_runs', 'classifications', 'write_authorizations'),
    'outbox': ('outbox', 'write_authorizations', 'issues', 'snapshots', 'groups'),
    'migrate': ('migration',), 'ingest': (),
    'stats': ('usage', 'usage_expectations', 'prices', 'reports', 'legacy_imports'),
    'harden': (), 'repair': (), 'pr': ('pr_setup',),
    'improve': (), 'host': (),
}


def scope_for_event(event, operation_id, *, binding_id=None):
    kind, payload = event['kind'], event['payload']
    request = payload.get('request', payload)
    if not isinstance(request,dict): request = {}
    run_ids = set()
    for value in (request.get('run_id'), payload.get('run_id'), (payload['run'] if isinstance(payload.get('run'),dict) else {}).get('id')):
        if isinstance(value, str): run_ids.add(value)
    entities = [('domain_receipts', operation_id)]
    namespaces = []
    globals_ = list(GLOBAL_KEYS)
    replacements = set()
    queries = []
    run_view = None
    history_all = False
    usage_run_ids = ()
    if binding_id: entities.append(('host_bindings', binding_id))
    if kind.startswith('domain.'):
        family = kind.split('.')[1]
        pending = [request]
        while pending:
            row = pending.pop()
            if isinstance(row, dict):
                if isinstance(row.get('run_id'), str): run_ids.add(row['run_id'])
                pending.extend(row.values())
            elif isinstance(row, list): pending.extend(row)
        if family not in DOMAIN_NAMESPACES:
            from .store import WorkflowError
            raise WorkflowError('INVALID_EVENT', 'unsupported domain event: ' + kind)
        namespaces.extend(DOMAIN_NAMESPACES[family])
        if family == 'improve':
            if kind == 'domain.improve.feedback':
                from .journal_domains import digest
                key = digest({'trace_hash':request.get('trace_hash'),'actor_id':request.get('actor_id'),'feedback':request.get('feedback')})
                entities.append(('improvement_feedback',key))
                run_view = 'trace'; usage_run_ids = tuple(sorted(run_ids))
            elif kind == 'domain.improve.case-approve':
                entities.append(('improvement_feedback',request.get('feedback_id','')))
        if family == 'ingest':
            from .journal_domains import digest
            index = request.get('index')
            if isinstance(index,dict) and 'fingerprint' in index:
                identifier = digest({'repo_id':request.get('repo_id'),'content_fingerprint':index['fingerprint']})
                entities.append(('source_indexes',identifier))
            entities.extend(('ingestion_cache',key) for key in (request.get('cache') if isinstance(request.get('cache'),dict) else {}))
        if family == 'stats':
            for row in request.get('events', []) if isinstance(request.get('events',[]),list) else ():
                if isinstance(row, dict) and isinstance(row.get('run_id'), str): run_ids.add(row['run_id'])
            for binding in (request.get('bindings') if isinstance(request.get('bindings'),dict) else {}).values():
                if isinstance(binding, dict) and isinstance(binding.get('run_id'), str): run_ids.add(binding['run_id'])
            if kind == 'domain.stats.metrics':
                namespaces.append('classifications')
                run_view = 'metrics'; history_all = True
        if family == 'host' and request.get('handoff_id'):
            entities.append(('host_handoffs', request['handoff_id']))
        if family == 'host' and isinstance(request.get('destination'), dict):
            destination = request['destination']
            if destination.get('binding_id'): entities.append(('host_bindings', destination['binding_id']))
            if destination.get('host') and destination.get('session_id'):
                queries.append(EntityQuery('host_bindings', (('host', destination['host']), ('session_id', destination['session_id']), ('status', 'active'))))
        if family == 'host':
            for key, value in request.items():
                if key.endswith('binding_id') and isinstance(value, str):
                    entities.append(('host_bindings', value))
            if request.get('session_id') and request.get('host'):
                queries.append(EntityQuery('host_bindings', (('host', request['host']),
                    ('session_id', request['session_id']), ('status', 'active'))))
            for run_id in run_ids:
                queries.extend((EntityQuery('host_bindings', (('run_id', run_id),)),
                                EntityQuery('host_tasks', (('run_id', run_id),))))
            for key in ('task_id',):
                if isinstance(request.get(key), str): entities.append(('host_tasks', request[key]))
    elif kind not in CORE_KINDS:
        # Generic patches have always replaced each named root value in its entirety.
        replacements.update(payload)
        # Replacement needs only existing SQL keys, never obsolete logical bodies.
        if kind != 'spec.approved': globals_ = [key for key in globals_ if key not in payload]
    if kind == 'plan.validated':
        replacements.update(payload)
        globals_ = [key for key in globals_ if key not in payload or key in
                    {'governing_input_receipt', 'governing_reassessment_required'}]
    if kind == 'context.resolution.recorded':
        entities.extend(('context_projections',key) for key in (payload.get('context_projections_delta') if isinstance(payload.get('context_projections_delta'),dict) else {}))
    if kind == 'document.proposed':
        entities.append(('document_proposals', payload.get('proposal', {}).get('proposal_hash', '')))
    if kind == 'document.approved':
        key = payload.get('approval', {}).get('proposal_hash', '')
        entities.extend((('document_proposals', key), ('document_approvals', key)))
    return ReadScope(run_ids=tuple(sorted(run_ids)), global_keys=tuple(dict.fromkeys(globals_)),
        namespaces=tuple(namespaces), entity_keys=tuple(entities), queries=tuple(queries),
        operation_ids=(operation_id,), run_view=run_view, history_all=history_all, usage_run_ids=usage_run_ids), replacements
