import json
import multiprocessing
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from test_hosts import host_state, attachment
from workflow_lib.store import WorkflowError, transact, read_state, HOST_CONTEXT
from workflow_lib.hosts import apply_host_event
from workflow_lib.releases import release_descriptor


def acquire(root, actor, queue):
    try:
        transact(Path(root),1,actor,{'kind':'domain.host.attach','payload':{'request':attachment(binding_id=actor,session_id=actor,actor_id=actor)}})
        queue.put('acquired')
    except WorkflowError:queue.put('blocked')

class IntegrationTests(unittest.TestCase):
    def test_multiprocess_owner_cas(self):
        with tempfile.TemporaryDirectory() as temp:
            transact(Path(temp),0,'seed',{'kind':'fixture','payload':host_state()})
            context=multiprocessing.get_context('spawn');queue=context.Queue()
            processes=[context.Process(target=acquire,args=(temp,actor,queue)) for actor in ('one','two')]
            for process in processes:process.start()
            results=[queue.get(timeout=15) for _ in processes]
            for process in processes:process.join(15);self.assertEqual(process.exitcode,0)
            self.assertEqual(sorted(results),['acquired','blocked'])
    def test_stale_binding_rejected_under_commit_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            transact(root,0,'seed',{'kind':'fixture','payload':host_state()})
            transact(root,1,'attach',{'kind':'domain.host.attach','payload':{'request':attachment()}})
            transact(root,2,'detach',{'kind':'domain.host.detach','payload':{'request':{'binding_id':'b1','revision':1}}})
            token=HOST_CONTEXT.set({'binding_id':'b1','revision':1})
            try:
                with self.assertRaises(WorkflowError):transact(root,3,'stale',{'kind':'fixture','payload':{'changed':True}})
            finally:HOST_CONTEXT.reset(token)
            self.assertNotIn('changed',read_state(root)['data'])
    def test_reviewer_cannot_mutate_implementation(self):
        state=host_state();state['runs']['run']['review_packages']={'pkg':{'role':'branch'}}
        apply_host_event(state,'attach',attachment(binding_id='rb',role='branch-reviewer',actor_id='ra',package_hash='pkg'))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);transact(root,0,'seed',{'kind':'fixture','payload':state})
            token=HOST_CONTEXT.set({'binding_id':'rb','revision':1})
            try:
                with self.assertRaises(WorkflowError):transact(root,1,'mutate',{'kind':'fixture','payload':{'changed':True}})
            finally:HOST_CONTEXT.reset(token)
    def test_external_root_corrupt_locator_blocks_known_mapped_only(self):
        from workflow_lib.host_locators import write_locator, locator_path, write_task_index
        from workflow_lib.host_hook import evaluate
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)/'project';project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True)
            root=Path(temp)/'external'
            state=host_state(str(project.resolve()));binding=apply_host_event(state,'attach',attachment(str(project.resolve()),host='claude'))
            apply_host_event(state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'mapped','scope':'item','item_id':'W1','token':'t'})
            transact(root,0,'seed',{'kind':'fixture','payload':state})
            write_locator(project,'claude','s1',root,'b1');write_task_index(project,'claude','s1',root,['mapped'])
            locator_path(project,'claude','s1').write_text('{')
            self.assertEqual(evaluate(str(project),'s1','TaskCompleted','mapped')['status'],'block')
            self.assertEqual(evaluate(str(project),'s1','TaskCompleted','ordinary')['status'],'inactive')
    def test_legacy_adoption_explicit_only_before_bindings(self):
        state=host_state()
        adopted=apply_host_event(state,'legacy-adopt',attachment(adopt_legacy=True))
        self.assertEqual(adopted['legacy_adoption_actor'],'a1')
        with self.assertRaises(WorkflowError):apply_host_event(state,'legacy-adopt',attachment(binding_id='b2',session_id='s2',adopt_legacy=True))

    def test_host_check_cli_uses_task_binding_without_mutation_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);state=host_state()
            apply_host_event(state,'attach',attachment())
            apply_host_event(state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'})
            transact(root,0,'seed',{'kind':'fixture','payload':state})
            result=subprocess.run([sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),'host','check','--root',str(root),'--binding-id','b1','--task-id','task'],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['reason_code'],'ACTIVE_ATTEMPT')
    def test_legacy_run_cannot_silently_attach(self):
        state=host_state();state['runs']['run'].pop('host_protocol_version',None)
        with self.assertRaises(WorkflowError):apply_host_event(state,'attach',attachment())
    def test_upgraded_helper_blocks_stale_session_mutation_and_mapped_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);state=host_state()
            binding=apply_host_event(state,'attach',attachment())
            apply_host_event(state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'})
            state['host_bindings']['b1']['release']['fingerprint']='older-helper'
            transact(root,0,'seed',{'kind':'fixture','payload':state})
            base=[sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py')]
            check=subprocess.run(base+['host','check','--root',str(root),'--binding-id','b1','--task-id','task'],capture_output=True,text=True)
            self.assertEqual(json.loads(check.stdout)['reason_code'],'RELEASE_MISMATCH')
            mutate=subprocess.run(base+['--binding-id','b1','--binding-revision','1','run','next','--root',str(root),'--run-id','run'],capture_output=True,text=True)
            self.assertEqual(json.loads(mutate.stdout)['error'],'RELEASE_MISMATCH')
