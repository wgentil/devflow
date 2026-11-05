"""Owned subprocesses model infrastructure effects; no provider or real infrastructure."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib.store import transact,read_state
from workflow_lib.protected_changes import snapshot_protected

class TypedExecutionTests(unittest.TestCase):
    def test_plan_apply_has_bound_source_and_cannot_repeat_authorized_effect(self):
        base=Path(self.enterContext(tempfile.TemporaryDirectory()));repo=base/'repo';repo.mkdir();control=base/'control'
        for args in (['init','-q'],['config','user.email','fixture@example.invalid'],['config','user.name','Fixture']):subprocess.run(['git',*args],cwd=repo,check=True)
        (repo/'config').write_text('owned fixture')
        subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','baseline'],cwd=repo,check=True)
        inv={'paths':[]};run={'id':'r','status':'active','state_version':1,'enforcement':{'protocol':'devflow.python-enforcement/v1','policy_version':1},
            'repositories':{'repo':{'location':str(repo)}},'protected_inventories':{'repo':{'inventory':inv,'baseline':snapshot_protected(repo,inv)}},
            'plan':{'work_items':[{'id':'I','kind':'iac','repo_id':'repo','dependencies':[]}]},
            'items':{'I':{'status':'pending','attempts':[{'token':'t'}]}},'active_attempt':{'token':'t','item_id':'I','state_version':1},
            'verification_proofs':{},'verifier_proofs':{}}
        transact(control,0,'seed',{'kind':'fixture','payload':{'runs':{'r':run},'repositories':run['repositories']}})
        clean=[sys.executable,'-c','print(\'{"violations":[]}\')']
        def call(kind,*args):
            p=subprocess.run([sys.executable,str(ROOT/'skills/workflow/scripts/run.py'),'build',kind,'--root',str(control),
                '--run-id','r','--attempt-id','t',*map(str,args)],capture_output=True,text=True)
            return p,json.loads(p.stdout)
        p,plan=call('verify-iac-plan','--plan-argv-json',json.dumps(clean),'--policy-argv-json',json.dumps(clean),'--operation-id','plan')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        counter=base/'effects'
        apply=[sys.executable,'-c',f"from pathlib import Path;p=Path({str(counter)!r});p.write_text(p.read_text()+'x' if p.exists() else 'x')"]
        p,authorization=call('authorize-apply','--apply-argv-json',json.dumps(apply),'--policy-argv-json',json.dumps(clean),
            '--plan-proof-id',plan['id'],'--actor-id','fixture-user')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        args=['--apply-argv-json',json.dumps(apply),'--policy-argv-json',json.dumps(clean),'--authorization-id',authorization['id']]
        p,proof=call('verify-iac-apply',*args,'--operation-id','apply')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertTrue(proof.get('source_identity'));self.assertTrue(proof.get('execution_id'))
        p,retry=call('verify-iac-apply',*args,'--operation-id','apply')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr);self.assertTrue(retry['replayed'])
        p,blocked=call('verify-iac-apply',*args,'--operation-id','another-apply')
        self.assertNotEqual(p.returncode,0)
        self.assertEqual(counter.read_text(),'x')
