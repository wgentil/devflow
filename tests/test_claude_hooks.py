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
