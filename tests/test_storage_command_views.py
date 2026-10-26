"""Real public commands must use selected records, preserving domain outcomes."""
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/workflow/scripts'
ENTRY = SCRIPTS / 'run.py'
sys.path.insert(0,str(SCRIPTS))
from workflow_lib import store, sqlite_store
from workflow_lib.storage_maintenance import compaction_plan, apply_compaction
from workflow_lib.run_archives import archive_run
from large_context_fixtures import make_context_project

class StorageCommandViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.base = Path(self.temp)
        fixture = make_context_project(self.base/'fixture',delivered_runs=3,history_bytes=30000,requirement_count=2)
        self.root, self.repo = fixture['root'], fixture['repo']
        plan = compaction_plan(self.root); apply_compaction(self.root,plan['plan_hash'])
        self.guard = self.base/'guard';self.guard.mkdir()
        (self.guard/'sitecustomize.py').write_text("""from workflow_lib import sqlite_store as sql
original=sql._decode
def forbidden_full(*args,**kwargs):raise AssertionError('EAGER_FULL_HISTORY_READ')
def selected(*args,**kwargs):
 value=original(*args,**kwargs)
 if isinstance(value,dict) and (value.get('_unrelated_storage_body') or value.get('synthetic_fixture') and 'review_packages' in value):
  raise AssertionError('UNRELATED_ARCHIVE_BODY_READ')
 return value
sql.read_state=forbidden_full
sql._decode=selected
""",encoding='utf-8')

    def backend(self):
        self.assertIsNotNone(importlib.util.find_spec('workflow_lib.storage_access'))
        return importlib.import_module('workflow_lib.storage_access')

    def environment(self, guarded=True):
        env = {**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
        if guarded:env['PYTHONPATH']=os.pathsep.join((str(self.guard),str(SCRIPTS)))
        return env

    def cli(self,*args,expected=0,guarded=True):
        result = subprocess.run([sys.executable,str(ENTRY),*map(str,args)],cwd=ROOT,
            env=self.environment(guarded),capture_output=True,text=True,encoding='utf-8',timeout=45)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        return json.loads(result.stdout)

    def request(self,name,value):
        path=self.base/name;path.write_text(json.dumps(value),encoding='utf-8');return path

    def test_public_command_family_contracts(self):
        self.backend()
        cases=[('context','resolve','--root',self.root),
            ('plan','ready','--root',self.root),
            ('run','status','--root',self.root,'--run-id','current'),
            ('build','test-change','list','--root',self.root,'--run-id','current'),
            ('issues','inspect','--root',self.root),('migrate','inspect','--root',self.root),
            ('stats','inspect','--root',self.root),('stats','routing','--root',self.root),
            ('improve','inspect','--root',self.root),('repair','status','--root',self.root,'--run-id','current')]
        for args in cases:
            with self.subTest(command=args[:2]):self.cli(*args)
        issue=self.request('issue.json',{'issue':{'id':'é東京','description':'original'}})
        first=self.cli('issues','capture','--root',self.root,'--input',issue,'--operation-id','issue')
        retry=self.cli('issues','capture','--root',self.root,'--input',issue,'--operation-id','issue')
        self.assertEqual(first['fingerprint'],retry['fingerprint']);self.assertTrue(retry['replayed'])
        metrics=self.cli('stats','metrics','--root',self.root,'--options','{"as_of":"2026-10-01T00:00:00Z"}', '--operation-id','metrics')
        self.assertEqual(metrics['report']['run_ids'],[])
        config=self.request('gate.json',{'run_id':'current','actor_id':'owner','gates':{'g':{
            'repo_id':'app','command':[sys.executable,'-c','print("ok")'],'contract':{'kind':'exit-status'}}}})
        self.cli('harden','configure','--root',self.root,'--input',config,'--operation-id','configure')
        profile=self.request('profile.json',{'extensions':['.json']})
        index=self.cli('ingest','--root',self.root,'--repo-id','app','--scope','docs/spec.json',
            '--profile-json',profile,'--operation-id','ingest')
        self.assertIn('index_id',index)
        self.cli('improve','trace-enable','--root',self.root,'--run-id','current','--actor-id','owner','--operation-id','trace')
        trace=self.cli('stats','trace','--root',self.root,'--options','{"run_id":"current"}')
        self.assertEqual(trace['usage_status'],'unknown')
        self.cli('run','discard','--root',self.root,'--run-id','current','--actor-id','owner','--reason','explicit fixture completion','--operation-id','discard')
        self.assertEqual(store.read_state(self.root)['data']['runs']['current']['status'],'discarded')

    def test_real_v2_build_review_acceptance_delivery_flow(self):
        self.backend()
        from test_verification_flow import VerificationFlowTests
        case=VerificationFlowTests('test_end_to_end_code_gate_review_acceptance_and_delivery_preparation')
        case.setUp();self.addCleanup(case.tearDown)
        sqlite_store.initialize_store(case.control)
        store.transact(case.control,0,'history',{'kind':'seed','payload':{'runs':{'unrelated':{
            'id':'unrelated','status':'delivered','active_attempt':None,'synthetic_fixture':True,
            'review_packages':{'offline':{'body':'historical payload'}}}}}})
        archive_run(case.control,'unrelated')
        with patch.dict(os.environ,{'PYTHONPATH':self.environment()['PYTHONPATH']}):
            case.test_end_to_end_code_gate_review_acceptance_and_delivery_preparation()

    def test_archived_retries_are_targeted(self):
        self.backend()
        # Seed a historical original auxiliary receipt with a stable operation ID.
        from commands.journal import commit
        from types import SimpleNamespace
        request={'issue':{'id':'old','description':'original é東京'}}
        args=SimpleNamespace(root=str(self.root),operation_id='old-capture',operation_id_explicit=True,expected_version=None)
        original=commit(args,'domain.issues.capture',request)
        plan=compaction_plan(self.root);apply_compaction(self.root,plan['plan_hash'])
        input_=self.request('old.json',request)
        retried=self.cli('issues','capture','--root',self.root,'--input',input_,'--operation-id','old-capture')
        self.assertEqual(retried['fingerprint'],original['fingerprint'])
        self.assertEqual(retried['event_sequence'],original['event_sequence'])
        self.assertTrue(retried['replayed'])
        self.assertEqual(retried['state_version'],store.read_state(self.root)['version'])

    def test_readonly_commands_do_not_preflight_mutate(self):
        self.backend()
        # The existing live preflight records drift. Read-only readiness and
        # delivery inspection must still reject drift without writing that record.
        (self.repo/'docs/spec.md').write_text('# changed outside approval\n')
        for args in [('plan','ready','--root',self.root),
                     ('delivery','prepare','--root',self.root,'--run-id','current',
                      '--repositories-json','{}','--outcome','retained-branch')]:
            with self.subTest(command=args[:2]):
                before=store.read_state(self.root)['version']
                result=subprocess.run([sys.executable,str(ENTRY),*map(str,args)],cwd=ROOT,
                    env=self.environment(False),capture_output=True,text=True,timeout=30)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(store.read_state(self.root)['version'],before)

    def test_missing_roots_and_runs_keep_existing_errors(self):
        self.backend()
        missing=self.base/'missing'
        self.cli('stats','inspect','--root',missing)
        # Existing best-effort measurement may create telemetry, never authority.
        self.assertFalse((missing/'format.json').exists())
        self.assertFalse((missing/'events').exists())
        self.assertFalse((missing/'state.json').exists())
        result=self.cli('run','status','--root',self.root,'--run-id','unknown',expected=2)
        self.assertEqual(result['error'],'RUN_NOT_FOUND')


    def test_stats_and_learning_match_legacy_across_archive(self):
        self.backend()
        from copy import deepcopy
        from workflow_lib.routing_evaluation import routing_statistics
        from workflow_lib.improvement_traces import project_run_trace
        from workflow_lib.journal_domains import digest
        fixture=make_context_project(self.base/'history-parity',delivered_runs=2,history_bytes=20000,requirement_count=1)
        root=fixture['root'];state=store.read_state(root)
        runs=deepcopy(state['data']['runs']);historical=runs['historical-0']
        historical.update(improvement_trace_enabled=True,acceptances=[{'complete':True,'requirements':[{'id':'R1','verdict':'MET'}]}],
            delivery={'recorded_at':'2026-09-01T00:00:00Z'})
        historical['native_invocations']={'i':{'status':'completed','operation_id':'op-native',
            'decision':{'routing':{'execution_path':'native','task_facts':{'task_id':'task'}}},
            'scope':{'stage':'implementation'},'result':{'usage':{'input_tokens':11,'output_tokens':3},
            'worker_outcome':{'status':'completed'}}}}
        store.transact(root,state['version'],'history-fields',{'kind':'seed','payload':{'runs':runs,
            'usage':{'events':[{'binding':{'run_id':'historical-0'},'input_tokens':11,'output_tokens':3,'cached_tokens':0,
                'source_id':'s','event_id':'e','provider':'p','model':'m'}],'gaps':[],'unbound':[]}}})
        old=store.read_state(root)
        expected_routing=routing_statistics(old['data'],{})
        expected_trace=project_run_trace(old,'historical-0',True)
        expected_trace={**expected_trace,'trace_hash':digest(expected_trace)}
        projected=deepcopy(old)
        store._apply_event(projected,{'kind':'domain.stats.metrics','payload':{'request':{'as_of':'2026-10-01T00:00:00Z'}},
            'sequence':old['version']+1,'operation_id':'report'})
        expected_report=projected['data']['domain_receipts']['report']['report']
        plan=compaction_plan(root);apply_compaction(root,plan['plan_hash'])
        self.assertEqual(self.cli('stats','routing','--root',root),expected_routing)
        self.assertEqual(self.cli('stats','trace','--root',root,'--options','{"run_id":"historical-0"}'),expected_trace)
        actual=self.cli('stats','metrics','--root',root,'--options','{"as_of":"2026-10-01T00:00:00Z"}','--operation-id','report')
        self.assertEqual(actual['report'],expected_report)


    def test_readonly_governing_resolution_never_records_preview(self):
        self.backend()
        from test_document_approvals import DocumentApprovalTests
        from workflow_lib.document_approvals import preflight_governing_inputs
        for layout in ('legacy','v2'):
            with self.subTest(layout=layout):
                case=DocumentApprovalTests();case.setUp();self.addCleanup(case.doCleanups)
                if layout=='v2':
                    plan=compaction_plan(case.root);apply_compaction(case.root,plan['plan_hash'])
                before=store.read_state(case.root)
                preview=preflight_governing_inputs(case.root,before,'inspection',record=False)
                self.assertTrue(preview['receipt']['files'])
                self.assertEqual(store.read_state(case.root),before)


    def test_issue_start_checks_existing_derived_run_identity(self):
        from copy import deepcopy
        from commands.journal import commit
        from types import SimpleNamespace
        args=SimpleNamespace(root=str(self.root),operation_id='snapshot',operation_id_explicit=True,expected_version=None)
        snapshot={'complete':True,'repo_id':'app','issues':[{'id':'issue'}]}
        result=commit(args,'domain.issues.snapshot',{'snapshot':snapshot})
        args.operation_id='group'
        commit(args,'domain.issues.group',{'snapshot_hash':result['snapshot_hash'],
            'groups':[{'id':'g','issue_ids':['issue'],'requirement_ids':{'issue':['R1']}}]})
        request={'snapshot_hash':result['snapshot_hash'],'group_id':'g','intent':'build'}
        before=store.read_state(self.root);preview=deepcopy(before)
        store._apply_event(preview,{'kind':'domain.issues.start','payload':{'request':request},
            'sequence':before['version']+1,'operation_id':'preview'})
        identifier=preview['data']['domain_receipts']['preview']['run_id']
        store.transact(self.root,before['version'],'collision',{'kind':'run.started','payload':{'run':{
            'id':identifier,'status':'active','active_attempt':None,'original_identity':'retain'}}})
        input_=self.request('start-issue.json',request)
        result=self.cli('issues','start','--root',self.root,'--input',input_,'--operation-id','start-issue',expected=2)
        self.assertEqual(result['error'],'RUN_ALREADY_EXISTS')
        self.assertEqual(store.read_state(self.root)['data']['runs'][identifier]['original_identity'],'retain')

    def test_feedback_uses_selected_attributed_usage(self):
        from copy import deepcopy
        state=store.read_state(self.root);runs=deepcopy(state['data']['runs'])
        runs['current']['improvement_trace_enabled']=True
        usage={'events':[{'binding':{'run_id':'current'},'source_id':'s','event_id':'e','provider':'p','model':'m',
            'input_tokens':11,'output_tokens':3,'cached_tokens':0}],'gaps':[],'unbound':[]}
        store.transact(self.root,state['version'],'usage-fixture',{'kind':'fixture','payload':{'runs':runs,'usage':usage}})
        trace=self.cli('stats','trace','--root',self.root,'--options','{"run_id":"current"}')
        self.assertEqual(trace['usage_status'],'reported')
        request={'run_id':'current','trace_hash':trace['trace_hash'],'actor_id':'reviewer',
            'feedback':{'owner':'helper','observation':'retain observed usage','command':[sys.executable,'-c','print(0)'],
                        'expected':{'exit_code':0},'scoring_version':1}}
        input_=self.request('feedback.json',request)
        response=self.cli('improve','feedback','--root',self.root,'--input',input_,'--operation-id','feedback')
        self.assertIn('feedback_id',response)


    def test_context_and_ingest_caches_keep_unloaded_entries(self):
        state=store.read_state(self.root)
        old={'_unrelated_storage_body':True,'body':'old cache body'*2000}
        store.transact(self.root,state['version'],'old-caches',{'kind':'fixture','payload':{
            'context_projections':{'unused':old},'ingestion_cache':{'unused':{**old,'text':'old source'}}}})
        first=self.cli('context','resolve','--root',self.root)
        second=self.cli('context','resolve','--root',self.root)
        self.assertFalse(first['projection_cache_hit']);self.assertTrue(second['projection_cache_hit'])
        profile=self.request('cached-profile.json',{'extensions':['.json']})
        for index in (1,2):
            result=self.cli('ingest','--root',self.root,'--repo-id','app','--scope','docs/spec.json',
                '--profile-json',profile,'--operation-id',f'cached-ingest-{index}')
            self.assertEqual(result['cache_hit'],index==2)
        data=store.read_state(self.root)['data']
        self.assertEqual(data['context_projections']['unused'],old)
        self.assertEqual(data['ingestion_cache']['unused']['body'],old['body'])

    def test_governing_approval_lookup_is_targeted(self):
        from test_document_approvals import DocumentApprovalTests
        from workflow_lib.document_approvals import propose_document_change,approve_document_change,preflight_governing_inputs
        from workflow_lib.storage_access import read_current
        case=DocumentApprovalTests();case.setUp();self.addCleanup(case.doCleanups)
        for index in range(10):
            state=store.read_state(case.root)
            store.transact(case.root,state['version'],f'old-proposal-{index}',{'kind':'document.proposed','payload':{'proposal':{
                'proposal_hash':f'old-{index}','repo_id':'p','diff_digest':f'd-{index}',
                '_unrelated_storage_body':True,'files':{f'old-{index}.md':{'diff':'old history'*2000}}}}})
        plan=compaction_plan(case.root);apply_compaction(case.root,plan['plan_hash'])
        case.write('rules.md','## A: Rule\nchanged\n')
        original=sqlite_store._decode
        def selected(*args,**kwargs):
            value=original(*args,**kwargs)
            if isinstance(value,dict):self.assertFalse(value.get('_unrelated_storage_body'),'Unrelated proposal body was hydrated')
            return value
        with patch.object(sqlite_store,'_decode',side_effect=selected):
            proposal=propose_document_change(case.root,'p',['rules.md'])
            approve_document_change(case.root,proposal['proposal_hash'],'owner')
            receipt=preflight_governing_inputs(case.root,read_current(case.root),'build')['receipt']
            self.assertTrue(receipt['effective_digest'])
        self.assertEqual(len(store.read_state(case.root)['data']['document_proposals']),11)
