"""Issue #2 regressions: replay and byte overflow are independent failures."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from large_context_fixtures import make_context_project
from workflow_lib.store import read_state,transact,WorkflowError
from workflow_lib.task_views import prepare_task_view
from workflow_lib.lifecycle_hooks import execute_hook
from workflow_lib.document_units import canonical

class LargeContextPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
    def project(self,name='project',**kw):return make_context_project(self.base/name,**kw)
    def test_unchanged_preparation_does_not_replay_inside_worker(self):
        f=self.project();calls=[];original=read_state
        def counted(root):calls.append(str(root));return original(root)
        # Root/run worker requests must no longer replay the entire journal.
        with patch('workflow_lib.store.read_state',side_effect=counted),patch('workflow_lib.task_views.read_state',side_effect=counted),patch('workflow_lib.repo_input_gate.read_state',side_effect=counted),patch('workflow_lib.document_approvals.read_state',side_effect=counted):
            try:execute_hook('prepare-context',{'root':str(f['root']),'run_id':'current','item_ids':['W1']},max_bytes=8192,deadline_seconds=5)
            except WorkflowError:pass # New worker route rejects an unscoped request.
        self.assertEqual(calls,[],'Journal replay must occur in parent preflight, never the bounded worker.')
    def test_history_is_not_selected_context(self):
        small=self.project('small');large=self.project('large',delivered_runs=4,event_count=30,history_bytes=100000)
        views=[prepare_task_view(f['root'],f['run'],{'run_id':'current'},['W1']) for f in (small,large)]
        self.assertEqual(views[0]['task_view']['units'],views[1]['task_view']['units'])
        self.assertEqual(views[0]['budget']['serialized_bytes'],views[1]['budget']['serialized_bytes'])
        self.assertNotIn('historical-',canonical(views[1]).decode())
    def test_selected_requirement_and_shared_facts_budgeted_separately(self):
        f=self.project();raw=copy.deepcopy(f['state']['data']['spec']);raw['requirements'][1]['text']='UNRELATED_SENTINEL'*2000
        from workflow_lib.repo_specs import write_spec_pair
        from workflow_lib.specs import content_hash
        pair={'repo_id':'app',**write_spec_pair(f['repo'],'docs/spec.json',raw,overwrite=True)}
        state=read_state(f['root']);runs=copy.deepcopy(state['data']['runs']);runs['current']['plan']['spec_hash']=content_hash(raw)
        transact(f['root'],state['version'],'larger-spec',{'kind':'fixture','payload':{'spec':raw,'spec_pair':pair,'approval':{**pair,'confirmed':True},'runs':runs}})
        for representation in ('markdown','json'):
            value=prepare_task_view(f['root'],runs['current'],{'run_id':'current'},['W1'],representation=representation)
            self.assertNotIn('UNRELATED_SENTINEL',canonical(value).decode());self.assertIn('Shared',canonical(value).decode())
            self.assertLessEqual(value['budget']['serialized_bytes'],20000)
    def test_real_required_overflow_reports_components(self):
        f=self.project();spec=copy.deepcopy(f['state']['data']['spec']);spec['requirements'][0]['text']='必要'*11000
        from workflow_lib.repo_specs import write_spec_pair
        from workflow_lib.specs import content_hash
        pair={'repo_id':'app',**write_spec_pair(f['repo'],'docs/spec.json',spec,overwrite=True)}
        state=read_state(f['root']);runs=copy.deepcopy(state['data']['runs']);runs['current']['plan']['spec_hash']=content_hash(spec)
        transact(f['root'],state['version'],'oversized-spec',{'kind':'fixture','payload':{'spec':spec,'spec_pair':pair,'approval':{**pair,'confirmed':True},'runs':runs}})
        with self.assertRaises(WorkflowError) as caught:prepare_task_view(f['root'],runs['current'],{'run_id':'current'},['W1'])
        self.assertEqual(caught.exception.code,'CONTEXT_BUDGET_EXCEEDED');self.assertIn('component_bytes',caught.exception.details)
        self.assertGreater(caught.exception.details['required_bytes'],20000);self.assertIsNone(read_state(f['root'])['data']['runs']['current']['active_attempt'])
