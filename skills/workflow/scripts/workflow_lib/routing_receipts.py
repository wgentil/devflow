"""Content-bound routing metadata and scoped worker reports, never proof."""
from copy import deepcopy
import re
from .document_units import digest
from .store import WorkflowError
from .task_routing import normalize_task_facts


def routing_lineage_id(task: dict) -> str:
    return digest([task['run_id'], task['task_id'], task['stage']])


def validate_routing_evidence(routing: dict, scope: dict) -> dict:
    def fail():
        raise WorkflowError('ROUTING_EVIDENCE_INVALID', 'Routing evidence must match immutable task and invocation scope.')
    if not isinstance(routing, dict) or type(routing.get('routing_schema_version')) is not int or routing['routing_schema_version'] != 1:
        fail()
    facts = normalize_task_facts(routing.get('task_facts'), scope)
    if (routing.get('task_hash') != digest(facts) or routing.get('scope_hash') != digest(scope)
            or routing.get('lineage_id') != routing_lineage_id(facts)
            or routing.get('classification_origin') != facts['origin']):
        fail()
    if (not isinstance(routing.get('policy_hash'), str) or not re.fullmatch(r'[0-9a-f]{64}', routing['policy_hash'])
            or routing.get('execution_path') not in {'isolated-native', 'interactive-nonfork', 'interactive-fork'}
            or not isinstance(routing.get('controls'), dict)
            or not isinstance(routing.get('reasons'), list)
            or any(not isinstance(reason, str) for reason in routing['reasons'])):
        fail()
    return deepcopy(routing)


def normalize_worker_outcome(result: dict, expected_scope: dict) -> dict:
    unknowns = []
    if not isinstance(result, dict): result = {}
    valid_scope = result.get('scope') == expected_scope
    if not valid_scope: unknowns.append('WORKER_SCOPE_MISMATCH')
    def strings(key):
        values = result.get(key)
        if (not isinstance(values, list) or len(values) > 64
                or any(not isinstance(v, str) or not v.strip() or len(v.encode()) > 4096 for v in values)):
            unknowns.append(key.upper() + '_UNAVAILABLE')
            return []
        return deepcopy(values)
    completed, refs, unresolved = strings('completed_scope'), strings('evidence_refs'), strings('unresolved_facts')
    required = expected_scope.get('item_id') or expected_scope.get('package_hash') or expected_scope.get('stage')
    status = result.get('status')
    if (status == 'completed' and (unknowns or not completed or not refs or unresolved or required not in completed)):
        status = 'partial'
    if status not in {'completed', 'partial', 'blocked'}: status = 'partial'
    return {'status': status, 'scope': deepcopy(expected_scope), 'completed_scope': completed,
            'evidence_refs': refs, 'unresolved_facts': unresolved, 'unknowns': unknowns,
            'purpose': 'Worker report only; existing verification and review determine proof.'}
