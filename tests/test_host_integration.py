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
    def test_cli_new_run_attachment_replaces_terminal_locator_and_task_index(self):
        from workflow_lib.host_locators import write_locator, write_task_index, read_locator, read_task_index
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp)/'project';project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True)
            root=project/'.devflow/control'
            state=host_state(str(project.resolve()))
            apply_host_event(state,'attach',attachment(str(project.resolve()),host='claude'))
            apply_host_event(state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'old-task','scope':'item','item_id':'W1','token':'t'})
            state['runs']['run']['status']='delivered'
            state['runs']['next']={**json.loads(json.dumps(state['runs']['run'])),'id':'next','status':'active'}
            transact(root,0,'seed',{'kind':'fixture','payload':state})
            write_locator(project,'claude','s1',root,'b1')
            write_task_index(project,'claude','s1',root,['old-task'])
            request=attachment(str(project.resolve()),host='claude',binding_id='b2',run_id='next')
            request.pop('release')
            payload=project/'attach.json';payload.write_text(json.dumps(request))
            loaded=project/'loaded.json';loaded.write_text(json.dumps(release_descriptor()))
            result=subprocess.run([sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),'host','attach','--root',str(root),'--file',str(payload),'--loaded-release',str(loaded),'--operation-id','next-attach'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(read_locator(project,'claude','s1')['binding_id'],'b2')
            self.assertEqual(read_task_index(project,'claude','s1')['task_ids'],[])
            self.assertEqual(read_state(root)['data']['host_bindings']['b1']['status'],'detached')
            retry=subprocess.run([sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),'host','attach','--root',str(root),'--file',str(payload),'--loaded-release',str(loaded),'--operation-id','next-attach'],capture_output=True,text=True)
            self.assertEqual(retry.returncode,0,retry.stdout+retry.stderr)
            self.assertEqual(read_task_index(project,'claude','s1')['task_ids'],[])
    def test_cli_terminal_switch_clears_old_project_task_cache(self):
        from workflow_lib.host_locators import write_locator, write_task_index, read_task_index
        with tempfile.TemporaryDirectory() as temp:
            old=Path(temp)/'old';new=Path(temp)/'new'
            for project in (old,new):
                project.mkdir();subprocess.run(['git','init','-q',str(project)],check=True)
            root=Path(temp)/'control'
            state=host_state(str(old.resolve()))
            apply_host_event(state,'attach',attachment(str(old.resolve()),host='claude'))
            apply_host_event(state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'old-task','scope':'item','item_id':'W1','token':'t'})
            state['runs']['run']['status']='delivered'
            state['runs']['next']={**json.loads(json.dumps(state['runs']['run'])),'id':'next','status':'active','repositories':{'repo':{'location':str(new.resolve())}}}
            transact(root,0,'seed',{'kind':'fixture','payload':state})
            write_locator(old,'claude','s1',root,'b1')
            write_task_index(old,'claude','s1',root,['old-task'])
            request=attachment(str(new.resolve()),host='claude',binding_id='b2',run_id='next')
            request.pop('release')
            payload=new/'attach.json';payload.write_text(json.dumps(request))
            loaded=new/'loaded.json';loaded.write_text(json.dumps(release_descriptor()))
            args=[sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),'host','attach','--root',str(root),'--file',str(payload),'--loaded-release',str(loaded),'--operation-id','switch-project']
            result=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(read_task_index(old,'claude','s1')['task_ids'],[])
            retry=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(retry.returncode,0,retry.stdout+retry.stderr)
            self.assertEqual(read_task_index(old,'claude','s1')['task_ids'],[])
            newer_root=Path(temp)/'other-control'
            write_locator(old,'claude','s1',newer_root,'newer-binding')
            write_task_index(old,'claude','s1',newer_root,['new-task'])
            retry=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(retry.returncode,0,retry.stdout+retry.stderr)
            self.assertEqual(read_task_index(old,'claude','s1')['control_root'],str(newer_root.resolve()))
            self.assertEqual(read_task_index(old,'claude','s1')['task_ids'],['new-task'])
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
    def test_current_cli_transfer_between_relocated_packages(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);project=base/'project with spaces';project.mkdir()
            subprocess.run(['git','init','-q',str(project)],check=True)
            root=project/'.devflow/control'
            from workflow_lib.bootstrap import exclude_runtime
            exclude_runtime(project)
            state=host_state(str(project.resolve()));transact(root,0,'seed',{'kind':'fixture','payload':state})
            copied=base/'second plugin with spaces'
            shutil.copytree(ROOT,copied,ignore=shutil.ignore_patterns('.git','.worktrees','.superpowers','__pycache__'))
            entries=[ROOT/'skills/workflow/scripts/run.py',copied/'skills/workflow/scripts/run.py']
            def cli(entry,*args):
                result=subprocess.run([sys.executable,'-B',str(entry),*map(str,args)],cwd=project,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr);return json.loads(result.stdout)
            def write(name,value):p=root/name;p.write_text(json.dumps(value));return p
            loaded=write('loaded.json',cli(entries[0],'version'))
            first=attachment(str(project.resolve()));first.pop('release')
            cli(entries[0],'host','attach','--root',root,'--file',write('source.json',first),'--loaded-release',loaded,'--operation-id','source')
            cli(entries[0],'host','handoff-prepare','--root',root,'--file',write('prepare.json',{'binding_id':'b1','revision':1,'handoff_id':'h','target_host':'claude','target_actor_id':'a2','target_session_id':'s2'}),'--operation-id','prepare')
            target=attachment(str(project.resolve()),binding_id='b2',host='claude',session_id='s2',actor_id='a2');target.pop('release')
            result=cli(entries[1],'host','handoff-accept','--root',root,'--file',write('accept.json',{'handoff_id':'h','destination':target}),'--loaded-release',loaded,'--operation-id','accept')
            self.assertEqual(result['binding_id'],'b2')
            self.assertEqual(read_state(root)['data']['runs']['run']['active_attempt']['token'],'t')
            self.assertEqual(read_state(root)['data']['host_bindings']['b1']['status'],'transferred')
            accept_retry=cli(entries[1],'host','handoff-accept','--root',root,'--file',root/'accept.json','--loaded-release',loaded,'--operation-id','accept')
            self.assertTrue(accept_retry['replayed'])
            source_retry=cli(entries[0],'host','attach','--root',root,'--file',root/'source.json','--loaded-release',loaded,'--operation-id','source')
            self.assertTrue(source_retry['replayed'])
            self.assertEqual(read_state(root)['data']['host_bindings']['b1']['status'],'transferred')
            self.assertEqual(subprocess.check_output(['git','status','--porcelain'],cwd=project),b'')
