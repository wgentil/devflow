"""Exercise public boundaries in fresh processes; approvals are owned fixture data."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib import store,sqlite_store
from control_store_fixtures import legacy_root

class EnforcementIntegrationTests(unittest.TestCase):
    def cli(self,base,*args,request=None,expected=0):
        argv=[sys.executable,str(ROOT/'skills/workflow/scripts/run.py'),'enforcement',*map(str,args)]
        if request is not None:
            path=base/'request.json';path.write_text(json.dumps(request));argv+=['--input',str(path)]
        result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,expected,result.stdout+result.stderr)
        return json.loads(result.stdout)
    def test_workflow_question_and_answer_both_formats(self):
        for initialize in (legacy_root,sqlite_store.initialize_store):
            with tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);root=base/'control';initialize(root)
                run={'id':'r','state_version':0,'status':'active','plan':{'spec_hash':'spec','work_items':[{'id':'a','dependencies':[]}]}}
                store.transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':run}}})
                self.cli(base,'adopt','--root',root,'--operation-id','adopt',request={'run_id':'r','authorization':{
                    'approved':True,'actor_id':'fixture-user','run_id':'r','state_version':0}})
                question_receipt=self.cli(base,'question','--root',root,'--operation-id','question',request={'run_id':'r','record':{
                    'id':'q','text':'Retention rule?','scope':['a'],'source_identity':'fixture-source','spec_hash':'spec'}})
                self.assertEqual(question_receipt['journal_version'],question_receipt['event_sequence'])
                decision=self.cli(base,'decide','--root',root,request={'run_id':'r','action':'dispatch','scope':{'item_id':'a'}})
                self.assertEqual(decision['status'],'block')
                self.cli(base,'answer','--root',root,'--operation-id','answer',request={'run_id':'r','record':{
                    'id':'q','question_version':1,'answer':'30 days','actor_id':'fixture-user','spec_hash':'spec','material':False,
                    'provenance':{'kind':'user-message','ref':'fixture-message'}}})
                decision=self.cli(base,'decide','--root',root,request={'run_id':'r','action':'dispatch','scope':{'item_id':'a'}})
                self.assertEqual(decision['status'],'allow')
    def test_standalone_public_session_without_workflow_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);repo=base/'repo';repo.mkdir();session=base/'session.sqlite3'
            self.cli(base,'session-init','--session',session,request={'id':'s','repositories':[str(repo)],'source_identity':'fixture-source'})
            event={'action':'configure-effects','record':{'max_attempts':1,'max_estimated_cost':1,'max_elapsed_ms':1000,
                'authorization':{'approved':True,'actor_id':'fixture-user'}}}
            self.cli(base,'session-event','--session',session,'--operation-id','configure','--expected-version',0,request=event)
            retry=self.cli(base,'session-event','--session',session,'--operation-id','configure','--expected-version',0,request=event)
            self.assertTrue(retry['replayed'])
            self.assertEqual(self.cli(base,'session-status','--session',session)['version'],1)
    def test_observe_source_records_real_fingerprint(self):
        from workflow_lib.enforcement_live import source_observation
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);repo=base/'repo';repo.mkdir();root=base/'control';sqlite_store.initialize_store(root)
            for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
            (repo/'source.py').write_text('value=1');subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','base'],cwd=repo,check=True)
            run={'id':'r','state_version':0,'enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'repositories':{'r':{'location':str(repo)}}}
            store.transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':run}}})
            self.cli(base,'observe-source','--root',root,'--operation-id','observe',request={'run_id':'r'})
            self.assertEqual(store.read_state(root)['data']['runs']['r']['source_identity'],source_observation(run)['source_identity'])

    def test_protected_proposal_and_approval_public_commands_both_formats(self):
        from workflow_lib.document_units import digest
        for initialize in (legacy_root,sqlite_store.initialize_store):
            with tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);root=base/'control';initialize(root);repo=base/'repo';repo.mkdir()
                for argv in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):
                    subprocess.run(['git',*argv],cwd=repo,check=True)
                target=repo/'acceptance.py';target.write_text('original rule')
                subprocess.run(['git','add','.'],cwd=repo,check=True)
                subprocess.run(['git','commit','-qm','fixture baseline'],cwd=repo,check=True)
                run={'id':'r','state_version':0,'status':'active','governing_digest':'g',
                    'repositories':{'repo':{'location':str(repo)}}}
                store.transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':run}}})
                self.cli(base,'adopt','--root',root,'--operation-id','adopt',request={'run_id':'r',
                    'authorization':{'approved':True,'actor_id':'fixture-user','run_id':'r','state_version':0}})
                inventory={'paths':['acceptance.py'],'governing_digest':'g'}
                self.cli(base,'protect-inventory','--root',root,'--operation-id','inventory',request={'run_id':'r',
                    'record':{'repo_id':'repo','inventory':inventory,'authorization':{'approved':True,
                        'actor_id':'fixture-user','reason':'declared acceptance contract','governing_digest':'g',
                        'inventory_hash':digest(inventory)}}})
                target.write_text('candidate rule')
                proposal={'run_id':'r','record':{'repo_id':'repo'}}
                self.cli(base,'propose-protected-change','--root',root,'--operation-id','proposal',request=proposal)
                subject=store.read_state(root)['data']['runs']['r']
                observation_hash=next(iter(subject['protected_change_proposals']))
                approval={'run_id':'r','record':{'repo_id':'repo','observation_hash':observation_hash,
                    'approved':True,'actor_id':'fixture-user','reason':'actual fixture decision',
                    'provenance':{'kind':'user-message','ref':'fixture-message'}}}
                self.cli(base,'approve-protected-change','--root',root,'--operation-id','approval',request=approval)
                target.write_text('different unapproved bytes')
                self.cli(base,'propose-protected-change','--root',root,'--operation-id','proposal',request=proposal)
                current=store.read_state(root)['data']['runs']['r']
                self.assertEqual(current['protected_change_proposals'],subject['protected_change_proposals'])
                self.assertEqual(current['protected_authorizations'],[approval['record']])
                from workflow_lib.enforcement_live import assert_protection_current
                with self.assertRaises(store.WorkflowError):assert_protection_current(current)
                self.assertEqual(target.read_text(),'different unapproved bytes')

    def test_standalone_public_question_answer_uses_contract_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);repo=base/'repo';repo.mkdir();session=base/'review.db'
            initial=self.cli(base,'session-init','--session',session,request={
                'id':'s','repositories':[str(repo)],'source_identity':'fixture-source'})
            contract_hash=initial['subject']['review_contract_hash']
            self.cli(base,'session-event','--session',session,'--operation-id','q','--expected-version','0',
                request={'action':'question','record':{'id':'q','text':'Which retention?',
                    'scope':None,'source_identity':'fixture-source','contract_hash':contract_hash}})
            answer={'id':'q','question_version':1,'answer':'Thirty days.','actor_id':'fixture-user',
                'contract_hash':contract_hash,'material':False,
                'provenance':{'kind':'user-message','ref':'fixture-message'}}
            self.cli(base,'session-event','--session',session,'--operation-id','a','--expected-version','1',
                request={'action':'answer','record':answer})
            state=self.cli(base,'session-status','--session',session)
            self.assertEqual(state['subject']['clarifications']['q']['answer'],answer)
            self.assertNotIn('plan',state['subject']);self.assertNotIn('spec',state['subject'])
            self.assertFalse((base/'events').exists());self.assertFalse((repo/'.devflow').exists())
