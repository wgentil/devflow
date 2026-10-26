#!/usr/bin/env python3
"""Measure actual commands on disposable synthetic storage; never accept a live root."""
from __future__ import annotations
import argparse
from contextlib import contextmanager,redirect_stdout,ExitStack
import importlib.util
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from large_context_fixtures import make_context_project
from workflow_lib import store,sqlite_store as sql,storage_objects
from workflow_lib.stored_records import digest,canonical
from workflow_lib.storage_maintenance import compaction_plan,apply_compaction,verify_store
from workflow_lib.storage_format import DATABASE_FILE


def _fixture(base,terminal_runs,review_bytes=0):
    fixture=make_context_project(base,delivered_runs=terminal_runs,requirement_count=2)
    root=fixture['root'];state=store.read_state(root);data=state['data']
    for index,(identifier,run) in enumerate(data['runs'].items()):
        if identifier=='current':continue
        size=review_bytes//terminal_runs+(index<review_bytes%terminal_runs)
        package={'schema_version':1,'run_id':identifier,'role':'branch',
            'repositories':{'app':{'worktree_diff':('review-'+str(index)+'\n')+('R'*size)}},
            'synthetic_fixture':True}
        package['package_hash']=digest(package)
        run['review_packages']={package['package_hash']:package}
    from test_hosts import attachment
    from workflow_lib.hosts import apply_host_event
    apply_host_event(data,'attach',attachment(str(fixture['repo']),run_id='current',host='claude'))
    store.transact(root,state['version'],'benchmark-body-fixture',{'kind':'fixture','payload':data})
    return fixture


def _physical(root):
    totals={key:0 for key in ('database_bytes','objects_bytes','cache_bytes','backup_bytes','other_bytes','total_bytes')}
    for path in root.rglob('*'):
        if not path.is_file():continue
        relative=path.relative_to(root).parts;size=path.stat().st_size
        key='database_bytes' if relative[0]=='store-v2' else 'objects_bytes' if relative[0]=='objects' else 'cache_bytes' if relative[0] in {'context-artifacts','context-checkpoints','context-telemetry'} else 'backup_bytes' if relative[0]=='backups' else 'other_bytes'
        totals[key]+=size;totals['total_bytes']+=size
    with sql.connection(root) as conn:
        try:
            totals['catalog_btree_bytes']=conn.execute("SELECT coalesce(sum(pgsize),0) FROM dbstat WHERE name NOT IN ('entities','events','run_views')").fetchone()[0]
            totals['catalog_btree_measurement']='SQLite dbstat, includes schema/index/metadata pages; overlaps database_bytes'
        except sql._sqlite().OperationalError:
            totals['catalog_btree_bytes']=None;totals['catalog_btree_measurement']='dbstat unavailable; not estimated'
    return totals


def _probe(root,arguments):
    spec=importlib.util.spec_from_file_location('storage_benchmark_entry',ROOT/'skills/workflow/scripts/run.py')
    entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
    samples=[]
    for temperature in ('cold','warm'):
        counters={'queries':0,'sqlite_vm_steps':0,'terminal_body_reads':0,'historical_package_reads':0,
            'old_segment_reads':0,'object_file_reads':0,'object_physical_bytes':0,'object_logical_bytes':0,
            'sqlite_scope_ms':0.0,'object_read_ms':0.0}
        original_connection=sql._connection;original_decode=sql._decode;original_read=storage_objects.read_object
        original_file=storage_objects._read_file
        @contextmanager
        def connection(*args,**kwargs):
            started=time.perf_counter()
            with original_connection(*args,**kwargs) as conn:
                def query(_):counters['queries']+=1
                def step():counters['sqlite_vm_steps']+=1;return 0
                conn.set_trace_callback(query);conn.set_progress_handler(step,1)
                try:yield conn
                finally:conn.set_trace_callback(None);conn.set_progress_handler(None,0)
            counters['sqlite_scope_ms']+=(time.perf_counter()-started)*1000
        def decode(root,codec,*args,**kwargs):
            if codec in {'archive','archive2'}:counters['terminal_body_reads']+=1
            if codec=='event-archive':counters['old_segment_reads']+=1
            return original_decode(root,codec,*args,**kwargs)
        def read(root,reference,*args,**kwargs):
            if reference.get('kind')=='review-package':counters['historical_package_reads']+=1
            started=time.perf_counter();value=original_read(root,reference,*args,**kwargs)
            counters['object_read_ms']+=(time.perf_counter()-started)*1000
            counters['object_logical_bytes']+=len(value)
            return value
        def read_file(*args,**kwargs):
            value=original_file(*args,**kwargs)
            counters['object_file_reads']+=1;counters['object_physical_bytes']+=len(value)
            return value
        with ExitStack() as patches:
            # Existing aliases and future imports observe the same instrumentation.
            for module in list(sys.modules.values()):
                if module is not None and getattr(module,'__name__','').startswith('workflow_lib'):
                    for name,value in list(vars(module).items()):
                        if value is original_read:patches.enter_context(patch.object(module,name,read))
            patches.enter_context(patch.object(sql,'_connection',connection))
            patches.enter_context(patch.object(sql,'_decode',decode))
            patches.enter_context(patch.object(storage_objects,'_read_file',read_file))
            output=io.StringIO();started=time.perf_counter()
            with redirect_stdout(output):code=entry.main(arguments)
            elapsed=(time.perf_counter()-started)*1000
        value=json.loads(output.getvalue())
        if code:raise RuntimeError('Actual command failed: '+output.getvalue())
        samples.append({'command':' '.join(arguments[:2]),'temperature':temperature,'elapsed_ms':elapsed,
            'result_status':value.get('status',value.get('stage')),'attempt_id':value.get('attempt_id'),**counters})
    return samples


def _command(root,arguments):
    started=time.perf_counter()
    code="import json,runpy,sys;from pathlib import Path;m=runpy.run_path(sys.argv[1]);print(json.dumps(m['_probe'](Path(sys.argv[2]),json.loads(sys.argv[3]))))"
    result=subprocess.run([sys.executable,'-B','-c',code,str(Path(__file__).resolve()),str(root),json.dumps(arguments)],capture_output=True,encoding='utf-8',timeout=180)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    samples=json.loads(result.stdout)
    for sample in samples:sample['subprocess_total_ms']=(time.perf_counter()-started)*1000
    return samples


def run_scale_benchmark(*,counts=(10,1000)):
    profiles=[];owned=[]
    with tempfile.TemporaryDirectory(prefix='devflow-control-scale-') as temporary:
        for count in counts:
            if count<1:raise ValueError('positive terminal run counts required')
            fixture=_fixture(Path(temporary)/str(count),count);root=fixture['root'];owned.append(root)
            before_total=sum(path.stat().st_size for path in root.rglob('*') if path.is_file())
            started=time.perf_counter();plan=compaction_plan(root);receipt=apply_compaction(root,plan['plan_hash'])
            compaction_ms=(time.perf_counter()-started)*1000
            state=store.read_state(root)
            store.transact(root,state['version'],'benchmark-tail',{'kind':'fixture','payload':{'benchmark_tail':1}})
            arguments=[['run','status','--root',str(root),'--run-id','current'],
                ['context','resolve','--root',str(root)],
                ['host','brief','--root',str(root),'--binding-id','b1','--revision','1'],
                ['run','next','--root',str(root),'--run-id','current','--item','W1','--operation-id','benchmark-next']]
            commands=[]
            for argv in arguments:commands.extend(_command(root,argv))
            # Map the actual issued attempt; completion must consult current authority.
            from workflow_lib.storage_access import read_current
            state=read_current(root,run_id='current');token=state['data']['runs']['current']['active_attempt']['token']
            store.transact(root,state['version'],'benchmark-map',{'kind':'domain.host.task-bind','payload':{'request':{
                'binding_id':'b1','revision':1,'task_id':'benchmark-task','scope':'item','item_id':'W1','token':token}}})
            commands.extend(_command(root,['host','check','--root',str(root),'--binding-id','b1','--task-id','benchmark-task']))
            physical=_physical(root)
            profiles.append({'terminal_runs':count,'commands':commands,'compaction_ms':compaction_ms,
                'full_audit_valid':verify_store(root,full=True)['valid'],'physical':physical,
                'before_total_bytes':before_total,'net_physical_change_bytes':physical['total_bytes']-before_total,
                'actual_reclaimed_bytes':max(0,before_total-physical['total_bytes'])})
    return {'schema_version':1,'provenance':'owned synthetic real-Git projects; full terminal runs and hash-bound review packages',
        'profiles':profiles,'owned_roots_removed':all(not root.exists() for root in owned),
        'platform':platform.platform(),'python':sys.version}


def run_review_corpus_benchmark(*,review_bytes=100*1024*1024):
    if review_bytes<0:raise ValueError('nonnegative review bytes required')
    with tempfile.TemporaryDirectory(prefix='devflow-review-corpus-') as temporary:
        fixture=_fixture(Path(temporary)/'fixture',10,review_bytes);root=fixture['root']
        before=store.read_state(root);logical_before=digest(before)
        legacy_payload_bytes=(root/'state.json').stat().st_size
        closed_bytes=sum(len(canonical(package)) for identifier,run in before['data']['runs'].items() if identifier!='current'
            for package in run.get('review_packages',{}).values())
        del before
        before_total=sum(path.stat().st_size for path in root.rglob('*') if path.is_file())
        started=time.perf_counter();plan=compaction_plan(root);receipt=apply_compaction(root,plan['plan_hash'])
        compaction_ms=(time.perf_counter()-started)*1000
        after=store.read_state(root);parity=digest(after)==logical_before;del after
        hot=0;archived_logical=0
        with sql.connection(root) as conn:
            for space,key,codec,payload,checksum in conn.execute('SELECT space,key,codec,payload,value_hash FROM entities'):
                if codec in {'archive','archive2'}:
                    archived_logical+=len(canonical(sql._decode(root,codec,payload,checksum)));continue
                if codec=='space':continue
                hot+=len(canonical(sql._decode(root,codec,payload,checksum)))
            for codec,payload,checksum in conn.execute('SELECT codec,payload,event_hash FROM events'):
                if codec!='event-archive':hot+=len(canonical(sql._decode(root,codec,payload,checksum)))
        physical=_physical(root)
        report={'schema_version':1,'provenance':'owned generated complete review packages; repeated ASCII diff bytes, gzip deduplication; not Bandpick production data',
            'closed_review_logical_bytes':closed_bytes,'legacy_payload_bytes':legacy_payload_bytes,
            'hot_logical_payload_bytes':hot,'archived_run_logical_bytes':archived_logical,'hot_payload_ratio':hot/legacy_payload_bytes,
            'physical':physical,'compaction_ms':compaction_ms,'full_audit_valid':verify_store(root,full=True)['valid'],
            'logical_parity':parity,'before_total_bytes':before_total,
            'net_physical_change_bytes':physical['total_bytes']-before_total,
            'actual_reclaimed_bytes':max(0,before_total-physical['total_bytes']),
            'reclamation_measurement':'net root file bytes with verified backups retained; not filesystem allocated blocks or GC unlink totals'}
    report['owned_roots_removed']=not root.exists()
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--review-bytes',type=int,default=100*1024*1024)
    parser.add_argument('--counts',type=int,nargs='+',default=[10,1000])
    args=parser.parse_args()
    report={'scale':run_scale_benchmark(counts=args.counts),'review_corpus':run_review_corpus_benchmark(review_bytes=args.review_bytes)}
    text=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    else:print(text,end='')

if __name__=='__main__':main()
