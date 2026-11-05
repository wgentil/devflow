import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError

class SessionTests(unittest.TestCase):
    def api(self):
        from workflow_lib import review_sessions
        return review_sessions
    def test_scope_output_and_replay(self):
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir()
        api=self.api()
        with self.assertRaises(WorkflowError):api.initialize_session(repo/'session.db',{'id':'s','repositories':[str(repo)],'source_identity':'sha'})
        path=base/'session.db';api.initialize_session(path,{'id':'s','repositories':[str(repo)],'source_identity':'sha'})
        event={'action':'configure-effects','record':{'max_attempts':1,'max_estimated_cost':1,'max_elapsed_ms':1000,'authorization':{'approved':True,'actor_id':'fixture-user'}}}
        first=api.transact_session(path,0,'configure',event)
        self.assertEqual(first['version'],1)
        retry=api.transact_session(path,0,'configure',event)
        self.assertTrue(retry['replayed'])
        self.assertEqual(api.read_session(path)['version'],1)
        with self.assertRaises(WorkflowError):api.transact_session(path,0,'different',event)
    def test_two_processes_cannot_double_claim(self):
        import subprocess,json
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();path=base/'session.db'
        api=self.api();api.initialize_session(path,{'id':'s','repositories':[str(repo)],'source_identity':'sha'})
        api.transact_session(path,0,'cfg',{'action':'configure-effects','record':{'max_attempts':1,'max_estimated_cost':1,'max_elapsed_ms':1000,'authorization':{'approved':True,'actor_id':'fixture-user'}}})
        gate=base/'go'
        script='''import sys,time,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from workflow_lib.review_sessions import transact_session
from workflow_lib.store import WorkflowError
while not Path(sys.argv[3]).exists(): time.sleep(.01)
try:
 r=transact_session(Path(sys.argv[2]),1,sys.argv[4],{'action':'claim','record':{'effect_id':sys.argv[4],'scope':'same','estimated_cost':1,'now_ms':1,'source_identity':'sha'}})
 print('claimed')
except WorkflowError: print('blocked')
'''
        workers=[subprocess.Popen([sys.executable,'-c',script,sys.path[0],str(path),str(gate),name],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for name in ('one','two')]
        gate.touch();outputs=[p.communicate(timeout=20) for p in workers]
        self.assertEqual(sorted(o[0].strip() for o in outputs),['blocked','claimed'],outputs)
        self.assertEqual(len(api.read_session(path)['subject']['effects']),1)
    def test_interruption_before_commit_retains_state_and_operation_identity(self):
        import sqlite3
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();path=base/'session.db'
        api=self.api();api.initialize_session(path,{'id':'s','repositories':[str(repo)],'source_identity':'sha'})
        conn=sqlite3.connect(path,isolation_level=None);conn.execute('BEGIN IMMEDIATE')
        conn.execute("UPDATE manifest SET body='incomplete' WHERE id=1");conn.close()
        self.assertEqual(api.read_session(path)['version'],0)
    def test_corrupt_manifest_is_not_empty_session(self):
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));path=base/'session.db';path.write_text('torn')
        with self.assertRaises(WorkflowError):self.api().read_session(path)

    def test_standalone_answer_binds_review_contract_without_fake_specification(self):
        from workflow_lib.action_policy import subject_decision
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();path=base/'session.db'
        api=self.api();initial=api.initialize_session(path,{'id':'s','repositories':[str(repo)],'source_identity':'sha'})
        subject=initial['subject'];contract_hash=subject['review_contract_hash']
        self.assertNotIn('plan',subject);self.assertNotIn('spec',subject)
        api.transact_session(path,0,'question',{'action':'question','record':{
            'id':'q','text':'Which retention rule?','scope':None,'source_identity':'sha','contract_hash':contract_hash}})
        self.assertEqual(subject_decision(api.read_session(path)['subject'],'completion',{})['status'],'block')
        answer={'id':'q','question_version':1,'answer':'Thirty days.','actor_id':'fixture-user',
            'material':False,'contract_hash':contract_hash,'provenance':{'kind':'user-message','ref':'fixture-message'}}
        api.transact_session(path,1,'answer',{'action':'answer','record':answer})
        subject=api.read_session(path)['subject']
        self.assertEqual(subject_decision(subject,'completion',{})['status'],'allow')
        self.assertNotIn('plan',subject);self.assertNotIn('spec',subject)
        self.assertEqual(subject['clarifications']['q']['answer'],answer)

    def test_initialization_cannot_import_preapproved_reviews_or_claims(self):
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir()
        for key,value in (('effects',{'fake':{'status':'completed'}}),('reviews',{'branch':[{'verdict':'pass'}]}),
                          ('worker_termination_observations',{'fake':{'basis':'os-owner-stopped'}})):
            with self.subTest(key=key), self.assertRaises(WorkflowError):
                self.api().initialize_session(base/(key+'.db'),{'id':'s','repositories':[str(repo)],
                    'source_identity':'sha',key:value})

    def test_material_session_answer_requires_exact_contract_amendment_and_user_approval(self):
        from workflow_lib.document_units import digest
        from workflow_lib.action_policy import subject_decision
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();path=base/'session.db'
        api=self.api();initial=api.initialize_session(path,{'id':'s','repositories':[str(repo)],'source_identity':'sha'})
        subject=initial['subject'];old_hash=subject['review_contract_hash']
        api.transact_session(path,0,'q',{'action':'question','record':{'id':'q','text':'Retention?',
            'scope':None,'source_identity':'sha','contract_hash':old_hash}})
        request={'retention_days':30}
        new_hash=digest({'scope':subject['review_contract']['scope'],'request':request})
        api.transact_session(path,1,'a',{'action':'answer','record':{'id':'q','question_version':1,
            'answer':'Thirty days.','actor_id':'fixture-user','material':True,'contract_hash':new_hash,
            'provenance':{'kind':'user-message','ref':'fixture-message'}}})
        self.assertEqual(subject_decision(api.read_session(path)['subject'],'completion',{})['status'],'block')
        record={'previous_contract_hash':old_hash,'review_contract':request,'authorization':{
            'approved':True,'actor_id':'fixture-user','contract_hash':new_hash,'reason':'approve actual decision',
            'provenance':{'kind':'user-message','ref':'fixture-approval'}}}
        api.transact_session(path,2,'amend',{'action':'amend-review-contract','record':record})
        subject=api.read_session(path)['subject']
        self.assertEqual(subject_decision(subject,'completion',{})['status'],'allow')
        self.assertNotIn('spec',subject);self.assertNotIn('plan',subject)
        with self.assertRaises(WorkflowError):
            api.transact_session(path,3,'stale-amend',{'action':'amend-review-contract','record':record})

    def test_contract_corruption_and_nonfinite_initial_input_fail_closed(self):
        import json,sqlite3
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();path=base/'session.db'
        api=self.api();api.initialize_session(path,{'id':'s','repositories':[str(repo)],'source_identity':'sha'})
        conn=sqlite3.connect(path)
        value=json.loads(conn.execute('SELECT body FROM manifest WHERE id=1').fetchone()[0])
        value['subject']['review_contract']['request']['changed']='unapproved'
        conn.execute('UPDATE manifest SET body=? WHERE id=1',(json.dumps(value),));conn.commit();conn.close()
        with self.assertRaises(WorkflowError):api.read_session(path)
        with self.assertRaises(WorkflowError):
            api.initialize_session(base/'invalid.db',{'id':'s','repositories':[str(repo)],'source_identity':'sha',
                'review_contract':{'estimate':float('nan')}})
