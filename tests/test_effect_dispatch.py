"""Native effect reservations use real root transactions and owned Git sources."""
import sys
import tempfile
import subprocess
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib import store,sqlite_store
from workflow_lib.store import WorkflowError

class EffectDispatchTests(unittest.TestCase):
    def fixture(self):
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));root=base/'control';repo=base/'repo';repo.mkdir()
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'source.py').write_text('value=1')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','base'],cwd=repo,check=True)
        sqlite_store.initialize_store(root)
        subject={'id':'r','state_version':0,'enforcement':{'protocol':'devflow.python-enforcement/v1', 'policy_version':1},'repositories':{'app':{'location':str(repo)}},
                 'effect_policy':{'max_attempts':1,'max_estimated_cost':1,'max_elapsed_ms':100000}}
        store.transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':subject}}})
        return root,repo
    def test_claim_observes_current_source_and_retry_does_not_launch_again(self):
        from workflow_lib.effect_dispatch import reserve_dispatch
        root,repo=self.fixture()
        receipt=reserve_dispatch(root,'r','invocation','exclusive-scope',1,'op',{})
        run=store.read_state(root)['data']['runs']['r']
        self.assertEqual(run['effects']['invocation']['status'],'claimed')
        self.assertEqual(run['effects']['invocation']['source_identity'],run['source_identity'])
        with self.assertRaises(WorkflowError):reserve_dispatch(root,'r','invocation','exclusive-scope',1,'op',{})
        self.assertEqual(len(store.read_state(root)['data']['runs']['r']['effects']),1)
    def test_missing_price_or_pending_question_never_claims(self):
        from workflow_lib.effect_dispatch import reserve_dispatch
        root,repo=self.fixture()
        with self.assertRaises(WorkflowError):reserve_dispatch(root,'r','invocation','scope',None,'op',{})
        self.assertFalse(store.read_state(root)['data']['runs']['r'].get('effects'))
        state=store.read_state(root);run=state['data']['runs']['r']
        run['clarifications']={'q':{'id':'q','version':1,'status':'pending','scope':None}}
        store.transact(root,state['version'],'question-fixture',{'kind':'fixture','payload':{'runs':{'r':run}}})
        with self.assertRaises(WorkflowError):reserve_dispatch(root,'r','invocation','scope',1,'op',{})
        self.assertFalse(store.read_state(root)['data']['runs']['r'].get('effects'))
