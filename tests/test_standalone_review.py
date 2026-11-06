"""Public standalone selection uses owned Git repositories, no workflow or paid model."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class StandaloneReviewTests(unittest.TestCase):
    def fixture(self):
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir()
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):self.git(repo,*args)
        (repo/'value.py').write_text('value = 60\n');(repo/'AGENTS.md').write_text('Use the supplied retention rule.\n')
        self.git(repo,'add','.');self.git(repo,'commit','-qm','baseline');first=self.git(repo,'rev-parse','HEAD').strip()
        (repo/'value.py').write_text('value = 30\n');self.git(repo,'commit','-qam','correction');second=self.git(repo,'rev-parse','HEAD').strip()
        return base,repo,first,second
    def git(self,repo,*args):return subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True,text=True).stdout
    def cli(self,*args,request=None,expected=0):
        argv=[sys.executable,str(ROOT/'skills/workflow/scripts/run.py'),'review',*map(str,args)]
        if request is not None:
            source=Path(self.enterContext(tempfile.TemporaryDirectory()))/'request.json';source.write_text(json.dumps(request));argv+=['--input',str(source)]
        result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        return json.loads(result.stdout)
    def start(self,repo,path,request):return self.cli('start','--repository',repo,'--session',path,request=request)
    def subject(self,path):
        from workflow_lib.review_sessions import read_session
        return read_session(path)['subject']
    def test_working_tree_review_initializes_no_workflow(self):
        base,repo,first,head=self.fixture();config=(repo/'.git/config').read_bytes()
        (repo/'staged').write_text('staged');self.git(repo,'add','staged');(repo/'value.py').write_text('value = 45\n');(repo/'loose').write_text('untracked')
        status=self.git(repo,'status','--porcelain');path=base/'review/session.db'
        self.start(repo,path,{'mode':'working-tree'})
        subject=self.subject(path);selection=subject['standalone_scope']
        self.assertEqual(selection['head_sha'],head);self.assertTrue(selection['index_hash'])
        self.assertEqual(selection['files']['value.py']['sha256'],__import__('hashlib').sha256((repo/'value.py').read_bytes()).hexdigest())
        self.assertIn('staged',selection['files']);self.assertIn('loose',selection['files'])
        self.assertEqual((repo/'.git/config').read_bytes(),config);self.assertEqual(self.git(repo,'status','--porcelain'),status)
        self.assertFalse((repo/'.devflow').exists());self.assertTrue(all(k not in subject for k in ('plan','spec','runs')))
        self.assertIn('AGENTS.md',subject['governing_evidence']);self.assertTrue(subject['limitations'])
        report=self.cli('report','--session',path);self.assertEqual(report['outcome'],'blocked');self.assertFalse(report['workflow_acceptance'])
    def test_committed_range_excludes_dirty_untracked_changes(self):
        base,repo,first,head=self.fixture();(repo/'value.py').write_text('dirty = True');(repo/'loose').write_text('untracked')
        path=base/'review/session.db';self.start(repo,path,{'mode':'committed-range','base':first,'head':head})
        scope=self.subject(path)['standalone_scope'];self.assertEqual(scope['base_sha'],first);self.assertEqual(scope['head_sha'],head)
        self.assertNotIn('loose',scope['files']);self.assertNotIn('loose',scope['changed_paths'])
        snapshot=Path(self.subject(path)['repositories']['repo-1']['location'])
        self.assertEqual((snapshot/'value.py').read_text(),'value = 30\n');self.assertEqual((repo/'value.py').read_text(),'dirty = True')
        self.cli('status','--session',path)
    def test_session_artifacts_cannot_be_review_inputs(self):
        base,repo,first,head=self.fixture()
        from workflow_lib.standalone_reviews import start_standalone
        with self.assertRaises(WorkflowError):start_standalone(repo,{'mode':'working-tree'},repo/'review.db')
        self.assertFalse((repo/'review.db').exists())
        with self.assertRaises(WorkflowError):start_standalone(repo,{'mode':'committed-range','head':head},base/'missing.db')
    def test_report_only_never_dispatches_a_writer(self):
        base,repo,first,head=self.fixture();path=base/'review/session.db';self.start(repo,path,{'mode':'working-tree'})
        before=self.git(repo,'status','--porcelain')
        result=self.cli('next','--session',path)
        self.assertEqual(result['kind'],'review');self.assertFalse(result['executed'])
        result=self.cli('next','--session',path,'--execute','--operation-id','missing-route',request={'perspective':'security','host':'codex','actor_id':'independent','estimated_cost':1})
        self.assertEqual(result['status'],'block');self.assertEqual(result['reason_code'],'NO_VALIDATED_PERMITTED_MODEL')
        self.assertEqual(self.git(repo,'status','--porcelain'),before)
        self.assertFalse(self.subject(path).get('effects'));self.assertFalse(self.subject(path).get('repair_authorization'))
    def test_source_replacement_and_conflicting_start_are_rejected(self):
        base,repo,first,head=self.fixture();path=base/'review/session.db';request={'mode':'working-tree'}
        self.start(repo,path,request);self.start(repo,path,request)
        (repo/'value.py').write_text('replacement')
        status=self.cli('status','--session',path);self.assertFalse(status['source_current'])
        from workflow_lib.standalone_reviews import start_standalone
        with self.assertRaises(WorkflowError):start_standalone(repo,request,path)
        with self.assertRaises(WorkflowError):start_standalone(repo,{'mode':'committed-range','base':first,'head':head},path)

    def model_fixture(self):
        from workflow_lib.review_sessions import read_session,transact_session
        base,repo,first,head=self.fixture();path=base/'review/session.db';self.start(repo,path,{'mode':'working-tree'})
        state=read_session(path)
        transact_session(path,state['version'],'budget',{'action':'configure-effects','record':{
            'max_attempts':4,'max_estimated_cost':4,'max_elapsed_ms':30000,'authorization':{'approved':True,'actor_id':'fixture-user'}}})
        return base,repo,path
    def test_session_model_crash_requires_observed_recovery(self):
        from unittest.mock import patch
        from test_review_dispatch import ReviewDispatchTests
        from workflow_lib.review_dispatch import dispatch_session_review
        from workflow_lib.review_sessions import read_session
        from workflow_lib.native_models import NativeError
        base,repo,path=self.model_fixture();fixture=ReviewDispatchTests()
        class Crash:
            def __init__(self,*args):pass
            def configure(self,resolved,brief,access='read-only'):return {'observed':resolved,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configured'}
            def discover(self):return {'capabilities':fixture.capabilities(),'discovery':fixture.discovery()}
            def invoke(self,*args):
                result=subprocess.run([sys.executable,'-c',"from pathlib import Path; p=Path('"+str(base/'counter')+"'); p.write_text(p.read_text()+'x' if p.exists() else 'x'); raise SystemExit(23)"],capture_output=True)
                if result.returncode:raise NativeError('unavailable','Owned child exited before a model completion receipt.')
            def close(self):pass
        request={'perspective':'security','host':'codex','actor_id':'fixture-reviewer','estimated_cost':1,'diagnostic':True}
        with patch('workflow_lib.native_runtime.policy',return_value=fixture.policy()),patch('workflow_lib.session_models.CodexBackend',Crash):
            result=dispatch_session_review(path,request,'crash')
            self.assertEqual(result['status'],'block')
            retry=dispatch_session_review(path,request,'crash');self.assertTrue(retry['replayed'])
            self.assertEqual((base/'counter').read_text(),'x')
            with self.assertRaises(WorkflowError):dispatch_session_review(path,request,'replacement')
        subject=read_session(path)['subject'];self.assertEqual(subject['effects']['crash']['status'],'uncertain')
        self.assertEqual(len(subject['model_receipts']),1)
    def test_generic_event_cannot_manufacture_session_model_output(self):
        from workflow_lib.review_sessions import read_session,transact_session
        base,repo,path=self.model_fixture();state=read_session(path)
        with self.assertRaises(WorkflowError):transact_session(path,state['version'],'forged',{'action':'session-model-finish',
            'record':{'invocation_id':'invented','result':{'status':'completed','invocation_ref':'claimed','output':'{}'}}})

    def test_snapshot_never_executes_project_git_filters(self):
        import os
        from unittest.mock import patch
        from workflow_lib.standalone_reviews import start_standalone
        base,repo,first,head=self.fixture();marker=base/'filter-ran';script=base/'filter.py'
        script.write_text('import sys\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text("ran")\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n')
        config=base/'global.gitconfig';config.write_text('[filter "fixture"]\n clean = '+sys.executable+' '+str(script)+'\n')
        (repo/'.gitattributes').write_text('value.py filter=fixture\n')
        with patch.dict(os.environ,{'GIT_CONFIG_GLOBAL':str(config)}):start_standalone(repo,{'mode':'working-tree'},base/'session.db')
        self.assertFalse(marker.exists(),'Starting read-only review executed a project filter.')
    def test_actual_native_report_is_ingested_once_and_retries_without_dispatch(self):
        from unittest.mock import patch
        from test_review_dispatch import ReviewDispatchTests
        from workflow_lib.review_dispatch import dispatch_session_review
        from workflow_lib.review_sessions import read_session
        from workflow_lib.standalone_reviews import standalone_status
        base,repo,path=self.model_fixture();fixture=ReviewDispatchTests();counter=base/'counter'
        class Transport:
            def __init__(self,*args):pass
            def configure(self,resolved,brief,access='read-only'):return {'observed':resolved,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configured'}
            def discover(self):return {'capabilities':fixture.capabilities(),'discovery':fixture.discovery()}
            def invoke(self,resolved,prompt,actor,access,timeout):
                assert access=='read-only'
                script='from pathlib import Path; p=Path('+repr(str(counter))+'); p.write_text(p.read_text()+"x" if p.exists() else "x"); print(\'{"verdict":"block","findings":[],"diagnostic":true}\')'
                result=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True,check=True)
                return {'status':'completed','observed':resolved,'invocation_ref':'fixture:actual-child','observation_source':'host-invocation-metadata','output':result.stdout}
            def close(self):pass
        request={'perspective':'security','host':'codex','actor_id':'fixture-reviewer','estimated_cost':1,'diagnostic':True}
        with patch('workflow_lib.native_runtime.policy',return_value=fixture.policy()),patch('workflow_lib.session_models.CodexBackend',Transport):
            first=dispatch_session_review(path,request,'review')
            self.assertEqual(first['status'],'allow')
            self.assertEqual(first['report_status'],'recorded')
        # A changed route does not erase an immutable invocation/retry receipt.
        again=dispatch_session_review(path,request,'review');self.assertTrue(again['replayed'])
        self.assertEqual(again['report_status'],'recorded');self.assertEqual(counter.read_text(),'x')
        subject=read_session(path)['subject'];self.assertEqual(len(subject['reviews']['session']),1)
        self.assertEqual(subject['effects']['review']['status'],'completed')
        self.assertEqual(standalone_status(path)['outcome'],'blocked')

    def test_real_stopped_coordinator_needs_exact_worker_attestation(self):
        from workflow_lib.review_sessions import read_session
        from workflow_lib.review_dispatch import dispatch_session_review
        from workflow_lib.enforcement_recovery import reconcile_session_model
        from unittest.mock import patch
        from test_review_dispatch import ReviewDispatchTests
        base,repo,path=self.model_fixture();script=base/'coordinator.py';marker=base/'launched'
        script.write_text('''import sys,os
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[PATH_SCRIPTS,PATH_TESTS]
from test_review_dispatch import ReviewDispatchTests
from workflow_lib.review_dispatch import dispatch_session_review
fixture=ReviewDispatchTests()
class Stop:
 def __init__(self,*args):pass
 def configure(self,resolved,brief,access='read-only'):return {'observed':resolved,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configured'}
 def discover(self):return {'capabilities':fixture.capabilities(),'discovery':fixture.discovery()}
 def invoke(self,*args):
  Path(MARKER).write_text('one')
  os._exit(23)
 def close(self):pass
with patch('workflow_lib.native_runtime.policy',return_value=fixture.policy()),patch('workflow_lib.session_models.CodexBackend',Stop):
 dispatch_session_review(Path(SESSION),{'perspective':'security','host':'codex','actor_id':'fixture-reviewer','estimated_cost':1,'diagnostic':True},'interrupted')
'''.replace('PATH_SCRIPTS',repr(str(ROOT/'skills/workflow/scripts'))).replace('PATH_TESTS',repr(str(ROOT/'tests'))).replace('MARKER',repr(str(marker))).replace('SESSION',repr(str(path))))
        result=subprocess.run([sys.executable,str(script)],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,23,result.stdout+result.stderr);self.assertEqual(marker.read_text(),'one')
        with self.assertRaises(WorkflowError):reconcile_session_model(path,'interrupted',{},'bad-recovery')
        confirmation={'approved':True,'actor_id':'fixture-user','worker_ref':'interrupted','reason':'Owned coordinator and all children stopped.',
            'provenance':{'kind':'user-message','ref':'fixture:stop-message'}}
        reconcile_session_model(path,'interrupted',confirmation,'recovery')
        self.assertEqual(read_session(path)['subject']['effects']['interrupted']['status'],'reconciled')
        retry=reconcile_session_model(path,'interrupted',confirmation,'recovery');self.assertTrue(retry['replayed'])
        self.assertEqual(marker.read_text(),'one')
    def test_snapshot_tampering_blocks_before_actual_model_effect(self):
        from unittest.mock import patch
        from test_review_dispatch import ReviewDispatchTests
        from workflow_lib.review_dispatch import dispatch_session_review
        from workflow_lib.standalone_reviews import standalone_status
        base,repo,path=self.model_fixture();subject=self.subject(path)
        (Path(subject['repositories']['repo-1']['location'])/'value.py').write_text('tampered')
        self.assertFalse(standalone_status(path)['source_current'])
        with patch('workflow_lib.native_runtime.policy',return_value=ReviewDispatchTests().policy()),patch('workflow_lib.session_models.CodexBackend') as backend:
            with self.assertRaises(WorkflowError):dispatch_session_review(path,{'perspective':'security','host':'codex','actor_id':'fixture-reviewer','estimated_cost':1,'diagnostic':True},'tampered')
        backend.assert_not_called()

    def test_selected_package_delivers_actual_range_and_governing_evidence(self):
        from workflow_lib.standalone_reviews import start_standalone
        from workflow_lib.session_evidence import prepare
        base,repo,first,head=self.fixture();path=base/'review/session.db'
        start_standalone(repo,{'mode':'committed-range','base':first,'head':head},path)
        package=prepare(path,'package')
        self.assertIn('-value = 60',package['standalone_scope']['diff'])
        self.assertIn('+value = 30',package['standalone_scope']['diff'])
        location=Path(package['repositories']['repo-1']['location'])
        self.assertEqual((location/'value.py').read_text(),'value = 30\n')
        self.assertIn('AGENTS.md',package['governing_evidence'])

    def test_positive_lightweight_review_can_pass_without_workflow_acceptance(self):
        from unittest.mock import patch
        from workflow_lib.review_sessions import read_session,transact_session
        from workflow_lib.review_policy import review_bindings,PERSPECTIVES
        from workflow_lib.review_dispatch import dispatch_session_review
        from workflow_lib.standalone_reviews import start_standalone,standalone_status
        from workflow_lib.adversarial_reviews import review_input_id
        from test_review_dispatch import ReviewDispatchTests
        base,repo,first,head=self.fixture();self.git(repo,'rm','value.py');(repo/'README').write_text('Teh guide\n')
        self.git(repo,'add','README');self.git(repo,'commit','-qm','prose baseline');(repo/'README').write_text('The guide\n')
        path=base/'review/session.db';start_standalone(repo,{'mode':'working-tree','intent':[{'id':'spelling','text':'Correct spelling only; preserve meaning.'}]},path)
        def event(op,action,record):
            state=read_session(path);return transact_session(path,state['version'],op,{'action':action,'record':record})
        subject=self.subject(path);authority='intent:'+subject['review_contract_hash']+'#spelling'
        event('contract','implementation-contract',{'scope':{'role':'session'},'source_identity':subject['source_identity'],
            'behaviors':[{'id':'spelling','text':'Correct the misspelling only.','authority_refs':[authority]}],
            'invariants':['Preserve meaning.'],'non_goals':['No executable behavior changes.'],'interfaces':[],
            'neighboring_disposition':{'applicability':'not-applicable','reason':'Only a misspelling changes.','evidence_refs':['repo-1:README']}})
        subject=self.subject(path)
        event('risk','review-risk',{'scope':{'role':'session'},'risk':{'schema_version':1,'bindings':review_bindings(subject,{'role':'session'}),
            'classification':'lightweight','triggers':[],'scope_evidence_refs':['repo-1:README:spelling-diff'],
            'perspectives':{p:{'applicability':'not-applicable','reason':'Selected change corrects only spelling in plain prose.','evidence_refs':['repo-1:README']} for p in PERSPECTIVES}}})
        event('budget','configure-effects',{'max_attempts':1,'max_estimated_cost':1,'max_elapsed_ms':30000,'authorization':{'approved':True,'actor_id':'fixture-user'}})
        fixture=ReviewDispatchTests()
        class Prose:
            def __init__(self,*args):pass
            def configure(self,resolved,brief,access='read-only'):return {'observed':resolved,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configured'}
            def discover(self):return {'capabilities':fixture.capabilities(),'discovery':fixture.discovery()}
            def invoke(self,resolved,prompt,actor,access,timeout):
                subject=read_session(path)['subject'];package=list(subject['review_packages'].values())[-1]
                assert (Path(subject['repositories']['repo-1']['location'])/'README').read_text()=='The guide\n'
                report={'verdict':'pass','findings':[],'reviewed_inputs':package['review_inputs'],'review_input_ref':review_input_id(package),
                    'risk_confirmation':{'assessment_hash':package['review_requirements']['assessment_hash'],'disposition':'confirmed',
                        'reason':'Exact diff changes spelling only.','evidence_refs':['package:'+package['package_hash']]},
                    'execution_inapplicable':{'reason':'Plain prose spelling has no execution target.','evidence_refs':['package:'+package['package_hash']]}}
                child=subprocess.run([sys.executable,'-c','import sys; print(sys.argv[1])',json.dumps(report)],capture_output=True,text=True,check=True)
                return {'status':'completed','observed':resolved,'invocation_ref':'fixture:prose-child','observation_source':'host-invocation-metadata','output':child.stdout}
            def close(self):pass
        with patch('workflow_lib.native_runtime.policy',return_value=fixture.policy()),patch('workflow_lib.session_models.CodexBackend',Prose):
            result=dispatch_session_review(path,{'perspective':'code','host':'codex','actor_id':'independent','estimated_cost':1},'prose')
        self.assertEqual(result['report_status'],'recorded',result)
        status=standalone_status(path);self.assertEqual(status['outcome'],'pass',status);self.assertFalse(status['workflow_acceptance'])

    def test_explicit_model_restriction_prevents_any_native_turn(self):
        from unittest.mock import patch
        from test_review_dispatch import ReviewDispatchTests
        from workflow_lib.review_dispatch import dispatch_session_review
        base,repo,path=self.model_fixture();fixture=ReviewDispatchTests()
        class Restricted:
            def __init__(self,*args):pass
            def configure(self,resolved,brief,access='read-only'):return {'observed':resolved,'observation_source':'host-effective-configuration','invocation_ref':'fixture:configured'}
            def discover(self):return {'capabilities':fixture.capabilities(),'discovery':fixture.discovery()}
            def invoke(self,*args):raise AssertionError('An explicitly excluded model was invoked.')
            def close(self):pass
        with patch('workflow_lib.native_runtime.policy',return_value=fixture.policy()),patch('workflow_lib.session_models.CodexBackend',Restricted):
            result=dispatch_session_review(path,{'perspective':'security','host':'codex','actor_id':'independent','estimated_cost':1,
                'diagnostic':True,'preferences':{'allowed_models':[]}},'restricted')
        self.assertEqual(result['status'],'block');self.assertFalse(result['dispatch'])
