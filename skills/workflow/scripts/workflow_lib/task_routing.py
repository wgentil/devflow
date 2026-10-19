"""Validated task facts and policy-owned routing intent; no host or journal I/O."""
from copy import deepcopy
from pathlib import PurePosixPath
import re

from .document_units import canonical, digest
from .store import WorkflowError

FIELDS = {'schema_version', 'task_id', 'run_id', 'stage', 'actor_id', 'item_id', 'kind',
          'scope', 'required_output', 'complexity', 'uncertainty', 'consequence', 'evidence_refs', 'origin'}
ENUMS = {'kind': {'discovery', 'extraction', 'implementation', 'requirements', 'architecture',
                 'debugging', 'review', 'security', 'deterministic'},
         'complexity': {'bounded', 'cross-component', 'unknown'},
         'uncertainty': {'resolved', 'material', 'unknown'},
         'consequence': {'ordinary', 'significant', 'unknown'}, 'origin': {'user', 'plan', 'harness'}}


def normalize_task_facts(task: dict, expected_scope: dict) -> dict:
    def fail():
        raise WorkflowError('TASK_FACTS_INVALID', 'Task facts must be bounded, valid and match the current scope.')
    if not isinstance(task, dict) or set(task) - FIELDS or FIELDS - {'item_id'} - set(task):
        fail()
    if type(task['schema_version']) is not int or task['schema_version'] != 1:
        fail()
    for key in ('task_id', 'run_id', 'stage', 'actor_id', 'item_id', 'required_output'):
        if key not in task:
            continue
        value = task[key]
        if not isinstance(value, str) or not value.strip() or len(value.encode('utf-8')) > (4096 if key == 'required_output' else 128):
            fail()
    for key, options in ENUMS.items():
        if not isinstance(task[key], str) or task[key] not in options:
            fail()
    for key in ('scope', 'evidence_refs'):
        values = task[key]
        if (not isinstance(values, list) or len(values) > 64 or any(not isinstance(v, str)
                or not v.strip() or len(v.encode('utf-8')) > 1024 for v in values)):
            fail()
    for value in task['scope']:
        path = PurePosixPath(value)
        if path.is_absolute() or '..' in path.parts or '\\' in value or re.match(r'^[A-Za-z]:', value):
            fail()
    for key in ('task_id', 'run_id', 'stage', 'actor_id', 'item_id'):
        if expected_scope.get(key) is not None and task.get(key) != expected_scope[key]:
            fail()
    if len(canonical(task)) > 65536:
        fail()
    return deepcopy(task)


def classify_task(policy: dict, task: dict | None, stage: str) -> dict:
    baseline = policy.get('stages', {}).get(stage)
    if task is None:
        return {'profile': baseline, 'reasons': ['STAGE_DEFAULT'], 'task_hash': None, 'classification_origin': None}
    facts = normalize_task_facts(task, {'stage': stage})
    rules = policy.get('task_routing', {})
    profile, reason = baseline, 'STAGE_DEFAULT'
    if facts['kind'] == 'deterministic':
        if baseline != 'deterministic':
            raise WorkflowError('TASK_DETERMINISTIC_MISMATCH', 'Only existing deterministic helper stages may bypass a model.')
        reason = 'DETERMINISTIC_OPERATION'
    elif baseline == 'deterministic':
        raise WorkflowError('TASK_DETERMINISTIC_MISMATCH', 'Model work cannot be disguised as a deterministic helper.')
    elif (facts['kind'] in rules.get('reasoning_kinds', []) or facts['complexity'] != 'bounded'
          or facts['uncertainty'] != 'resolved' or facts['consequence'] != 'ordinary'):
        profile, reason = rules.get('reasoning_profile', baseline), 'REASONING_OR_UNCERTAINTY'
    elif facts['kind'] in rules.get('discovery_kinds', []) and facts['scope'] and facts['evidence_refs']:
        profile, reason = rules.get('discovery_profile', baseline), 'BOUNDED_DISCOVERY'
    elif facts['kind'] == 'implementation':
        profile = rules.get('implementation_profile', baseline)
        # An implementation subtask cannot lower a more demanding stage default.
        order = rules.get('profile_order', [])
        if baseline in order and profile in order and order.index(baseline) > order.index(profile):
            profile = baseline
        reason = 'BOUNDED_IMPLEMENTATION'
    return {'profile': profile, 'reasons': [reason], 'task_hash': digest(facts), 'classification_origin': facts['origin']}
