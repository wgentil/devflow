import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path('/Users/wayne/.codex/worktrees/19ac/devflow')
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from run_platform_tests import run_suite
from workflow_lib import lifecycle_hooks

original = lifecycle_hooks.WORKER_PATH
output = ROOT / 'docs/releases/v0.3.17-evidence/controlled-startup-reproduction.json'
with tempfile.TemporaryDirectory(prefix='devflow-controlled-hook-startup-') as temporary:
    worker = Path(temporary) / 'slow-owned-worker.py'
    worker.write_text('import sys,time,runpy\n'
                      'time.sleep(5.5)\n'
                      'sys.path.insert(0,' + repr(str(original.parent)) + ')\n'
                      'runpy.run_path(' + repr(str(original)) + ',run_name="__main__")\n')
    with patch.object(lifecycle_hooks, 'WORKER_PATH', worker):
        report = run_suite(ROOT / 'tests', ['test_context_regressions.py', 'test_context_transport.py'], output)
expected_failure = 'test_context_regressions.ContextRegressionTests.test_offline_hook_shares_fixture_checks'
expected_error = 'test_context_transport.ContextTransportTests.test_input_artifact_removed_on_success_timeout_and_overflow'
assert report['tests_run'] == 5 and report['failures'] == [expected_failure] and report['errors'] == [expected_error]
assert 'HOOK_DEADLINE_EXCEEDED' in report['failure_traces'][0]['traceback']
assert 'Required context preparation failed' in report['error_traces'][0]['traceback']
print(json.dumps({'expected_negative_reproduction': True,
                  'cause': 'Owned worker startup delayed 5.5s against unchanged production 5s deadline',
                  'matching_failing_cases': report['failures'] + report['errors'],
                  'temporary_worker_removed': not worker.exists(),
                  'runtime_files_changed': False}))
