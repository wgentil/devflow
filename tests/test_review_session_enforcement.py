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
