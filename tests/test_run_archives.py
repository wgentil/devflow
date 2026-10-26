"""Terminal storage is physical maintenance, never loss of logical history."""
import importlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib import store, sqlite_store
from control_store_fixtures import owned_control

class RunArchiveTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(owned_control())
        sqlite_store.initialize_store(self.root)

    def backend(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.run_archives'))
        return importlib.import_module('workflow_lib.run_archives')

    def seed(self, runs):
        return store.transact(self.root, 0, 'seed', {'kind': 'seed', 'payload': {
            'runs': runs, 'extension': {'unknown': 'preserved'},
            'usage': {'events': [], 'gaps': ['unknown usage'], 'unbound': []}}})

    def run_record(self, key, status='discarded', *, path='shared_test.py'):
        return {'id': key, 'status': status, 'active_attempt': None,
                'repositories': {'app': {'location': '/nonexistent/old-checkout'}},
                'items': {'w': {'status': 'complete', 'attempts': [{'token': key + '-t'}]}},
                'verification_proofs': {'p': {'phase': 'GREEN', 'fresh': True, 'test_hashes': {path: 'h'}}},
                'verifier_proofs': {'p': {'passed': True}},
                'review_packages': {}, 'context': {'rule': 'é東京'}, 'actors': {'implementer': 'dev'}}

    def test_terminal_detail_roundtrip(self):
        archives = self.backend()
        self.seed({key: self.run_record(key, status) for key, status in [('a', 'delivered'), ('b', 'discarded')]})
        before = store.read_state(self.root)
        for key in ('a', 'b'):
            summary = archives.archive_run(self.root, key)
            self.assertEqual(summary['id'], key)
            self.assertNotIn('repositories', summary)
            self.assertEqual(archives.read_run(self.root, key), before['data']['runs'][key])
        self.assertEqual(store.read_state(self.root), before)
        self.assertEqual([row['id'] for row in archives.iter_run_summaries(self.root, page_size=1)], ['a', 'b'])
        self.assertEqual(list(archives.iter_events(self.root, page_size=1)), list(before['operations'].values()))

    def test_archive_retry_needs_no_live_checkout(self):
        archives = self.backend()
        self.seed({'a': self.run_record('a')})
        receipt = sqlite_store.lookup_operation(self.root, 'seed')
        archives.archive_run(self.root, 'a')
        retry = store.transact(self.root, -100, 'seed', {'kind': 'different', 'payload': {}})
        self.assertTrue(retry['replayed'])
        self.assertEqual(retry['event'], receipt)
        self.assertEqual(archives.read_run(self.root, 'a')['context'], {'rule': 'é東京'})

    def test_active_and_corrupt_archive_boundaries(self):
        archives = self.backend()
        self.seed({'active': self.run_record('active', 'active'), 'closed': self.run_record('closed')})
        before = store.read_state(self.root)
        with self.assertRaises(store.WorkflowError): archives.archive_run(self.root, 'active')
        self.assertEqual(store.read_state(self.root), before)
        archives.archive_run(self.root, 'closed')
        with sqlite_store.connection(self.root) as conn:
            raw = json.loads(conn.execute('SELECT payload FROM entities WHERE space=? AND key=?',
                             (sqlite_store._space(('runs',)), 'closed')).fetchone()[0])
        ref = raw['reference']
        path = self.root / 'objects/manifests' / ref['object_id'][:2] / (ref['object_id'][2:] + '.json')
        path.write_text('{}')
        with self.assertRaises(store.WorkflowError): archives.read_run(self.root, 'closed')
        # A separate active record remains independently readable.
        self.assertEqual(archives.read_run(self.root, 'active'), before['data']['runs']['active'])

    def test_shared_test_invalidation_reaches_archived_runs(self):
        archives = self.backend()
        runs = {key: self.run_record(key, 'active' if key == 'active' else 'discarded',
                 path='unrelated.py' if key == 'unrelated' else 'shared_test.py')
                for key in ('active', 'closed1', 'closed2', 'unrelated')}
        runs['active']['test_change_proposals'] = {'change': {'id': 'change', 'approval': {'actor_id': 'owner'},
            'status': 'approved', 'changed_paths': ['shared_test.py']}}
        self.seed(runs)
        for key in ('closed1', 'closed2', 'unrelated'): archives.archive_run(self.root, key)
        old_objects = set((self.root / 'objects/manifests').rglob('*.json'))
        store.transact(self.root, 1, 'invalidate', {'kind': 'test.change.applying',
            'payload': {'run_id': 'active', 'proposal_id': 'change'}})
        state = store.read_state(self.root)
        for key in ('active', 'closed1', 'closed2'):
            self.assertFalse(state['data']['runs'][key]['verification_proofs']['p']['fresh'])
            self.assertFalse(state['data']['runs'][key]['verifier_proofs']['p']['passed'])
        self.assertTrue(state['data']['runs']['unrelated']['verification_proofs']['p']['fresh'])
        self.assertTrue(old_objects.issubset(set((self.root / 'objects/manifests').rglob('*.json'))))
        with sqlite_store.connection(self.root) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM entities WHERE codec='archive'").fetchone()[0], 3)

    def test_incomplete_dependency_rows_cannot_skip_archived_run(self):
        archives = self.backend()
        active = self.run_record('active', 'active')
        active['test_change_proposals'] = {'change': {'id': 'change', 'approval': {'actor_id': 'owner'},
            'status': 'approved', 'changed_paths': ['shared_test.py']}}
        self.seed({'active': active, 'closed': self.run_record('closed')})
        archives.archive_run(self.root, 'closed')
        conn = sqlite3.connect(self.root / 'store-v2/control.sqlite3')
        try:
            conn.execute("DELETE FROM dependencies WHERE kind='test-path' AND run_id='closed'")
            # Simulate lost index data even when the dirty marker appears clean.
            conn.execute("DELETE FROM dependency_dirty")
            conn.commit()
        finally: conn.close()
        with self.assertRaises(store.WorkflowError) as caught:
            store.transact(self.root, 1, 'invalidate', {'kind': 'test.change.applying',
                'payload': {'run_id': 'active', 'proposal_id': 'change'}})
        self.assertEqual(caught.exception.code, 'CORRUPT_DEPENDENCY_INDEX')
        self.assertEqual(sqlite_store.lookup_operation(self.root, 'invalidate'), None)

    def test_missing_dependency_index_fails_closed(self):
        archives = self.backend()
        self.seed({'a': self.run_record('a')})
        archives.archive_run(self.root, 'a')
        conn = sqlite3.connect(self.root / 'store-v2/control.sqlite3')
        try: conn.execute('DROP INDEX dependency_source'); conn.commit()
        finally: conn.close()
        with self.assertRaises(store.WorkflowError):
            store.transact(self.root, 1, 'new', {'kind': 'note', 'payload': {'safe': False}})
