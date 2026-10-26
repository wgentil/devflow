"""Pure reducer fixtures. Frozen streams were captured from owned temporary roots
in the existing journal/host/review tests; their paths are inert synthetic inputs.
No fixture contains a real project control root or requires those paths to exist.
"""


def basic_event_streams():
    yield [{'id': 'note', 'kind': 'note', 'payload': {'unknown': {'bytes': 'é東京'}}},
           {'id': 'replace', 'kind': 'another-extension', 'payload': {'unknown': None}}]
    yield [{'id': 'register', 'kind': 'domain.host.init', 'payload': {'request': {
               'repo_id': 'app', 'location': '/owned/application'}}}]
    yield [{'id': 'run', 'kind': 'run.started', 'payload': {'run': {
               'id': 'run', 'status': 'active', 'items': {}, 'active_attempt': None}}},
           {'id': 'discard', 'kind': 'run.discarded', 'payload': {
               'run_id': 'run', 'reason': 'explicit discard', 'actor_id': 'human'}}]

    yield [{'id':'cache-seed','kind':'fixture','payload':{'context_projections':{'old':{'value':'retained'}}}},
           {'id':'cache-delta','kind':'context.resolution.recorded','payload':{'resolved_context':{},
            'resolved_context_source_hash':'source','context_projections_delta':{'new':{'value':'added'}}}}]
    seed = {'id': 'r', 'status': 'active', 'active_attempt': {'token': 't'},
            'verification_proofs': {'p': {'kind': 'iac-plan', 'token': 't', 'repo_id': 'app'}},
            'unresolved_findings': [{'id': 'park'}, {'id': 'resolve'}, {'id': 'waive'}],
            'reviews': {'branch': [{'verdict': 'request-changes'}]}}
    details = [
        ('authorization.recorded', {'run_id': 'r', 'authorization': {
            'id': 'a', 'attempt_id': 't', 'plan_proof_id': 'p', 'repo_id': 'app'}}),
        ('finding.parked', {'run_id': 'r', 'finding_id': 'park', 'ruling': {
            'actor_id': 'owner', 'why': 'later', 'cost_if_wrong': 'rework'}}),
        ('finding.resolved', {'run_id': 'r', 'finding_id': 'resolve', 'resolution': {
            'actor_id': 'owner', 'why': 'fixed', 'evidence_refs': ['proof']}}),
        ('finding.waived', {'run_id': 'r', 'finding_id': 'waive', 'authorization': {
            'approved': True, 'run_id': 'r', 'finding_id': 'waive', 'scope': 'explicit'}}),
        ('review.adjudicated', {'run_id': 'r', 'adjudication': {
            'id': 'd', 'role': 'branch', 'decision': 'return', 'actor_id': 'owner',
            'rationale': 'correct issue', 'cost_if_wrong': 'rework'}}),
        ('test.change.proposed', {'run_id': 'r', 'proposal': {'id': 'change', 'run_id': 'r', 'proposal_hash': 'h'}}),
        ('test.change.approved', {'run_id': 'r', 'proposal_id': 'change', 'approval': {'actor_id': 'owner', 'proposal_hash': 'h'}}),
    ]
    yield [{'id': 'seed', 'kind': 'run.started', 'payload': {'run': seed}}] + [
        {'id': f'manual-{i}', 'kind': kind, 'payload': payload} for i, (kind, payload) in enumerate(details)]


def captured_event_streams():
    import gzip
    import json
    from pathlib import Path
    return json.loads(gzip.decompress((Path(__file__).parent /
        'fixtures/control-storage-events.json.gz').read_bytes()))


def supplemental_domain_streams():
    from copy import deepcopy
    from workflow_lib import store
    def pair(kind, data, request):
        return [{'id': 'seed', 'kind': 'fixture', 'payload': data},
                {'id': 'event', 'kind': kind, 'payload': {'request': request}}]
    yield pair('domain.improve.trace-enable', {'runs': {'r': {'id': 'r'}}},
               {'run_id': 'r', 'actor_id': 'owner'})
    yield pair('domain.stats.legacy-import', {}, {'record': {
        'legacy': True, 'source_hash': 'h', 'source_run_id': 'old'}})
    yield pair('domain.outbox.uncertain', {'outbox': {'o': {
        'status': 'dispatching', 'dispatch_token': 't'}}}, {'id': 'o', 'token': 't'})
    yield pair('domain.migrate.delivered', {'migration': {
        'increments': {'increments': [{'id': 'one', 'depends_on': [], 'criteria': []}]},
        'parity': [{'increment_id': 'one', 'verified': []}]}, 'runs': {'r': {
        'id': 'r', 'status': 'delivered', 'migration_increment_id': 'one',
        'delivery': {'manifest_hash': 'h'}}}}, {'run_id': 'r', 'increment_id': 'one'})
    package = {'role': 'pr', 'pr_id': 'pr', 'head_sha': 'head'}
    run = {'id': 'r', 'pending_pr': {'pr_id': 'pr', 'head_sha': 'head'},
           'review_packages': {'pkg': package}, 'reviews': {'pr': [{
           'review_id': 'review', 'package_hash': 'pkg', 'verdict': 'human-decision-required',
           'actor_id': 'reviewer', 'findings': [{'id': 'f', 'owner': 'owner',
           'options': [{'choice': 'reject', 'effect': 'reject'}]}]}]}}
    from workflow_lib.pr_reviews import record_pr_human_decision
    decision = record_pr_human_decision(run, 'pkg', 'owner', 'f', 'reject', 'explicit choice')
    yield pair('domain.pr.human-decision', {'runs': {'r': run}}, {'run_id': 'r', 'decision': decision})
    found = set()
    for events in captured_event_streams():
        state = store._empty()
        for event in events:
            kind = event['kind']
            if kind == 'domain.host.attach' and 'legacy' not in found:
                data = deepcopy(state['data'])
                request = deepcopy(event['payload']['request'])
                data['host_bindings'] = {}
                data['runs'][request['run_id']].pop('host_owner_release', None)
                request['adopt_legacy'] = True
                yield pair('domain.host.legacy-adopt', data, request)
                found.add('legacy')
            store._apply_event(state, event)
            if kind == 'domain.host.model-receipt' and 'interrupt' not in found:
                data = deepcopy(state['data'])
                request = event['payload']['request']
                yield pair('domain.host.model-interrupt', data, {
                    'binding_id': request['binding_id'], 'revision': request['revision'],
                    'invocation': {'invocation_id': request['receipt']['invocation_id']},
                    'error_kind': 'network', 'retry_count': 0})
                found.add('interrupt')


def registered_domain_kinds():
    import ast
    from pathlib import Path
    base = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/workflow_lib'
    kinds = set()
    for filename, prefix in [('journal_domains.py', ''), ('hosts.py', 'domain.host.')]:
        for node in ast.walk(ast.parse((base / filename).read_text(encoding='utf-8'))):
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == 'kind':
                for comparator in node.comparators:
                    kinds.update(prefix + value.value for value in ast.walk(comparator)
                                 if isinstance(value, ast.Constant) and isinstance(value.value, str))
    return kinds


def registered_core_kinds():
    import ast
    from pathlib import Path
    source=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/workflow_lib/store.py'
    tree=ast.parse(source.read_text(encoding='utf-8'))
    function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_apply_event')
    kinds=set()
    for node in ast.walk(function):
        if isinstance(node,ast.Compare) and isinstance(node.left,ast.Name) and node.left.id=='kind':
            for comparator in node.comparators:
                kinds.update(value.value for value in ast.walk(comparator)
                    if isinstance(value,ast.Constant) and isinstance(value.value,str))
    return kinds
