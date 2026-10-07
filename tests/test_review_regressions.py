import json
import subprocess
import sys
import unittest
import tempfile
import io
from contextlib import redirect_stdout
from unittest.mock import patch
from copy import deepcopy
from pathlib import Path

from tests import test_foundation_flow as flow
ENTRY = flow.ENTRY
from tests.test_runs import state as fixture_state
from workflow_lib.store import WorkflowError, read_state, transact
from workflow_lib.briefs import assemble_brief
from workflow_lib.plans import validate_plan
from workflow_lib.specs import validate_spec
from workflow_lib.runs import issue_attempt
import run as dispatcher


class ReviewRegressions(unittest.TestCase):
    setUp = flow.FoundationFlowTests.setUp
    tearDown = flow.FoundationFlowTests.tearDown
    cli = flow.FoundationFlowTests.cli
    put_json = flow.FoundationFlowTests.put_json

    def start(self):
        transact(self.control, 0, 'seed', {'kind': 'fixture', 'payload': fixture_state()})
        self.cli('run', 'start', '--root', self.control, '--run-id', 'r')

    def next(self, **kwargs):
        args = ['run', 'next', '--root', self.control, '--run-id', 'r']
        for key, value in kwargs.items():
            args += ['--' + key.replace('_', '-'), value]
        return self.cli(*args)

    def test_result_and_abandon_retries_return_committed_state(self):
        self.start()
        token = self.next()['attempt_id']
        args = ['run', 'result', '--root', self.control, '--run-id', 'r', '--attempt-id', token,
                '--result', '{"outcome":"failed"}', '--operation-id', 'submit']
        self.cli(*args)
        replay = self.cli(*args)
        self.assertTrue(replay['replayed'])
        second = self.next()['attempt_id']
        self.cli('run', 'abandon', '--root', self.control, '--run-id', 'r', '--attempt-id', second,
                 '--operation-id', 'submit')
        self.assertEqual(read_state(self.control)['data']['runs']['r']['active_attempt']['token'], second)
        args = ['run', 'abandon', '--root', self.control, '--run-id', 'r', '--attempt-id', second,
                '--operation-id', 'abandon']
        self.cli(*args)
        self.assertTrue(self.cli(*args)['replayed'])
        third = self.next()['attempt_id']
        args = ['run', 'result', '--root', self.control, '--run-id', 'r', '--attempt-id', third,
                '--result', '{"outcome":"failed"}']
        self.cli(*args)
        self.assertTrue(self.cli(*args)['replayed'])

    def test_layer_replay_does_not_report_uncommitted_input(self):
        a = self.put_json('a.json', {'slices': {}})
        b = self.put_json('b.json', {'slices': {'architecture': {'status': 'answered', 'value': 'B'}}})
        self.cli('context', 'set', '--root', self.control, '--layer', 'org', '--file', a, '--operation-id', 'same')
        response = self.cli('context', 'set', '--root', self.control, '--layer', 'project', '--file', b, '--operation-id', 'same')
        self.assertNotIn('stored_layer', response)
        self.assertNotIn('project', read_state(self.control)['data']['context'])

    def test_commit_replay_after_preflight_returns_only_a_committed_receipt(self):
        transact(self.control, 0, 'raced', {'kind': 'original', 'payload': {'saved': 'A'}})
        with self.assertRaises(dispatcher._OperationReplay) as caught:
            dispatcher._commit(self.control, 0, 'raced', {'kind': 'proposed', 'payload': {'saved': 'B'}})
        self.assertEqual(caught.exception.result['event_kind'], 'original')
        self.assertTrue(caught.exception.result['replayed'])
        self.assertEqual(read_state(self.control)['data']['saved'], 'A')

    def test_changed_context_requires_resolution_before_new_run(self):
        self.start()
        layer = self.put_json('layer.json', {'slices': {'architecture': {'status': 'answered', 'value': 'A'}}})
        self.cli('context', 'set', '--root', self.control, '--layer', 'org', '--file', layer)
        self.cli('context', 'resolve', '--root', self.control)
        layer.write_text(json.dumps({'slices': {'architecture': {'status': 'answered', 'value': 'B'}}}))
        self.cli('context', 'set', '--root', self.control, '--layer', 'org', '--file', layer)
        bad = self.cli('run', 'start', '--root', self.control, '--run-id', 'new', ok=False)
        self.assertIn('CONTEXT_NOT_RESOLVED', bad.stdout)
        self.cli('context', 'resolve', '--root', self.control)
        self.cli('run', 'start', '--root', self.control, '--run-id', 'new')
        self.assertEqual(read_state(self.control)['data']['runs']['new']['context']['values']['architecture'], 'B')
        current = read_state(self.control)
        transact(self.control, current['version'], 'legacy-layer-edit', {'kind': 'context.layer.set',
            'payload': {'context': {'org': {'slices': {'architecture': {'status': 'answered', 'value': 'C'}}}}}})
        bad = self.cli('run', 'start', '--root', self.control, '--run-id', 'stale', ok=False)
        self.assertIn('CONTEXT_NOT_RESOLVED', bad.stdout)

    def test_failed_results_and_blocked_dependencies_survive_compact_resume(self):
        self.start()
        token = self.next()['attempt_id']
        self.cli('run', 'result', '--root', self.control, '--run-id', 'r', '--attempt-id', token,
                 '--result', '{"outcome":"failed","detail":"critical failing test"}')
        for command in ('status', 'summary', 'brief'):
            response = self.cli('run', command, '--root', self.control, '--run-id', 'r')
            self.assertEqual(response['latest_attempts']['W1']['result']['detail'], 'critical failing test')
            self.assertEqual(response['blocked_items'], [{'id': 'W2', 'blocked_by': ['W1']}])

    def test_malformed_context_is_rejected_before_commit(self):
        for value in ({'slices': {'architecture': None}}, {'slices': []}, [], {'slices': {'a': {'status': []}}}):
            path = self.put_json('invalid.json', value)
            response = self.cli('context', 'set', '--root', self.control, '--layer', 'org', '--file', path, ok=False)
            self.assertIn('INVALID_CONTEXT', response.stdout)
            self.assertEqual(read_state(self.control)['version'], 0)

    def test_invalid_enum_references_and_stage_metadata_have_stable_errors(self):
        fixture = fixture_state()
        for field, value in (('kind', []), ('requirement_ids', [[]])):
            plan = deepcopy(fixture['plan'])
            plan['work_items'][0][field] = value
            with self.assertRaises(WorkflowError):
                validate_plan({**fixture['spec'], 'approval': fixture['approval']}, plan)
        for stage in (None, {'required_slices': [None]}, {'kind_instructions': []}):
            plan = {**fixture['plan'], 'stage': stage}
            with self.assertRaises(WorkflowError):
                validate_plan({**fixture['spec'], 'approval': fixture['approval']}, plan)
        spec = {**fixture['spec'], 'mode': []}
        with self.assertRaises(WorkflowError):
            validate_spec(spec)

    def test_historical_event_payloads_remain_equal_to_disk(self):
        self.start()
        token = self.next()['attempt_id']
        self.cli('run', 'abandon', '--root', self.control, '--run-id', 'r', '--attempt-id', token)
        state = read_state(self.control)
        for event in state['operations'].values():
            disk = json.loads((self.control / 'events' / f"{event['sequence']:08d}.json").read_text())
            self.assertEqual(event, disk)

    def test_telemetry_deduplicates_supplied_ids_and_counts_independent_reads(self):
        path = self.put_json('org.json', {'slices': {}})
        for _ in range(2):
            self.cli('context', 'set', '--root', self.control, '--layer', 'org', '--file', path, '--operation-id', 'B')
        rows = [json.loads(line) for line in (self.control / 'offload.jsonl').read_text().splitlines()]
        self.assertEqual([row['operation_id'] for row in rows], ['B'])
        self.cli('context', 'resolve', '--root', self.control)
        current = read_state(self.control)
        transact(self.control, current['version'], 'seed', {'kind': 'fixture', 'payload': fixture_state()})
        self.cli('run', 'start', '--root', self.control, '--run-id', 'r')
        self.next()
        for _ in range(2):
            self.cli('run', 'brief', '--root', self.control, '--run-id', 'r')
        rows = [json.loads(line) for line in (self.control / 'offload.jsonl').read_text().splitlines()]
        self.assertEqual(len([row for row in rows if row['operation'] == 'run.brief']), 2)

    def test_next_rejects_different_item_even_during_replay(self):
        self.start()
        self.next(operation_id='issue')
        for kwargs in ({'item': 'W2'}, {'item': 'unknown'}, {'item': 'W2', 'operation_id': 'issue'}):
            args = ['run', 'next', '--root', self.control, '--run-id', 'r']
            for key, value in kwargs.items():
                args += ['--' + key.replace('_', '-'), value]
            response = self.cli(*args, ok=False)
            self.assertIn('ITEM_INELIGIBLE', response.stdout)

    def test_concurrent_attempt_replay_rejects_a_different_requested_item(self):
        fixture = fixture_state()
        fixture['plan']['work_items'][1]['dependencies'] = []
        transact(self.control, 0, 'seed', {'kind': 'fixture', 'payload': fixture})
        self.cli('run', 'start', '--root', self.control, '--run-id', 'r')

        def concurrent_issue(root, version, operation_id, event):
            run = read_state(root)['data']['runs']['r']
            issued = issue_attempt(run, 'W1')
            transact(root, version, operation_id, {'kind': 'run.attempt.issued',
                     'payload': {'run_id': 'r', 'attempt': issued['active_attempt']}})
            return transact(root, version, operation_id, event)

        stdout = io.StringIO()
        with patch.object(dispatcher, 'transact', side_effect=concurrent_issue), redirect_stdout(stdout):
            code = dispatcher.main(['run', 'next', '--root', str(self.control), '--run-id', 'r',
                                    '--item', 'W2', '--operation-id', 'race'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout.getvalue())['error'], 'ITEM_INELIGIBLE')
        self.assertEqual(read_state(self.control)['data']['runs']['r']['active_attempt']['item_id'], 'W1')

    def test_tilde_root_uses_one_directory_for_state_and_telemetry(self):
        path = self.put_json('org.json', {'slices': {}})
        with tempfile.TemporaryDirectory(prefix='devflow-review-') as home_temp:
            root = Path(home_temp) / 'control'
            stdout = io.StringIO()
            # Isolate home expansion without writing to or changing the real home.
            original = Path.expanduser
            def expand(value):
                return root if str(value) == '~/control' else original(value)
            with patch.object(Path, 'expanduser', expand), redirect_stdout(stdout):
                code = dispatcher.main(['context', 'set', '--root', '~/control',
                                        '--layer', 'org', '--file', str(path)])
            self.assertEqual(code, 0, stdout.getvalue())
            self.assertTrue((root / 'offload.jsonl').is_file())
            self.assertFalse((self.repo / '~').exists())
