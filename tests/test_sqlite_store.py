"""Indexed authority must retain the legacy transaction and receipt contracts."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib import store
from control_store_fixtures import owned_control, legacy_root


class SQLiteStoreTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(owned_control())

    def backend(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.sqlite_store'),
                             'The indexed backend must implement the real transaction contract')
        return importlib.import_module('workflow_lib.sqlite_store')

    def test_transaction_and_retry_parity(self):
        sql = self.backend()
        sql.initialize_store(self.root)
        first = store.transact(self.root, 0, 'one', {'kind': 'note', 'payload': {'x': 1}})
        self.assertEqual(first['state']['version'], 1)
        self.assertEqual(first['state']['data'], {'x': 1})
        retry = store.transact(self.root, 0, 'one', {'kind': 'different', 'payload': {'x': 2}})
        self.assertTrue(retry['replayed'])
        self.assertEqual(retry['event'], first['event'])
        for kind in ('domain.future.changed','domain.host.attach'):
            retry = store.transact(self.root, -1, 'one', {'kind':kind,'payload':{'request':None}})
            self.assertEqual(retry['event'],first['event'])
            self.assertTrue(retry['replayed'])
        self.assertEqual(sql.lookup_operation(self.root, 'one'), first['event'])
        self.assertIsNone(sql.lookup_operation(self.root, 'missing'))
        self.assertEqual(sql.read_head_event(self.root), first['event'])
        with self.assertRaises(store.WorkflowError) as caught:
            store.transact(self.root, 0, 'stale', {'kind': 'note', 'payload': {'x': 2}})
        self.assertEqual(caught.exception.code, 'STALE_STATE')
        def fail(state):
            self.assertEqual(state['version'], 1)
            raise store.WorkflowError('TEST_PRECOMMIT', 'do not commit')
        with self.assertRaises(store.WorkflowError):
            store.transact(self.root, 1, 'failed', {'kind': 'note', 'payload': {'x': 2}}, precommit=fail)
        self.assertEqual(store.read_state(self.root)['data'], {'x': 1})
        self.assertIsNone(sql.lookup_operation(self.root, 'failed'))
        token = store.HOST_CONTEXT.set({'binding_id': 'missing', 'revision': 1})
        try:
            with self.assertRaises(store.WorkflowError) as caught:
                store.transact(self.root, 1, 'bad-host', {'kind': 'note', 'payload': {'x': 3}})
            self.assertEqual(caught.exception.code, 'STALE_BINDING')
        finally:
            store.HOST_CONTEXT.reset(token)

    def test_host_role_release_and_live_guard_precede_retry(self):
        sql = self.backend()
        sql.initialize_store(self.root)
        binding = {'binding_id': 'b', 'revision': 1, 'status': 'active', 'role': 'branch-reviewer',
                   'actor_id': 'reviewer', 'run_id': 'r', 'release': {'fingerprint': 'old'}}
        store.transact(self.root, 0, 'seed', {'kind': 'seed', 'payload': {'host_bindings': {'b': binding}}})
        token = store.HOST_CONTEXT.set({'binding_id': 'b', 'revision': 1})
        try:
            with self.assertRaises(store.WorkflowError) as caught:
                store.transact(self.root, 0, 'seed', {'kind': 'note', 'payload': {}})
            self.assertEqual(caught.exception.code, 'HOST_CONFLICT')
        finally: store.HOST_CONTEXT.reset(token)
        token = store.HOST_CONTEXT.set({'binding_id': 'b', 'revision': 1, 'release': True})
        try:
            with self.assertRaises(store.WorkflowError) as caught:
                store.transact(self.root, 0, 'seed', {'kind': 'note', 'payload': {}})
            self.assertEqual(caught.exception.code, 'RELEASE_MISMATCH')
        finally: store.HOST_CONTEXT.reset(token)
        def refuse(): raise store.WorkflowError('LIVE_GUARD', 'binding changed')
        token = store.LIVE_TRANSFER.set(refuse)
        try:
            with self.assertRaises(store.WorkflowError) as caught:
                store.transact(self.root, 0, 'seed', {'kind': 'note', 'payload': {}})
            self.assertEqual(caught.exception.code, 'LIVE_GUARD')
        finally: store.LIVE_TRANSFER.reset(token)
        self.assertEqual(store.read_state(self.root)['version'], 1)

    def test_domain_receipt_and_conflict_parity(self):
        sql = self.backend()
        sql.initialize_store(self.root)
        from commands.journal import commit
        from types import SimpleNamespace
        parsed = SimpleNamespace(root=str(self.root), operation_id='repo', operation_id_explicit=True,
                                 expected_version=None)
        first = commit(parsed, 'domain.host.init', {'repo_id': 'app', 'location': '/owned/repository'})
        self.assertEqual(first['repo_id'], 'app')
        again = commit(parsed, 'domain.host.init', {'repo_id': 'app', 'location': '/owned/repository'})
        self.assertTrue(again['replayed'])
        self.assertEqual(again['event_sequence'], 1)
        with self.assertRaises(store.WorkflowError) as caught:
            commit(parsed, 'domain.host.init', {'repo_id': 'other', 'location': '/owned/repository'})
        self.assertEqual(caught.exception.code, 'OPERATION_CONFLICT')
        self.assertEqual(store.read_state(self.root)['version'], 1)

    def test_scoped_write_does_not_erase_unloaded_entities(self):
        sql = self.backend()
        sql.initialize_store(self.root)
        runs = {key: {'id': key, 'status': 'active', 'active_attempt': None} for key in ('a', 'b')}
        store.transact(self.root, 0, 'seed', {'kind': 'fixture', 'payload': {
            'runs': runs, 'unknown_extension': {'opaque': ['preserve', 3]}}})
        scopes = importlib.import_module('workflow_lib.storage_scopes')
        view = sql.read_working_state(self.root, scopes.ReadScope(run_ids=('a',), global_keys=()))
        self.assertEqual(set(view['data']['runs']), {'a'})
        self.assertNotIn('unknown_extension', view['data'])
        store.transact(self.root, 1, 'discard', {'kind': 'run.discarded', 'payload': {
            'run_id': 'a', 'reason': 'explicit test decision', 'actor_id': 'human'}})
        state = store.read_state(self.root)
        self.assertEqual(state['data']['runs']['a']['status'], 'discarded')
        self.assertEqual(state['data']['runs']['b'], runs['b'])
        self.assertEqual(state['data']['unknown_extension'], {'opaque': ['preserve', 3]})
        # Generic patches replace the entire named namespace, matching legacy update semantics.
        store.transact(self.root, 2, 'replace', {'kind': 'generic-extension', 'payload': {'runs': {'b': runs['b']}}})
        self.assertEqual(store.read_state(self.root)['data']['runs'], {'b': runs['b']})

    def test_event_family_replay_parity(self):
        from copy import deepcopy
        from unittest.mock import patch
        from storage_event_cases import (basic_event_streams, captured_event_streams,
                                         supplemental_domain_streams, registered_domain_kinds, registered_core_kinds)
        from workflow_lib.storage_scopes import CORE_KINDS
        sql = self.backend()
        streams = list(basic_event_streams()) + captured_event_streams() + list(supplemental_domain_streams())
        covered = set()
        for index, events in enumerate(streams):
            with self.subTest(stream=index), patch.object(store, '_guard_spec_approval'):
                # External repository approval is independently covered by the existing
                # live guard tests. This compares pure replay of frozen logical events.
                target = self.root / f'v2-{index}'
                sql.initialize_store(target)
                old = store._empty()
                for position, source in enumerate(events, 1):
                    event = {'schema_version': 1, 'sequence': position,
                             'operation_id': source.get('operation_id', source.get('id')),
                             'kind': source['kind'], 'payload': source['payload']}
                    if source.get('host_binding'): event['host_binding'] = source['host_binding']
                    store._apply_event(old, event)
                    old['version'] = position
                    old['operations'][event['operation_id']] = deepcopy(event)
                    token = store.HOST_CONTEXT.set(event.get('host_binding'))
                    try:
                        new = store.transact(target, position - 1, event['operation_id'],
                            {'kind': event['kind'], 'payload': event['payload']})
                    finally: store.HOST_CONTEXT.reset(token)
                    self.assertEqual(new['event'], event)
                    from workflow_lib.run_archives import archive_run
                    for run_id, run in old['data'].get('runs', {}).items():
                        if (run.get('status') in {'delivered', 'discarded'} and not run.get('active_attempt')
                                and not any(row.get('status') == 'running' for row in run.get('native_invocations', {}).values())
                                and not any(row.get('status') == 'claimed' for row in run.get('repair_cycles', []))):
                            archive_run(target, run_id)
                    actual = store.read_state(target)
                    self.assertEqual(actual['data'], old['data'], (index, position, event['kind']))
                    self.assertEqual(actual['operations'], old['operations'])
                    self.assertEqual(actual['version'], position)
                    covered.add(event['kind'])
        self.assertEqual(CORE_KINDS,registered_core_kinds())
        self.assertFalse(CORE_KINDS - covered, f'Missing valid core fixtures: {CORE_KINDS - covered}')
        self.assertFalse(registered_domain_kinds() - covered, f'Missing domain branches: {registered_domain_kinds() - covered}')
        families = {kind.split('.')[1] for kind in covered if kind.startswith('domain.')}
        self.assertEqual(families, {'host', 'pr', 'repair', 'issues', 'outbox', 'migrate',
                                   'ingest', 'stats', 'improve', 'harden'})

    def test_invalid_reducer_variants_have_legacy_failure_parity(self):
        from storage_event_cases import (basic_event_streams, captured_event_streams,
                                         supplemental_domain_streams, registered_domain_kinds, registered_core_kinds)
        kinds = {row['kind'] for stream in list(basic_event_streams()) + captured_event_streams() + list(supplemental_domain_streams())
                 for row in stream}
        sql = self.backend()
        for index, kind in enumerate(sorted(kinds)):
            with self.subTest(kind=kind):
                old_root = legacy_root(self.root / f'invalid-legacy-{index}')
                new_root = self.root / f'invalid-indexed-{index}'
                sql.initialize_store(new_root)
                outcomes = []
                for root in (old_root, new_root):
                    try:
                        result = store.transact(root, 0, 'invalid-variant', {'kind': kind, 'payload': {}})
                        outcomes.append(('accepted', result['event'], store.read_state(root)['data']))
                    except Exception as exc:
                        outcomes.append((getattr(exc, 'code', type(exc).__name__),))
                        self.assertEqual(store.read_state(root)['version'], 0)
                self.assertEqual(outcomes[0], outcomes[1])

    def test_projection_records_preserve_derived_iteration_order(self):
        sql = self.backend()
        from workflow_lib.run_archives import store_detail, hydrate_detail
        with owned_control() as root:
            run = {'id':'r','status':'discarded','active_attempt':None,
                   'native_invocations':{'z':{'status':'completed'},'a':{'status':'completed'}}}
            codec,payload,expected = sql._encode(root,run,'projection-json')
            self.assertEqual(list(sql._decode(root,codec,payload,expected)['native_invocations']),['z','a'])
            record=store_detail(root,run)
            self.assertEqual(list(hydrate_detail(root,record)['native_invocations']),['z','a'])

    def test_generic_replacement_does_not_hydrate_old_namespace(self):
        from unittest.mock import patch
        sql = self.backend()
        sql.initialize_store(self.root)
        old_value = 'old-large-body' * 20000
        store.transact(self.root, 0, 'old', {'kind': 'extension', 'payload': {'extension': old_value}})
        forbidden = sql._sha(sql._json(old_value).encode('utf-8'))
        decode = sql._decode
        def selected_only(*args):
            self.assertNotEqual(args[-1], forbidden, 'Replacement loaded an obsolete body')
            return decode(*args)
        with patch.object(sql, '_decode', side_effect=selected_only):
            store.transact(self.root, 1, 'new', {'kind': 'extension', 'payload': {'extension': 'new'}})
        self.assertEqual(store.read_state(self.root)['data']['extension'], 'new')

    def test_scopes_reject_unknown_domain_and_select_bound_usage(self):
        sql = self.backend()
        sql.initialize_store(self.root)
        store.transact(self.root, 0, 'seed', {'kind': 'note', 'payload': {
            'runs': {'r': {'id': 'r', 'status': 'active'}}}})
        event = {'kind': 'domain.stats.usage-import', 'payload': {'request': {
            'records': [{'source_id': 's', 'event_id': 'e', 'provider': 'p', 'model': 'm',
                         'input_tokens': 1, 'cached_tokens': 0, 'output_tokens': 1}],
            'bindings': {'s:e': {'run_id': 'r'}}}}}
        with owned_control() as legacy:
            legacy_root(legacy)
            store.transact(legacy, 0, 'seed', {'kind': 'note', 'payload': {
                'runs': {'r': {'id': 'r', 'status': 'active'}}}})
            old = store.transact(legacy, 1, 'usage', event)
            new = store.transact(self.root, 1, 'usage', event)
            self.assertEqual(store.read_state(self.root)['data'], old['state']['data'])
        from workflow_lib.storage_scopes import scope_for_event
        with self.assertRaises(store.WorkflowError):
            scope_for_event({'kind': 'domain.future.changed', 'payload': {'request': {}}}, 'future')

    def test_two_process_writers_have_one_cas_winner(self):
        sql = self.backend()
        sql.initialize_store(self.root)
        code = "import sys;from pathlib import Path;from workflow_lib.store import transact,WorkflowError\ntry:transact(Path(sys.argv[1]),0,sys.argv[2],{'kind':'note','payload':{'winner':sys.argv[2]}});print('commit')\nexcept WorkflowError as e:print(e.code)"
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'skills/workflow/scripts')}
        processes = [subprocess.Popen([sys.executable, '-B', '-c', code, str(self.root), name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env) for name in ('a', 'b')]
        outputs = []
        for process in processes:
            self.addCleanup(lambda p=process: p.kill() if p.poll() is None else None)
            out, err = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, err.decode('utf-8', errors='replace'))
            outputs.append(out.decode().strip())
        self.assertEqual(sorted(outputs), ['STALE_STATE', 'commit'])
        self.assertEqual(store.read_state(self.root)['version'], 1)

    def test_killed_after_projection_and_event_insert_rolls_back(self):
        sql = self.backend()
        sql.initialize_store(self.root)
        code = "import os,sys;from pathlib import Path;from workflow_lib import store,sqlite_store as sql\noriginal=sql._set_meta\ndef die(conn,key,value):\n if key=='head':os._exit(38)\n return original(conn,key,value)\nsql._set_meta=die\nstore.transact(Path(sys.argv[1]),0,'crashed',{'kind':'note','payload':{'large':'x'*200000}})"
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'skills/workflow/scripts')}
        result = subprocess.run([sys.executable, '-B', '-c', code, str(self.root)], env=env,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 38, result.stderr)
        self.assertEqual(store.read_state(self.root)['data'], {})
        self.assertEqual(store.read_state(self.root)['version'], 0)
        self.assertIsNone(sql.lookup_operation(self.root, 'crashed'))
        self.assertTrue(list((self.root / 'objects/manifests').rglob('*.json')))
        store.transact(self.root, 0, 'crashed', {'kind': 'note', 'payload': {'recovered': True}})
        self.assertEqual(store.read_state(self.root)['data'], {'recovered': True})

    def test_killed_precommit_leaves_no_event_or_projection(self):
        sql = self.backend()
        sql.initialize_store(self.root)
        code = "import os,sys;from pathlib import Path;from workflow_lib.store import transact\ndef die(state):os._exit(37)\ntransact(Path(sys.argv[1]),0,'interrupted',{'kind':'note','payload':{'partial':True}},precommit=die)"
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'skills/workflow/scripts')}
        result = subprocess.run([sys.executable, '-B', '-c', code, str(self.root)], env=env,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 37, result.stderr)
        self.assertEqual(store.read_state(self.root)['version'], 0)
        self.assertEqual(store.read_state(self.root)['data'], {})
        self.assertIsNone(sql.lookup_operation(self.root, 'interrupted'))
        self.assertFalse(store.transact(self.root, 0, 'interrupted', {'kind': 'note', 'payload': {'complete': True}})['replayed'])
