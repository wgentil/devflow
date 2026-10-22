import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from large_context_fixtures import make_context_project
from workflow_lib.briefs import assemble_brief
from workflow_lib.document_units import canonical
from workflow_lib.lifecycle_hooks import prepared_context
from workflow_lib.store import read_state,transact,WorkflowError

class OptionalContextBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.f=make_context_project(Path(self.temp.name)/'project');self.root=self.f['root']
    def configure(self,size,required='Keep this required decision.'):
        state=read_state(self.root);runs=copy.deepcopy(state['data']['runs']);run=runs['current']
        run['plan']['stage']={'name':'implementation','required_slices':['platform'],'optional_slices':['extra']}
        run['context']={'values':{'platform':required,'extra':'OPTIONAL'*((size+7)//8)},'provenance':{'platform':'project','extra':'project'}}
        transact(self.root,state['version'],'optional-fixture',{'kind':'fixture','payload':{'runs':runs}})
        return run
    def view(self,run):
        envelope=assemble_brief(run,run['context'],run['plan']['stage'],['W1'],20000)
        return prepared_context(self.root,run,envelope,['W1'],stage='implementation')
    def test_cli_drops_optional_slice_when_only_combined_view_overflows(self):
        self.configure(10000)
        path=Path(__file__).resolve().parents[1]/'skills/workflow/scripts/run.py'
        spec=importlib.util.spec_from_file_location('optional_entry',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        output=io.StringIO()
        with redirect_stdout(output):code=module.main(['run','next','--root',str(self.root),'--run-id','current','--item','W1','--operation-id','optional-next'])
        value=json.loads(output.getvalue());self.assertEqual(code,0,value)
        self.assertTrue(value['attempt_id']);self.assertNotIn('extra',value['context']['values']);self.assertNotIn('extra',value['context']['provenance'])
        self.assertEqual(value['context']['values']['platform'],'Keep this required decision.')
        self.assertIn('extra',value['budget']['optional_omitted']);self.assertLessEqual(len(canonical(value)),20000)
        self.assertEqual(value['budget']['component_bytes']['optional'],0)
    def test_retained_optional_slice_bytes_are_classified(self):
        value=self.view(self.configure(100));parts=value['budget']['component_bytes']
        self.assertIn('extra',value['context']['values']);self.assertGreater(parts['optional'],100)
        self.assertEqual(parts['serialized_bytes'],len(canonical(value)))
        self.assertEqual(sum(n for key,n in parts.items() if key!='serialized_bytes'),len(canonical(value)))
    def test_required_slice_remains_mandatory_when_optional_is_also_present(self):
        run=self.configure(1000,required='REQUIRED'*1600)
        with self.assertRaises(WorkflowError) as caught:self.view(run)
        self.assertEqual(caught.exception.code,'CONTEXT_BUDGET_EXCEEDED')
        self.assertGreater(caught.exception.details['required_bytes'],20000)
        self.assertIsNone(read_state(self.root)['data']['runs']['current']['active_attempt'])
