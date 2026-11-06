"""Recorded selections must not depend on future live defaults."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from test_runs import state

class IssueRunContractTests(unittest.TestCase):
    def test_recorded_contract_survives_default_changes(self):
        self.assertTrue((Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/workflow_lib/issue_run_contracts.py').exists(), 'recorded run contract implementation missing')
        from workflow_lib.issue_run_contracts import historical_issue_run
        from workflow_lib.review_policy import new_review_policy
        contract = {'schema_version': 1, 'enforcement': {'protocol': 'devflow.python-enforcement/v1', 'policy_version': 1}, 'review_policy': new_review_policy()}
        data = state()
        with patch('workflow_lib.review_policy.new_review_policy', side_effect=AssertionError('live default consulted')):
            run = historical_issue_run(data, 'recorded', data['plan'], contract)
        self.assertEqual(run['enforcement'], contract['enforcement'])
        self.assertEqual(run['review_policy'], contract['review_policy'])

    def test_legacy_construction_does_not_select_current_policy(self):
        self.assertTrue((Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/workflow_lib/issue_run_contracts.py').exists(), 'recorded run contract implementation missing')
        from workflow_lib.issue_run_contracts import historical_issue_run
        data = state()
        run = historical_issue_run(data, 'historical', data['plan'], None)
        self.assertNotIn('enforcement', run)
        self.assertNotIn('review_policy', run)

    def test_unknown_contract_fails_closed(self):
        self.assertTrue((Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/workflow_lib/issue_run_contracts.py').exists(), 'recorded run contract implementation missing')
        from workflow_lib.issue_run_contracts import validate_run_contract
        from workflow_lib.store import WorkflowError
        for value in ({}, None, {'schema_version': True}, {'schema_version': 99}):
            with self.assertRaises(WorkflowError): validate_run_contract(value)

    def test_plain_start_keeps_recorded_policy(self):
        import json
        from workflow_lib import store
        fixture = Path(__file__).parent / 'fixtures/issue-replay-upgrade/v0.3.17-plain.json'
        case = json.loads(fixture.read_text())
        result = store._empty()
        for event in case['events']:
            store._apply_event(result, event)
        self.assertEqual(result['data'], case['expected']['data'])

    def test_current_proof_without_execution_is_rejected(self):
        import json
        from workflow_lib import store
        from workflow_lib.issue_run_contracts import V0318
        case = json.loads((Path(__file__).parent / 'fixtures/issue-replay-upgrade/v0.3.17-proof.json').read_text())
        case['events'][3]['payload']['request']['run_contract'] = V0318
        result = store._empty()
        for event in case['events'][:-1]: store._apply_event(result, event)
        with self.assertRaises(store.WorkflowError) as caught:
            store._apply_event(result, case['events'][-1])
        self.assertEqual(caught.exception.code, 'TOOL_EXECUTION_REQUIRED')

    def test_live_start_stamps_and_retry_does_not_consult_new_defaults(self):
        import json, tempfile
        from types import SimpleNamespace
        from workflow_lib import store
        from workflow_lib.issue_run_contracts import V0318
        from commands.issues import dispatch
        case = json.loads((Path(__file__).parent / 'fixtures/issue-replay-upgrade/v0.3.17-proof.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'control'; (root / 'events').mkdir(parents=True)
            for event in case['events'][:3]:
                (root / 'events' / f"{event['sequence']:08d}.json").write_text(json.dumps(event))
            path = Path(tmp) / 'input.json'; path.write_text(json.dumps(case['events'][3]['payload']['request']))
            args = SimpleNamespace(root=str(root), input=str(path), operation='start', operation_id='new-start', operation_id_explicit=True, expected_version=None)
            first = dispatch(args)
            event = store.read_state(root)['operations']['new-start']
            self.assertEqual(event['payload']['request'].get('run_contract'), V0318)
            with patch('workflow_lib.issue_run_contracts.current_run_contract', side_effect=AssertionError('default on retry')):
                second = dispatch(args)
            self.assertTrue(second['replayed'])
            self.assertEqual(first['run_id'], second['run_id'])

    def test_capture_and_specify_do_not_select_policy(self):
        import json
        from workflow_lib import store
        case = json.loads((Path(__file__).parent / 'fixtures/issue-replay-upgrade/v0.3.17-proof.json').read_text())
        for intent in ('capture', 'specify'):
            result = store._empty()
            for event in case['events'][:3]: store._apply_event(result, event)
            event = case['events'][3]; event['payload']['request']['intent'] = intent
            store._apply_event(result, event)
            self.assertFalse(result['data'].get('runs'))
