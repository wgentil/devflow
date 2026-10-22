#!/usr/bin/env python3
"""Measure real run-next on disposable synthetic Git/journal projects only."""
import argparse
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from large_context_fixtures import make_context_project
from workflow_lib import store,context_preparation,lifecycle_hooks


def _entry():
    spec=importlib.util.spec_from_file_location('benchmark_run',ROOT/'skills/workflow/scripts/run.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def _next(entry,root):
    output=io.StringIO();started=time.perf_counter()
    with redirect_stdout(output):
        code=entry.main(['run','next','--root',str(root),'--run-id','current','--item','W1','--operation-id','benchmark-next'])
    elapsed=(time.perf_counter()-started)*1000
    result=json.loads(output.getvalue())
    if code:raise RuntimeError(f'Actual run next failed: {result}')
    return result,elapsed


def run_benchmark(*,events=4370,delivered_runs=40,history_bytes=79691776):
    if events<2 or delivered_runs<0 or history_bytes<0 or (history_bytes and not delivered_runs):
        raise ValueError('events >= 2; nonnegative runs/bytes; history bytes require historical runs')
    # No existing-root parameter: cleanup can only affect this owned temporary tree.
    with tempfile.TemporaryDirectory(prefix='devflow-context-benchmark-') as name:
        base=Path(name).resolve();fixture=make_context_project(base/'large',event_count=events,delivered_runs=delivered_runs,history_bytes=history_bytes)
        small=make_context_project(base/'small')
        worker_reads=base/'worker-reads';worker=base/'instrumented-hook.py'
        actual_worker=lifecycle_hooks.WORKER_PATH
        worker.write_text('import sys,runpy\nfrom pathlib import Path\nsys.path.insert(0,'+repr(str(actual_worker.parent))+')\n'
            'from workflow_lib import store\noriginal=store._read_journal\ndef counted(root):\n'
            '    with Path('+repr(str(worker_reads))+').open("a") as output:output.write("read\\n")\n'
            '    return original(root)\nstore._read_journal=counted\nrunpy.run_path('+repr(str(actual_worker))+',run_name="__main__")\n',encoding='utf-8')
        entry=_entry();counts={};phase=['initial'];original=store._read_journal;commit=context_preparation.commit_prepared_attempt;commits=[]
        def counted(root):
            counts[phase[0]]=counts.get(phase[0],0)+1
            return original(root)
        def measured_commit(*args,**kwargs):
            started=time.perf_counter()
            try:return commit(*args,**kwargs)
            finally:commits.append((time.perf_counter()-started)*1000)
        with patch.object(lifecycle_hooks,'WORKER_PATH',worker):
            small_view,_=_next(entry,small['root'])
            with patch.object(store,'_read_journal',side_effect=counted),patch.object(context_preparation,'commit_prepared_attempt',side_effect=measured_commit):
                started=time.perf_counter();store.read_state(fixture['root']);initial=(time.perf_counter()-started)*1000
                phase[0]='next';view,total=_next(entry,fixture['root'])
                phase[0]='exact_retry';retry,retry_ms=_next(entry,fixture['root'])
        final=store.read_state(fixture['root'])
        report={'fixture':fixture['statistics'],'environment':{'platform':platform.platform(),'python':platform.python_version()},
            'initial_replay_ms':initial,'preflight_ms':view['preparation']['preflight_ms'],'worker_ms':view['preparation']['worker_ms'],
            'total_ms':total,'commit_ms':sum(commits),'exact_retry_ms':retry_ms,
            'replay_counts':{**counts,'worker':len(worker_reads.read_text(encoding='utf-8').splitlines()) if worker_reads.exists() else 0},
            'selected_context_bytes':view['task_view']['content_bytes'],'small_selected_context_bytes':small_view['task_view']['content_bytes'],
            'component_bytes':view['budget']['component_bytes'],'token_issued':bool(view.get('attempt_id')),
            'exact_retry_same_token':bool(view.get('attempt_id')) and view.get('attempt_id')==retry.get('attempt_id'),
            'attempt_count':len(final['data']['runs']['current']['items']['W1']['attempts']),
            'selected_units_match_small':view['task_view']['units']==small_view['task_view']['units'],
            'limitations':['Synthetic delivered metadata and long review strings, not the reporter project or live verifier deliveries.',
                'total_ms measures actual CLI next including locked commit; preparation.total_ms covers fewer phases.',
                'Ordinary authoritative journal replay remains proportional to history; no paid host or native Windows validation.']}
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events',type=int,default=4370);parser.add_argument('--delivered-runs',type=int,default=40)
    parser.add_argument('--history-bytes',type=int,default=79691776);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.events<2 or args.delivered_runs<0 or args.history_bytes<0 or (args.history_bytes and not args.delivered_runs):
        parser.error('events >= 2; nonnegative runs/bytes; history bytes require historical runs')
    report=run_benchmark(events=args.events,delivered_runs=args.delivered_runs,history_bytes=args.history_bytes)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return 0


if __name__=='__main__':raise SystemExit(main())
