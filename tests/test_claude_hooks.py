import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from test_hosts import host_state, attachment
from workflow_lib.store import transact, read_state
from workflow_lib.host_locators import write_locator, locator_path
HOOK=Path(os.environ.get('DEVFLOW_HOOK_PATH', ROOT/'adapters/claude-code/hook.py'))

class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name).resolve()/'project with spaces';self.project.mkdir()
        subprocess.run(['git','init','-q',str(self.project)],check=True)
        self.root=self.project/'.devflow/control'
    def call(self,event='TaskCompleted',task='task',raw=None):
        payload={'hook_event_name':event,'session_id':'s1','cwd':str(self.project),'task_id':task,'task_subject':'ignored $(touch hacked)'}
        return subprocess.run([sys.executable,'-B',str(HOOK)],input=raw if raw is not None else json.dumps(payload),text=True,encoding='utf-8',capture_output=True,timeout=12)
    def attach(self):
        transact(self.root,0,'seed',{'kind':'fixture','payload':host_state(str(self.project))})
        transact(self.root,1,'attach',{'kind':'domain.host.attach','payload':{'request':attachment(str(self.project),host='claude')}})
        transact(self.root,2,'task',{'kind':'domain.host.task-bind','payload':{'request':{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'}}})
        write_locator(self.project,'claude','s1',self.root,'b1')
    def test_inactive_no_files_or_shell_effect(self):
        result=self.call();self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse((self.project/'.devflow').exists())
        self.assertFalse((self.project/'hacked').exists())
    def test_mapped_blocks_unmapped_unaffected_stop_nonblocking(self):
        self.attach();version=read_state(self.root)['version']
        blocked=self.call();self.assertEqual(blocked.returncode,2);self.assertIn('ACTIVE_ATTEMPT',blocked.stderr)
        self.assertEqual(self.call(task='ordinary').returncode,0)
        self.assertEqual(self.call(event='Stop').returncode,0)
        self.assertEqual(read_state(self.root)['version'],version)
    def test_brief_dedup_and_no_provider_effects(self):
        self.attach()
        first=self.call(event='SessionStart');self.assertEqual(first.returncode,0,first.stderr)
        self.assertIn('additionalContext',first.stdout)
        self.assertEqual(self.call(event='UserPromptSubmit').stdout,'')
        self.assertEqual(read_state(self.root)['version'],3)
    def test_session_start_rebuilds_even_when_fingerprint_unchanged(self):
        self.attach()
        self.assertIn('additionalContext', self.call(event='SessionStart').stdout)
        self.assertIn('additionalContext', self.call(event='SessionStart').stdout)

    def test_required_context_failure_is_visible_without_success_context(self):
        self.attach()
        state = read_state(self.root)
        transact(self.root, state['version'], 'missing-spec', {'kind': 'fixture', 'payload': {'spec': None}})
        result = self.call(event='UserPromptSubmit')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn('additionalContext', result.stdout)
        self.assertIn('SPEC_NOT_APPROVED', result.stderr)
    def test_corrupt_and_missing_locator_mapped_fail_closed(self):
        self.attach();path=locator_path(self.project,'claude','s1');path.write_text('{')
        self.assertEqual(self.call().returncode,2)
        self.assertEqual(self.call(task='ordinary').returncode,0)
        path.unlink();self.assertEqual(self.call().returncode,2)
    def test_malformed_and_oversized_bounded(self):
        self.assertEqual(self.call(raw='{').returncode,0)
        result=self.call(raw='x'*70000)
        self.assertLess(len(result.stderr),2000)
        self.assertFalse((self.project/'.devflow').exists())
    def test_oversized_known_completion_event_blocks(self):
        raw=json.dumps({'hook_event_name':'TaskCompleted','session_id':'s1','cwd':str(self.project),'task_id':'task','task_subject':'x'*70000})
        self.assertEqual(self.call(raw=raw).returncode,2)
    def test_oversized_known_prompt_event_blocks(self):
        raw = json.dumps({'hook_event_name': 'UserPromptSubmit', 'session_id': 's1',
                          'cwd': str(self.project), 'prompt': 'x' * 70000})
        self.assertEqual(self.call(raw=raw).returncode, 2)

    def test_binding_project_mismatch_blocks_only_mapped_task(self):
        self.attach();state=read_state(self.root)
        state['data']['host_bindings']['b1']['project_dir']='/tmp/other-project'
        transact(self.root,state['version'],'moved-fixture',{'kind':'fixture','payload':{'host_bindings':state['data']['host_bindings']}})
        result=self.call();self.assertEqual(result.returncode,2)
        self.assertIn('PROJECT_BINDING_MISMATCH',result.stderr)
        self.assertEqual(self.call(task='ordinary').returncode,0)

    def test_descriptor_launch_from_unicode_package_root(self):
        import shutil
        package = Path(self.temp.name) / 'installed plugin é東京'
        source = HOOK.resolve().parents[2]
        package.mkdir()
        for folder in ('skills', 'adapters', 'definitions', '.claude-plugin', '.codex-plugin'):
            if (source / folder).exists():
                shutil.copytree(source / folder, package / folder, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(source / 'plugin.json', package / 'plugin.json')
        descriptor = json.loads((package / 'adapters/claude-code/hooks.json').read_text(encoding='utf-8'))
        handler = descriptor['hooks']['TaskCompleted'][0]['hooks'][0]
        argv = [handler['command'], *[arg.replace('${CLAUDE_PLUGIN_ROOT}', str(package)) for arg in handler['args']]]
        result = subprocess.run(argv, input=json.dumps({'hook_event_name': 'TaskCompleted', 'cwd': str(self.project),
            'session_id': 'é東京', 'task_id': 'é東京'}).encode('utf-8'), capture_output=True, timeout=handler['timeout'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.project / '.devflow').exists())

    def test_hook_launcher_failure_blocks_mandatory_events(self):
        import contextlib
        import importlib.util
        import io
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('installed_hook_launch_failure', HOOK)
        hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hook)
        for event in ('UserPromptSubmit', 'TaskCompleted'):
            payload = {'hook_event_name': event, 'cwd': str(self.project), 'session_id': 's1', 'task_id': 'task'}
            stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode('utf-8')), encoding='utf-8')
            with self.subTest(event=event), patch.object(sys, 'stdin', stdin), patch.object(sys, 'executable', str(self.project / 'missing-python')), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(hook.main(), 2)


class AdapterTimeoutTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('devflow_timeout_adapter', HOOK)
        self.hook = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.hook)
        self.temp = tempfile.TemporaryDirectory(prefix='devflow-hook-timeout-')
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name).resolve()

    def invoke(self, event, child, *, stderr=None):
        import contextlib
        import io
        from unittest.mock import patch
        payload = {'hook_event_name': event, 'cwd': str(self.project), 'session_id': 'é東京', 'task_id': 'mapped'}
        stdin = io.TextIOWrapper(io.BytesIO(json.dumps(payload).encode('utf-8')), encoding='utf-8')
        out = io.StringIO()
        err = io.StringIO() if stderr is None else stderr
        def run(argv, **kwargs):
            self.assertEqual(kwargs.get('timeout'), 8)
            if isinstance(child, BaseException):
                raise child
            return child(argv, **kwargs) if callable(child) else child
        with patch.object(sys, 'stdin', stdin), patch.object(self.hook.subprocess, 'run', side_effect=run), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.hook.main()
        return code, out.getvalue(), err

    def test_helper_timeout_is_advisory_only_for_prompt_and_session_start(self):
        marker = 'SENSITIVE_PARTIAL_RESPONSE'
        for event, want in (('SessionStart', 0), ('UserPromptSubmit', 0), ('TaskCompleted', 2)):
            timeout = subprocess.TimeoutExpired(['helper é東京'], 8,
                output=json.dumps({'brief': {'note': marker}}).encode('utf-8'), stderr=b'\xffpartial diagnostic')
            with self.subTest(event=event):
                code, output, err = self.invoke(event, timeout)
                self.assertEqual(code, want)
                self.assertEqual(output, '', 'timeout cannot advertise successful or partial context')
                self.assertIn('timed out', err.getvalue().lower())
                self.assertNotIn(marker, err.getvalue())
                self.assertLess(len(err.getvalue().encode('utf-8')), 2000)
                if event == 'UserPromptSubmit':
                    self.assertIn('context', err.getvalue().lower())
                    self.assertIn('attach', err.getvalue().lower())

    def test_timeout_warning_failure_does_not_change_event_exit_policy(self):
        import io
        class BrokenStream(io.StringIO):
            def write(self, value):
                raise OSError('closed diagnostic sink')
        for event, want in (('UserPromptSubmit', 0), ('TaskCompleted', 2)):
            with self.subTest(event=event):
                code, output, _ = self.invoke(event, subprocess.TimeoutExpired(['helper'], 8), stderr=BrokenStream())
                self.assertEqual((code, output), (want, ''))

    def test_non_timeout_failures_and_explicit_blocks_still_block(self):
        cases = {
            'policy': subprocess.CompletedProcess(['helper'], 0, b'{"status":"block","reason_code":"SPEC_NOT_APPROVED","message":"Required context missing"}', b''),
            'error': subprocess.CompletedProcess(['helper'], 2, b'{"error":"CORRUPT_STATE","message":"Invalid journal"}', b''),
            'json': subprocess.CompletedProcess(['helper'], 0, b'not JSON', b''),
            'launcher': OSError('helper unavailable'),
        }
        for event in ('UserPromptSubmit', 'TaskCompleted'):
            for label, result in cases.items():
                with self.subTest(event=event, failure=label):
                    code, output, err = self.invoke(event, result)
                    self.assertEqual((code, output), (2, ''))
                    self.assertTrue(err.getvalue())

    def test_real_stalled_helper_preserves_prompt_and_completion_policy(self):
        from unittest.mock import patch
        helper_root = self.project / 'helper é東京'
        helper = helper_root / 'skills/workflow/scripts/run.py'
        helper.parent.mkdir(parents=True)
        helper.write_text("import time\nprint('{\"brief\":',flush=True)\ntime.sleep(30)\n", encoding='utf-8')
        real_run = subprocess.run
        timeouts = []
        def short_fixture_wait(argv, **kwargs):
            # Production still passes 8; shorten only this owned stalling child.
            self.assertEqual(kwargs['timeout'], 8)
            kwargs['timeout'] = 0.15
            try:
                return real_run(argv, **kwargs)
            except subprocess.TimeoutExpired as exc:
                timeouts.append(exc)
                raise
        for event, want in (('UserPromptSubmit', 0), ('TaskCompleted', 2)):
            before = len(timeouts)
            with self.subTest(event=event), patch.object(self.hook, 'ROOT', helper_root):
                code, output, err = self.invoke(event, short_fixture_wait)
                self.assertEqual(len(timeouts), before + 1, 'the real helper must time out, not fail to launch/parse')
                self.assertEqual((code, output), (want, ''))
                self.assertIn('timed out', err.getvalue().lower())

    def test_prompt_timeout_diagnostic_uses_utf8_with_legacy_stderr(self):
        import io
        stderr = io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
        code, output, _ = self.invoke('UserPromptSubmit', subprocess.TimeoutExpired(['helper é東京'], 8), stderr=stderr)
        self.assertEqual((code, output), (0, ''))
        self.assertIn('timed out', stderr.buffer.getvalue().decode('utf-8').lower())
