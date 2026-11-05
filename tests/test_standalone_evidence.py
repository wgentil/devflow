"""Real deterministic standalone execution; reviewer identities are explicit fixtures."""
from pathlib import Path
import json,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class StandaloneEvidenceTests(unittest.TestCase):
    def test_real_pair_independent_review_and_completion_without_workflow(self):
        from workflow_lib.review_sessions import initialize_session,read_session,transact_session
        from workflow_lib.session_evidence import capture,prepare,record_review,complete
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.document_units import digest
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();session=base/'session.db'
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        script="""import json
from pathlib import Path
ok=Path('value').read_text()=='30'
print(json.dumps({'schema':'devflow-test-report-v2','tests':[{'id':'retention','outcome':'passed' if ok else 'failed','failure_phase':None if ok else 'test-assertion'}]}))
raise SystemExit(0 if ok else 1)
"""
        (repo/'test.py').write_text(script);(repo/'value').write_text('60')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','fixture'],cwd=repo,check=True)
        state=initialize_session(session,{'id':'s','repositories':[str(repo)],'source_identity':'declared',
            'review_contract':{'verification':{'repo_id':'repo-1','input_paths':['test.py'],'target_ids':['retention'],
                'argv':[sys.executable,'test.py'],'report_format':'json','authority_refs':['fixture-user-rule:30-days']}}})
        subject=state['subject'];inv={'paths':['test.py'],'governing_digest':subject['governing_digest']}
        transact_session(session,0,'inventory',{'action':'protect-inventory','record':{'repo_id':'repo-1','inventory':inv,
            'baseline':snapshot_protected(repo,inv),'authorization':{'approved':True,'actor_id':'fixture-user','reason':'explicit fixture scope',
                'inventory_hash':digest(inv),'governing_digest':subject['governing_digest']}}})
        def cli(action,op,request=None):
            entry=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
            argv=[sys.executable,str(entry),'enforcement',action,'--session',str(session),'--operation-id',op]
            if request is not None:
                request_path=base/'request.json';request_path.write_text(json.dumps(request));argv+=['--input',str(request_path)]
            result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return json.loads(result.stdout)
        red=cli('session-verify','red',{'phase':'RED','timeout_seconds':10})
        # Historical validation must bind proof source exactly to its reserved execution.
        import copy
        from workflow_lib.session_evidence import reduce_session
        subject=copy.deepcopy(read_session(session)['subject']);subject['executions']['red']['status']='launching'
        forged=copy.deepcopy(red);forged['source_observation']={'snapshots':{'repo-1':{'invented':'source'}},'source_identity':'forged'}
        with self.assertRaises(WorkflowError):reduce_session(subject,'session-proof',{'proof':forged})
        (repo/'value').write_text('30')
        green=cli('session-verify','green',{'phase':'GREEN','timeout_seconds':10})
        self.assertNotEqual(red['source_identity'],green['source_identity'])
        self.assertTrue(capture(session,'GREEN','green',timeout=10)['replayed'])
        package=cli('session-prepare','package')
        report={'package_hash':package['package_hash'],'actor_id':'fixture-reviewer','invocation_ref':'fixture-review',
            'verdict':'pass','findings':[],'test_oracles':[{'red_proof_id':red['id'],'green_proof_id':green['id'],
                'input_hashes':green['integrity']['contract']['input_hashes'],
                'authority_refs':['fixture-user-rule:30-days'],'failure_relevance':'Sixty fails the specified thirty-day behavior.'}]}
        cli('session-review','review',report)
        outcome=cli('session-complete','complete')
        self.assertEqual(outcome['outcome'],'assessed')
        self.assertFalse(outcome['verified_repair'])
        subject=read_session(session)['subject']
        self.assertNotIn('plan',subject);self.assertNotIn('spec',subject);self.assertNotIn('runs',subject)
        self.assertFalse((repo/'.devflow').exists())
        with self.assertRaises(WorkflowError):capture(session,'GREEN','after-completion',timeout=10)

    def test_prose_repair_requires_user_authorization_and_independent_current_disposition(self):
        from workflow_lib.review_sessions import initialize_session,read_session,transact_session
        from workflow_lib.session_evidence import prepare,record_review,complete
        from workflow_lib.enforcement_live import source_observation
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.finding_closure import finding_hash
        from workflow_lib.document_units import digest
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();path=base/'s.db'
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'README').write_text('incorrect sentence')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','baseline'],cwd=repo,check=True)
        initialize_session(path,{'id':'s','repositories':[str(repo)],'source_identity':'declared'})
        def event(op,action,record):
            state=read_session(path);return transact_session(path,state['version'],op,{'action':action,'record':record})
        subject=read_session(path)['subject'];inv={'paths':[],'governing_digest':subject['governing_digest']}
        event('inv','protect-inventory',{'repo_id':'repo-1','inventory':inv,'baseline':snapshot_protected(repo,inv),
            'authorization':{'approved':True,'actor_id':'fixture-user','reason':'explicit prose fixture protection scope',
                'inventory_hash':digest(inv),'governing_digest':subject['governing_digest']}})
        event('source','observe-source',source_observation(read_session(path)['subject']))
        package=prepare(path,'initial-package')
        finding={'id':'doc','severity':'important','mandatory':True,'status':'open','obligations':['wording']}
        record_review(path,{'actor_id':'fixture-reviewer','invocation_ref':'first-call','package_hash':package['package_hash'],
            'verdict':'request-changes','findings':[finding]},'initial-review')
        candidate={'finding_id':'doc','source_identity':read_session(path)['subject']['source_identity'],'proof_ids':[],'rationale':'prose correction'}
        with self.assertRaises(WorkflowError):event('unauthorized','propose-fix',candidate)
        event('authorize','authorize-session-repair',{'contract_hash':subject['review_contract_hash'],'implementer_actor':'fixture-writer',
            'authorization':{'approved':True,'actor_id':'fixture-user','reason':'correct the sentence',
                'provenance':{'kind':'user-message','ref':'fixture-message'}}})
        (repo/'README').write_text('correct sentence')
        event('corrected-source','observe-source',source_observation(read_session(path)['subject']))
        candidate['source_identity']=read_session(path)['subject']['source_identity'];event('candidate','propose-fix',candidate)
        package=prepare(path,'corrected-package')
        applicability={'reason':'Only prose wording changed.','evidence_refs':['package:'+package['package_hash']]}
        report={'actor_id':'fixture-reviewer','invocation_ref':'fresh-call','package_hash':package['package_hash'],
            'verdict':'pass','findings':[],'execution_inapplicable':applicability,'closure_dispositions':[{
                'finding_id':'doc','finding_hash':finding_hash(finding),'source_identity':candidate['source_identity'],
                'obligations':['wording'],'disposition':'resolved','proof_ids':[],'execution_inapplicable':applicability}]}
        review=record_review(path,report,'corrected-review')
        event('close','close-finding',{'finding_id':'doc','review_id':digest(report)})
        self.assertTrue(complete(path,'complete')['verified_repair'])
        self.assertEqual(complete(path,'complete')['outcome'],'verified-repair')
