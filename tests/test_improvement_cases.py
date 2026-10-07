import sys
import json
import argparse
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))

from workflow_lib.improvement_cases import propose_case
from workflow_lib.improvement_traces import project_run_trace
from workflow_lib.journal_domains import digest
from workflow_lib.store import read_state, transact, WorkflowError


class ImprovementCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        run = {'id': 'r', 'status': 'active', 'plan': {'work_items': []},
               'improvement_trace_enabled': True}
        transact(self.root, 0, 'fixture', {'kind': 'fixture', 'payload': {'runs': {'r': run}}})

    def tearDown(self): self.temp.cleanup()

    def event(self, kind, request, operation_id):
        state = read_state(self.root)
        return transact(self.root, state['version'], operation_id,
                        {'kind': 'domain.improve.' + kind, 'payload': {'request': request}})

    def feedback_request(self):
        trace = project_run_trace(read_state(self.root), 'r', True)
        return {'run_id': 'r', 'trace_hash': digest(trace), 'actor_id': 'reviewer',
                'feedback': {'observation': 'gate missed case', 'owner': 'validator',
                             'expected': {'status': 'pass'}, 'command': ['python3', '-c',
                             'import json; print(json.dumps({"status":"pass"}))'],
                             'scoring_version': 1}}

    def test_feedback_binds_to_trace(self):
        request = self.feedback_request()
        request['trace_hash'] = 'stale'
        with self.assertRaises(WorkflowError): self.event('feedback', request, 'bad')
        self.assertNotIn('improvement_feedback', read_state(self.root)['data'])

    def test_model_candidate_needs_human_approval(self):
        response = self.event('feedback', self.feedback_request(), 'feedback')
        candidate = response['state']['data']['domain_receipts']['feedback']['candidate']
        self.assertNotIn(candidate['case_id'], response['state']['data'].get('improvement_cases', {}))

    def test_changed_case_hash_invalidates_approval(self):
        response = self.event('feedback', self.feedback_request(), 'feedback')
        receipt = response['state']['data']['domain_receipts']['feedback']
        with self.assertRaises(WorkflowError):
            self.event('case-approve', {'feedback_id': receipt['feedback_id'],
                       'case_hash': 'changed', 'actor_id': 'human', 'approved': True}, 'bad')

    def test_duplicate_approval_replays_without_new_case(self):
        response = self.event('feedback', self.feedback_request(), 'feedback')
        receipt = response['state']['data']['domain_receipts']['feedback']
        request = {'feedback_id': receipt['feedback_id'],
                   'case_hash': receipt['candidate']['case_hash'],
                   'actor_id': 'human', 'approved': True}
        self.event('case-approve', request, 'approve')
        replay = self.event('case-approve', request, 'approve')
        self.assertTrue(replay['replayed'])
        self.assertEqual(len(read_state(self.root)['data']['improvement_cases']), 1)

    def test_model_evaluate_requires_approved_case_ids(self):
        from commands.improve import dispatch
        source = self.root / 'model.json'
        source.write_text(json.dumps({'host': 'codex', 'model_id': 'm',
                                      'host_version': '1.0', 'case_ids': ['unknown'],
                                      'results': []}))
        with self.assertRaises(WorkflowError):
            dispatch(argparse.Namespace(improve_command='model-evaluate',
                                        root=str(self.root), input=str(source)))


if __name__ == '__main__': unittest.main()
