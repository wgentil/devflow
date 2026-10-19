import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.hosts import apply_host_event, binding_for_session, validate_binding
from workflow_lib.host_locators import write_locator, read_locator, locator_path
from workflow_lib.releases import release_descriptor
from workflow_lib.store import WorkflowError, transact, read_state

def host_state(project='/tmp/project'):
    from workflow_lib.specs import content_hash
    spec = {'mode': 'new', 'requirements': [{'id': 'R1', 'title': 'Fixture behavior',
        'text': 'Fixture required behavior', 'acceptance_criteria': ['fixture target passes'], 'provenance': {'kind': 'authored'}}]}
    spec_hash = content_hash(spec)
    return {'spec': spec, 'approval': {'confirmed': True, 'content_hash': spec_hash},
        'repositories':{'repo':{'location':project}}, 'runs':{'run':{
        'id':'run', 'host_protocol_version':1, 'actors':{'implementer':'original'}, 'repositories':{'repo':{'location':project}},
        'plan':{'spec_hash': spec_hash, 'work_items':[{'id':'W1','kind':'code','requirement_ids':['R1']}]},
        'items':{'W1':{'status':'pending','attempts':[{'token':'t'}]}},
        'active_attempt':{'item_id':'W1','token':'t'},'status':'active'}}}

def attachment(project='/tmp/project', **overrides):
    return {'binding_id':'b1','host':'codex','session_id':'s1','actor_id':'a1','role':'implementer',
            'run_id':'run','project_dir':project,'release':release_descriptor(), **overrides}

class HostTests(unittest.TestCase):
    def setUp(self): self.state=host_state()
    def test_owner_conflict_and_reviewer_coexistence(self):
        first=apply_host_event(self.state,'attach',attachment())
        self.assertEqual(first['revision'],1)
        with self.assertRaises(WorkflowError): apply_host_event(self.state,'attach',attachment(binding_id='b2',session_id='s2'))
        self.state['runs']['run']['review_packages']={'pkg':{'role':'item','package_hash':'pkg'}}
        apply_host_event(self.state,'attach',attachment(binding_id='review',session_id='rs',actor_id='reviewer',role='item-reviewer',item_id='W1',package_hash='pkg'))
        self.assertEqual(len(self.state['host_bindings']),2)
    def test_new_run_retires_delivered_session_binding(self):
        prior=apply_host_event(self.state,'attach',attachment())
        apply_host_event(self.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'})
        self.state['runs']['run']['status']='delivered'
        self.state['runs']['next']={**copy.deepcopy(self.state['runs']['run']),'id':'next','status':'active'}
        current=apply_host_event(self.state,'attach',attachment(binding_id='b2',run_id='next'))
        self.assertEqual((prior['revision'],current['revision']),(1,1))
        self.assertEqual(self.state['host_bindings']['b1']['status'],'detached')
        self.assertEqual(self.state['host_bindings']['b1']['revision'],2)
        self.assertEqual(binding_for_session(self.state,'codex','s1')['binding_id'],'b2')
        self.assertEqual(self.state['runs']['run']['status'],'delivered')
        self.assertFalse(self.state.get('host_tasks'))
        mapped=apply_host_event(self.state,'task-bind',{'binding_id':'b2','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'})
        self.assertEqual(mapped['run_id'],'next')
    def test_terminal_switch_blocks_running_worker_without_retiring_binding(self):
        apply_host_event(self.state,'attach',attachment())
        self.state['runs']['run']['status']='delivered'
        self.state['runs']['run']['native_invocations']={'work':{'status':'running','scope':{'binding_id':'b1'}}}
        self.state['runs']['next']={**copy.deepcopy(self.state['runs']['run']),'id':'next','status':'active'}
        with self.assertRaises(WorkflowError) as caught:
            apply_host_event(self.state,'attach',attachment(binding_id='b2',run_id='next'))
        self.assertEqual(caught.exception.code,'NATIVE_INVOCATION_ACTIVE')
        self.assertEqual(self.state['host_bindings']['b1']['status'],'active')
        self.assertNotIn('b2',self.state['host_bindings'])
    def test_old_implementer_cannot_review(self):
        self.state['runs']['run']['review_packages']={'pkg':{'role':'item'}}
        with self.assertRaises(WorkflowError): apply_host_event(self.state,'attach',attachment(role='item-reviewer',actor_id='original',item_id='W1',package_hash='pkg'))
    def test_task_mapping_and_stale_revision(self):
        apply_host_event(self.state,'attach',attachment())
        mapped=apply_host_event(self.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'})
        self.assertEqual(mapped['token'],'t')
        with self.assertRaises(WorkflowError): validate_binding(self.state,'b1',99)
        apply_host_event(self.state,'detach',{'binding_id':'b1','revision':1})
        with self.assertRaises(WorkflowError): validate_binding(self.state,'b1',1)
        self.assertIsNone(binding_for_session(self.state,'codex','s1'))
        self.assertEqual(self.state['runs']['run']['active_attempt']['token'],'t')
    def test_mismatching_project_session_and_task(self):
        with self.assertRaises(WorkflowError): apply_host_event(self.state,'attach',attachment(project_dir='/tmp/other'))
        apply_host_event(self.state,'attach',attachment())
        with self.assertRaises(WorkflowError): apply_host_event(self.state,'attach',attachment(binding_id='another'))
        with self.assertRaises(WorkflowError): apply_host_event(self.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'wrong'})
    def test_locator_cache_is_rebuildable_and_session_hashed(self):
        with tempfile.TemporaryDirectory() as temp:
            project=Path(temp); root=project/'.devflow/control'
            write_locator(project,'claude','../session',root,'b1')
            value=read_locator(project,'claude','../session')
            self.assertEqual(value,{'control_root':str(root.resolve()),'binding_id':'b1'})
            path=locator_path(project,'claude','../session')
            self.assertTrue(path.is_relative_to(project.resolve()/'.devflow/hosts/claude'))
            path.write_text('{')
            with self.assertRaises(WorkflowError):read_locator(project,'claude','../session')
            write_locator(project,'claude','../session',root,'b1')
            self.assertEqual(read_locator(project,'claude','../session')['binding_id'],'b1')
    def test_journal_replay_and_operation_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            transact(root,0,'seed',{'kind':'fixture','payload':self.state})
            from argparse import Namespace
            from commands.journal import commit
            args=Namespace(root=str(root),operation_id='attach',operation_id_explicit=True,expected_version=None)
            first=commit(args,'domain.host.attach',attachment())
            retry=commit(args,'domain.host.attach',attachment())
            self.assertEqual(first['binding_id'],retry['binding_id']);self.assertTrue(retry['replayed'])
            with self.assertRaises(WorkflowError):commit(args,'domain.host.attach',attachment(actor_id='other'))
            args.operation_id='conflict';args.expected_version=0
            with self.assertRaises(WorkflowError):commit(args,'domain.host.detach',{'binding_id':'b1','revision':1})
            self.assertEqual(read_state(root)['data']['host_bindings']['b1']['status'],'active')
    def test_explicit_task_remap_after_rework_preserves_scope(self):
        from workflow_lib.journal_domains import digest
        apply_host_event(self.state,'attach',attachment())
        old=apply_host_event(self.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'t'})
        self.state['runs']['run']['items']['W1']['attempts'].append({'token':'new'})
        new=apply_host_event(self.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'item','item_id':'W1','token':'new','replace':True,'previous_mapping_hash':digest(old)})
        self.assertEqual(new['token'],'new')
        with self.assertRaises(WorkflowError):apply_host_event(self.state,'task-bind',{'binding_id':'b1','revision':1,'task_id':'task','scope':'delivery','replace':True,'previous_mapping_hash':digest(new)})
