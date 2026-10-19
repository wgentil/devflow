import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.model_policy import resolve_profile
from workflow_lib.store import WorkflowError


def task(**changes):
    return {'schema_version': 1, 'task_id': 'T1', 'run_id': 'run', 'stage': 'implementation',
            'actor_id': 'worker', 'item_id': 'W1', 'kind': 'implementation', 'scope': ['src/a.py'],
            'required_output': 'Implement R1 and report evidence', 'complexity': 'bounded',
            'uncertainty': 'resolved', 'consequence': 'ordinary', 'evidence_refs': ['plan:W1'],
            'origin': 'plan', **changes}


class TaskRoutingTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / 'definitions/model-policy.json').read_text())

    def test_absent_facts_keep_stage_and_known_tasks_route_conservatively(self):
        from workflow_lib.task_routing import classify_task
        self.assertEqual(classify_task(self.policy, None, 'implementation')['profile'], 'efficient-coding')
        cases = [({'kind': 'discovery'}, 'fast-analysis'),
                 ({'uncertainty': 'material'}, 'deep-reasoning'),
                 ({'consequence': 'significant'}, 'deep-reasoning'),
                 ({'complexity': 'unknown'}, 'deep-reasoning'),
                 ({'kind': 'review'}, 'deep-reasoning'),
                 ({'scope': [], 'kind': 'discovery'}, 'efficient-coding')]
        for changes, expected in cases:
            with self.subTest(changes=changes):
                self.assertEqual(classify_task(self.policy, task(**changes), 'implementation')['profile'], expected)

    def test_invalid_scope_and_claimed_deterministic_work_cannot_bypass_routing(self):
        from workflow_lib.task_routing import normalize_task_facts, classify_task
        for changes in ({'schema_version': True}, {'scope': ['../secret']}, {'scope': ['/secret']},
                        {'scope': ['C:\\secret']}, {'scope': ['src/../../secret']},
                        {'complexity': 'easy'}, {'extra': 'unknown'}, {'required_output': 'é' * 3000}):
            with self.subTest(changes=changes), self.assertRaises(WorkflowError):
                normalize_task_facts(task(**changes), {})
        for key in ('run_id', 'stage', 'actor_id', 'item_id'):
            with self.subTest(key=key), self.assertRaises(WorkflowError):
                normalize_task_facts(task(), {key: 'different'})
        with self.assertRaises(WorkflowError):
            classify_task(self.policy, task(kind='deterministic'), 'implementation')
        self.assertEqual(classify_task(self.policy, task(stage='tests', kind='deterministic'), 'tests')['profile'], 'deterministic')

    def test_decisions_are_content_bound_without_mutation(self):
        from workflow_lib.task_routing import classify_task
        value = task(); before = copy.deepcopy(value)
        first = classify_task(self.policy, value, 'implementation')
        self.assertEqual(first, classify_task(self.policy, value, 'implementation'))
        self.assertNotEqual(first['task_hash'], classify_task(self.policy, task(required_output='Other'), 'implementation')['task_hash'])
        self.assertEqual(value, before)

    def test_resolver_uses_task_profile_but_preserves_explicit_preferences(self):
        request = {'host': 'claude', 'stage': 'implementation', 'task': task(kind='review')}
        result = resolve_profile(self.policy, request, {}, {}, None)
        self.assertEqual(result['profile'], 'deep-reasoning')
        self.assertEqual(result['routing']['classification_origin'], 'plan')
        self.assertFalse(result['dispatch'])
        explicit = resolve_profile(self.policy, {**request, 'profile': 'efficient-coding', 'effort': 'medium'}, {}, {}, None)
        self.assertEqual(explicit['profile'], 'efficient-coding')
        self.assertEqual(explicit['recommendation']['effort'], 'medium')
        self.assertEqual(resolve_profile(self.policy, {**request, 'allowed_models': []}, {}, {}, None)['status'], 'block')
