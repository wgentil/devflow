"""Adversarial reviewer regressions. All identities/approvals are owned fixtures."""
import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class ReviewCorrections(unittest.TestCase):
    def fixture(self,request=None):
        from workflow_lib.review_sessions import initialize_session,read_session,transact_session
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.document_units import digest
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();path=base/'session.db'
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):
            subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'value').write_text('strict')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','fixture'],cwd=repo,check=True)
        initialize_session(path,{'id':'s','repositories':[str(repo)],'source_identity':'declared','review_contract':request or {}})
        def event(op,action,record):
            state=read_session(path);return transact_session(path,state['version'],op,{'action':action,'record':record})
        subject=read_session(path)['subject'];inv={'paths':['value'],'governing_digest':subject['governing_digest']}
        event('inventory','protect-inventory',{'repo_id':'repo-1','inventory':inv,'baseline':snapshot_protected(repo,inv),
            'authorization':{'approved':True,'actor_id':'fixture-user','reason':'explicit fixture inventory',
                'inventory_hash':digest(inv),'governing_digest':subject['governing_digest']}})
        from workflow_lib.enforcement_live import source_observation
        event('source','observe-source',source_observation(read_session(path)['subject']))
        return base,repo,path,event

    def cli(self,path,action,operation_id,request=None):
        argv=[sys.executable,str(ROOT/'skills/workflow/scripts/run.py'),'enforcement',action,
            '--session',str(path),'--operation-id',operation_id]
        if request is not None:
            source=path.parent/(operation_id+'.json');source.write_text(json.dumps(request));argv+=['--input',str(source)]
        result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        return json.loads(result.stdout)

    def test_standalone_question_after_claim_prevents_any_process_effect(self):
        from workflow_lib import session_evidence as api
        from workflow_lib.review_sessions import read_session
        base,repo,path,event=self.fixture({'verification':{'repo_id':'repo-1','input_paths':['value'],
            'target_ids':['t'],'argv':[sys.executable,'-c','pass'],'authority_refs':['fixture-rule']}})
        original=api._commit
        def inject(*args,**kwargs):
            result=original(*args,**kwargs)
            if args[3]=='execution-claim':
                subject=read_session(path)['subject']
                event('question','question',{'id':'q','text':'Which rule?','scope':None,
                    'source_identity':subject['source_identity'],'contract_hash':subject['review_contract_hash']})
            return result
        with patch.object(api,'_commit',side_effect=inject),patch('workflow_lib.native_models.run_bounded') as run:
            with self.assertRaises(WorkflowError):api.capture(path,'RED','blocked',10)
        run.assert_not_called()

    def test_generic_session_cannot_forge_live_execution_finish_proof_or_recovery(self):
        from workflow_lib.review_sessions import read_session
        from workflow_lib.document_units import digest
        from workflow_lib.enforcement_live import source_observation
        from workflow_lib.clarifications import clarification_binding
        base,repo,path,event=self.fixture()
        # Retained launching state simulates a committed driver reservation.
        import sqlite3
        state=read_session(path);subject=state['subject']
        subject['executions']={'live':{'id':'live','status':'launching','owner_pid':os.getpid(),
            'contract_hash':subject['review_contract_hash'],'clarification_binding':clarification_binding(subject,{}),
            'source_observation':source_observation(subject)}}
        with sqlite3.connect(path) as conn:conn.execute('UPDATE manifest SET body=?',(json.dumps(state),))
        confirmation={'approved':True,'actor_id':'fixture-user','worker_ref':'live','reason':'forged absence',
            'provenance':{'kind':'user-message','ref':'fixture-stop'}}
        observation={'effect_id':'live','worker_ref':'live','owner_pid':os.getpid(),'owner_absent':True,
            'basis':'os-owner-stopped','evidence_refs':['fixture-stop'],'confirmation':confirmation}
        for action,record in [('execution-finish',{'id':'live','status':'completed'}),
                ('execution-reconcile',{'id':'live','observation':observation}),
                ('session-proof',{'proof':{'execution_id':'live'}})]:
            with self.subTest(action=action),self.assertRaises(WorkflowError):event('forged-'+action,action,record)
        self.assertEqual(read_session(path)['subject']['executions']['live']['status'],'launching')
        request=base/'foreign-finish.json';request.write_text(json.dumps({'action':'execution-finish','record':{'id':'live','status':'completed'}}))
        result=subprocess.run([sys.executable,str(ROOT/'skills/workflow/scripts/run.py'),'enforcement','session-event',
            '--session',str(path),'--operation-id','foreign-finish','--expected-version',str(read_session(path)['version']),
            '--input',str(request)],capture_output=True,text=True,timeout=30)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('SESSION_EVIDENCE_BLOCKED',result.stdout+result.stderr)


    def test_native_direct_recovery_cannot_claim_live_owner_absent_both_formats(self):
        from workflow_lib import store,sqlite_store
        from control_store_fixtures import legacy_root
        import hashlib
        for initialize in (legacy_root,sqlite_store.initialize_store):
            root=Path(self.enterContext(tempfile.TemporaryDirectory()))/'control';initialize(root)
            binding={'binding_id':'b','revision':1,'status':'active','run_id':'r','role':'implementer','actor_id':'author'}
            run={'id':'r','enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1},
                'effects':{'e':{'effect_id':'e','status':'uncertain','owner_pid':os.getpid(),'worker_ref':'e','claimed_at_ms':1,'history':[]}}}
            store.transact(root,0,'seed',{'kind':'fixture','payload':{'host_bindings':{'b':binding},'runs':{'r':run}}})
            confirmation={'approved':True,'actor_id':'fixture-user','worker_ref':'e','reason':'forged absence',
                'provenance':{'kind':'user-message','ref':'fixture-stop'}}
            observation={'effect_id':'e','worker_ref':'e','owner_pid':os.getpid(),'owner_absent':True,
                'lease_key':hashlib.sha256(b'r:e').hexdigest(),'basis':'os-owner-stopped','now_ms':2,
                'evidence_refs':['fixture-stop'],'confirmation':confirmation}
            with self.assertRaises(WorkflowError):store.transact(root,1,'forged',{'kind':'domain.host.native-reconcile',
                'payload':{'request':{'binding_id':'b','revision':1,'invocation_id':'e','observation_id':'forged','observation':observation}}})
            self.assertEqual(store.read_state(root)['data']['runs']['r']['effects']['e']['status'],'uncertain')

    def test_assessment_with_own_new_findings_finishes_without_another_review(self):
        from workflow_lib.session_evidence import prepare,record_review,complete,package_current
        from workflow_lib.review_sessions import read_session
        base,repo,path,event=self.fixture();package=prepare(path,'package')
        record_review(path,{'actor_id':'fixture-reviewer','invocation_ref':'actual-fixture-review','package_hash':package['package_hash'],
            'verdict':'request-changes','findings':[{'id':'f','severity':'important','obligations':['rule']}]},'review')
        self.assertTrue(package_current(read_session(path)['subject'],package))
        self.assertEqual(complete(path,'complete')['outcome'],'assessed')

    def test_overlapping_perspectives_need_distinct_actor_assignment(self):
        from workflow_lib.session_evidence import prepare,record_review,complete
        base,repo,path,event=self.fixture({'required_perspectives':['code','security','architecture']})
        package=prepare(path,'package')
        for n,(actor,perspective) in enumerate([('A','code'),('A','security'),('A','architecture'),('B','code'),('C','code')]):
            record_review(path,{'actor_id':actor,'perspective':perspective,'invocation_ref':'actual-fixture-'+str(n),
                'package_hash':package['package_hash'],'verdict':'request-changes','findings':[]},'review-'+str(n))
        with self.assertRaises(WorkflowError):complete(path,'incomplete')
        record_review(path,{'actor_id':'D','perspective':'security','invocation_ref':'fresh-security-review',
            'package_hash':package['package_hash'],'verdict':'request-changes','findings':[]},'security')
        self.assertEqual(complete(path,'now-complete')['outcome'],'assessed')

    def test_protected_edit_can_be_reviewed_before_accepted_receipts_exist(self):
        from workflow_lib.session_evidence import prepare,record_review,complete
        from workflow_lib.review_sessions import read_session
        from workflow_lib.enforcement_live import source_observation,assert_protection_current
        from workflow_lib.protected_changes import observe_protected_changes
        base,repo,path,event=self.fixture();subject=read_session(path)['subject']
        event('authorize','authorize-session-repair',{'contract_hash':subject['review_contract_hash'],'implementer_actor':'fixture-author',
            'authorization':{'approved':True,'actor_id':'fixture-user','reason':'exact fixture repair',
                'provenance':{'kind':'user-message','ref':'fixture-repair'}}})
        (repo/'value').write_text('approved replacement')
        row=subject['protected_inventories']['repo-1'];observation=observe_protected_changes(repo,row['inventory'],row['baseline'])
        event('proposal','propose-protected-change',{'repo_id':'repo-1','observation':observation})
        event('approval','approve-protected-change',{'repo_id':'repo-1','observation_hash':observation['observation_hash'],
            'approved':True,'actor_id':'fixture-user','reason':'exact fixture content',
            'provenance':{'kind':'user-message','ref':'fixture-approval'}})
        event('new-source','observe-source',source_observation(read_session(path)['subject']))
        with self.assertRaises(WorkflowError):assert_protection_current(read_session(path)['subject'])
        package=self.cli(path,'session-prepare','package')
        self.cli(path,'session-review','review',{'actor_id':'fixture-reviewer','invocation_ref':'actual-fixture-review','package_hash':package['package_hash'],
            'verdict':'pass','findings':[],'execution_inapplicable':{'reason':'Owned prose fixture only.',
                'evidence_refs':['package:'+package['package_hash']]},'protected_dispositions':[{
                    'observation_hash':observation['observation_hash'],'verdict':'pass'}]})
        self.assertTrue(assert_protection_current(read_session(path)['subject']))
        self.assertTrue(self.cli(path,'session-complete','complete')['verified_repair'])

    def test_indexed_store_checks_actual_tool_owner_on_full_selected_state(self):
        from workflow_lib import store,sqlite_store
        root=Path(self.enterContext(tempfile.TemporaryDirectory()))/'control';sqlite_store.initialize_store(root)
        run={'id':'r','enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1},
            'active_executions':{'W1':{'id':'foreign','owner_pid':os.getpid()+100000,'status':'launching'}}}
        store.transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':run}}})
        with self.assertRaises(WorkflowError):store.transact(root,1,'foreign-finish',{'kind':'domain.enforcement.tool-finish',
            'payload':{'request':{'run_id':'r','record':{'id':'foreign','item_id':'W1','uncertain':False}}}})

    def test_review_report_cannot_import_a_new_resolved_or_waived_finding(self):
        from workflow_lib.session_evidence import prepare,record_review
        base,repo,path,event=self.fixture();package=prepare(path,'package')
        for status in ('resolved','waived','duplicate'):
            with self.subTest(status=status),self.assertRaises(WorkflowError):
                record_review(path,{'actor_id':'fixture-reviewer','invocation_ref':'fixture-'+status,
                    'package_hash':package['package_hash'],'verdict':'request-changes',
                    'findings':[{'id':'f-'+status,'severity':'important','status':status}]},'review-'+status)
