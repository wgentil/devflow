import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.context import record_slice, remove_location
from workflow_lib.store import WorkflowError

class ContextLifecycleTests(unittest.TestCase):
    def test_interview_decline_mode_sync(self):
        state={'context':{'project':{'slices':{'architecture':{'status':'declined','reason':'unknown'}}}},'projections':{'p':1}}
        state=record_slice(state,'project','architecture',{'status':'declined','reason':'unknown'})
        self.assertEqual(state['context']['project']['slices']['architecture']['status'],'declined')
        state=record_slice(state,'project','testing',{'status':'answered','value':'pytest'})
        self.assertIsNone(state['resolved_context'])
    def test_location_removal_reference_safety(self):
        with tempfile.TemporaryDirectory() as d:
            state={'repositories':{'r':{'location':d}},'runs':{'x':{'status':'active','plan':{'work_items':[{'repo_id':'r'}]}}}}
            with self.assertRaises(WorkflowError): remove_location(state,'r')
