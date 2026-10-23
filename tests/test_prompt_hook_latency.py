"""Optional refresh cost must not weaken authoritative task completion."""
import hashlib
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib import host_hook, store
from workflow_lib.host_locators import locator_path, write_task_index


class PromptHookLatencyTests(unittest.TestCase):
    def setUp(self):
        from test_claude_hooks import HookTests
        self.fixture = HookTests('test_inactive_no_files_or_shell_effect')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.attach()
        self.project, self.root = self.fixture.project, self.fixture.root
        self.locator = locator_path(self.project, 'claude', 's1')

    def remove_hints(self):
        self.locator.unlink(missing_ok=True)
        self.locator.with_suffix('.tasks.json').unlink(missing_ok=True)

    def files(self):
        return {p.relative_to(self.project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.project / '.devflow').rglob('*') if p.is_file()}

    def optional_without_storage_reads(self, event, reason):
        before = self.files()
        original_open = Path.open
        snapshot = (self.root / 'state.json').resolve()
        def guarded_open(path, *args, **kwargs):
            self.assertNotEqual(path.resolve(), snapshot, 'optional discovery must not open the state snapshot')
            return original_open(path, *args, **kwargs)
        with patch.object(store, '_read_journal', side_effect=AssertionError('optional discovery replayed the journal')), patch.object(Path, 'open', guarded_open):
            result = host_hook.evaluate(self.project, 's1', event)
        self.assertEqual((result['status'], result['reason_code']), ('inactive', reason))
        self.assertIn('attach', result['message'].lower())
        self.assertEqual(self.files(), before, 'inactive discovery must not create or repair state/cache files')

    def test_undiscoverable_optional_events_do_not_replay_or_read_snapshot(self):
        self.remove_hints()
        for event in ('SessionStart', 'UserPromptSubmit'):
            with self.subTest(event=event):
                self.optional_without_storage_reads(event, 'ATTACHMENT_NOT_DISCOVERED')
        state = store.read_state(self.root)
        self.assertEqual(state['version'], 3)
        self.assertEqual(state['data']['runs']['run']['active_attempt']['token'], 't')

    def test_corrupt_locator_without_index_does_not_replay(self):
        self.locator.write_text('{', encoding='utf-8')
        for event in ('SessionStart', 'UserPromptSubmit'):
            with self.subTest(event=event):
                self.optional_without_storage_reads(event, 'LOCATOR_INVALID')

    def test_invalid_task_index_is_not_an_optional_refresh_hint(self):
        self.remove_hints()
        for body in ('{', '[]', 'null', '{"task_ids":[]}'):
            self.locator.with_suffix('.tasks.json').write_text(body, encoding='utf-8')
            for event in ('SessionStart', 'UserPromptSubmit'):
                with self.subTest(body=body, event=event):
                    self.optional_without_storage_reads(event, 'ATTACHMENT_NOT_DISCOVERED')

    def test_missing_discovery_caches_do_not_bypass_completion(self):
        self.remove_hints()
        with patch.object(store, '_read_journal', wraps=store._read_journal) as replay:
            decision = host_hook.evaluate(self.project, 's1', 'TaskCompleted', 'task')
        self.assertEqual((decision['status'], decision['reason_code']), ('block', 'ACTIVE_ATTEMPT'))
        self.assertEqual(replay.call_count, 1)

    def test_external_index_including_empty_index_retains_authoritative_root(self):
        external = Path(self.fixture.temp.name).resolve() / 'external control'
        shutil.copytree(self.root, external)
        self.remove_hints()
        for tasks in (['task'], []):
            write_task_index(self.project, 'claude', 's1', external, tasks)
            for event, want in (('UserPromptSubmit', 'inactive'), ('TaskCompleted', 'block')):
                with self.subTest(tasks=tasks, event=event), patch.object(store, '_read_journal', wraps=store._read_journal) as replay:
                    result = host_hook.evaluate(self.project, 's1', event, 'task')
                self.assertEqual((result['status'], result['reason_code']), (want, 'LOCATOR_MISSING'))
                self.assertEqual(replay.call_count, 1)
                self.assertEqual(replay.call_args.args[0].resolve(), external)

    def test_stale_index_cannot_grant_detached_binding_completion(self):
        write_task_index(self.project, 'claude', 's1', self.root, ['task'])
        store.transact(self.root, 3, 'detach', {'kind': 'domain.host.detach', 'payload': {
            'request': {'binding_id': 'b1', 'revision': 1}}})
        result = host_hook.evaluate(self.project, 's1', 'TaskCompleted', 'task')
        self.assertEqual((result['status'], result['reason_code']), ('block', 'BINDING_DETACHED'))

    def test_sessions_do_not_share_negative_discovery(self):
        for event in ('SessionStart', 'UserPromptSubmit'):
            with self.subTest(event=event), patch.object(store, '_read_journal', wraps=store._read_journal) as replay:
                result = host_hook.evaluate(self.project, 'unattached-s2', event)
            self.assertEqual(result['status'], 'inactive')
            self.assertEqual(replay.call_count, 0)
        attached = host_hook.evaluate(self.project, 's1', 'SessionStart')
        self.assertEqual(attached['status'], 'allow')
        self.assertEqual(attached['brief']['binding_id'], 'b1')
        self.assertEqual(attached['brief']['active_attempt']['token'], 't')
        with patch.object(store, '_read_journal', wraps=store._read_journal) as replay:
            self.assertEqual(host_hook.evaluate(self.project, 'unattached-s2', 'UserPromptSubmit')['status'], 'inactive')
        self.assertEqual(replay.call_count, 0)

    def test_invalid_task_index_does_not_bypass_completion(self):
        self.remove_hints()
        for body in ('{', '[]', 'null', '{}'):
            self.locator.with_suffix('.tasks.json').write_text(body, encoding='utf-8')
            with self.subTest(body=body):
                result = host_hook.evaluate(self.project, 's1', 'TaskCompleted', 'task')
                self.assertEqual((result['status'], result['reason_code']), ('block', 'ACTIVE_ATTEMPT'))

    def test_attached_refresh_reuses_authoritative_state(self):
        original = host_hook.host_brief
        observed = []
        def capture(data, binding, **kwargs):
            view = original(data, binding, **kwargs)
            observed.append((data, kwargs.get('authoritative_state'), view))
            return view
        for event in ('SessionStart', 'UserPromptSubmit'):
            with self.subTest(event=event), patch.object(store, '_read_journal', wraps=store._read_journal) as replay, patch.object(host_hook, 'host_brief', side_effect=capture):
                decision = host_hook.evaluate(self.project, 's1', event)
                self.assertIn(decision['status'], ('allow', 'inactive'))
                self.assertEqual(replay.call_count, 1, 'attached refresh must not replay again inside context preparation')
                data, authoritative, view = observed[-1]
                self.assertIsNotNone(authoritative)
                self.assertIs(authoritative['data'], data)
                self.assertEqual(authoritative['version'], 3)
                self.assertGreaterEqual(authoritative['_context_read_ms'], 0)
                self.assertGreaterEqual(view['preparation']['preflight_ms'], authoritative['_context_read_ms'])
                self.assertIn('R1', view['task_view']['required_ids'])
                self.assertEqual(view['task_view']['coverage']['missing_ids'], [])
                self.assertEqual(view['active_attempt']['token'], 't')
        state = store.read_state(self.root)
        self.assertEqual(state['version'], 3)
        self.assertEqual(state['data']['runs']['run']['active_attempt']['token'], 't')

    def test_cached_brief_cannot_waive_revoked_binding_completion(self):
        write_task_index(self.project, 'claude', 's1', self.root, ['task'])
        self.assertEqual(host_hook.evaluate(self.project, 's1', 'SessionStart')['status'], 'allow')
        brief_path = self.locator.with_suffix('.brief.json')
        old_cache = brief_path.read_bytes()
        store.transact(self.root, 3, 'detach', {'kind': 'domain.host.detach', 'payload': {
            'request': {'binding_id': 'b1', 'revision': 1}}})
        result = host_hook.evaluate(self.project, 's1', 'TaskCompleted', 'task')
        self.assertEqual((result['status'], result['reason_code']), ('block', 'BINDING_DETACHED'))
        token = store.HOST_CONTEXT.set({'binding_id': 'b1', 'revision': 1})
        try:
            with self.assertRaises(store.WorkflowError) as caught:
                store.transact(self.root, 4, 'stale-write', {'kind': 'fixture', 'payload': {'forbidden': True}})
        finally:
            store.HOST_CONTEXT.reset(token)
        self.assertEqual(caught.exception.code, 'STALE_BINDING')
        self.assertEqual(brief_path.read_bytes(), old_cache)
        current = store.read_state(self.root)
        self.assertEqual(current['version'], 4)
        self.assertNotIn('forbidden', current['data'])
