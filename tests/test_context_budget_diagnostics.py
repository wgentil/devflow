import copy
import tempfile
from pathlib import Path
import unittest
import test_task_views
from large_context_fixtures import make_context_project
from workflow_lib.document_units import canonical
from workflow_lib.store import WorkflowError,read_state,transact
from workflow_lib.lifecycle_hooks import run_lifecycle_hook

class ContextBudgetTests(unittest.TestCase):
    def setUp(self):
        self.f=test_task_views.TaskViewTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_exact_utf8_component_total(self):
        value=self.f.build();parts=value['budget']['component_bytes']
        self.assertEqual(parts['serialized_bytes'],len(canonical(value)))
        self.assertEqual(sum(n for k,n in parts.items() if k!='serialized_bytes'),len(canonical(value)))
        for key in ('requirements','shared_spec','governing','stage_documents','control_envelope','artifact_references','optional','serialization_overhead'):self.assertGreaterEqual(parts[key],0)
        self.assertGreater(parts['requirements'],len('こんにちは'))
    def test_optional_reference_overhead_reserved(self):
        (self.f.root/'extra.md').write_text('OPTIONAL'*160,encoding='utf-8');self.f.sources['extra']={'root':str(self.f.root),'path':'extra.md'}
        self.f.selection['documents'].append({'source_id':'extra','required':False})
        full=self.f.build();budget=full['budget']['serialized_bytes']-50
        value=self.f.build(max_bytes=budget)
        self.assertLessEqual(len(canonical(value)),budget);self.assertIn('extra',value['budget']['optional_omitted'])
    def test_unrelated_requirements_excluded_shared_unknowns_preserved(self):
        self.f.selection['spec']['shared_contract']={'rule':'Preserve the unknown shared decision.'}
        for representation in ('markdown','json'):
            value=self.f.build(representation=representation);text=canonical(value).decode()
            self.assertIn('Preserve the unknown shared decision.',text);self.assertNotIn('Unselected requirement',text)
    def test_large_required_rule_remains_blocking(self):
        (self.f.root/'rules.md').write_text('# Rules\n## G1: Safety\n'+'必須'*10000+'\n## G2: Optional\nOther',encoding='utf-8')
        with self.assertRaises(WorkflowError) as caught:self.f.build()
        self.assertEqual(caught.exception.code,'CONTEXT_BUDGET_EXCEEDED')
        self.assertGreater(caught.exception.details['component_bytes']['governing'],20000)
    def test_error_fits_hook_budget(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);f=make_context_project(Path(temp.name)/'project')
        spec=copy.deepcopy(f['state']['data']['spec']);spec['requirements'][0]['text']='PRIVATE_DETAIL'*5000
        from workflow_lib.repo_specs import write_spec_pair
        from workflow_lib.specs import content_hash
        pair={'repo_id':'app',**write_spec_pair(f['repo'],'docs/spec.json',spec,overwrite=True)}
        runs=copy.deepcopy(f['state']['data']['runs']);runs['current']['plan']['spec_hash']=content_hash(spec)
        transact(f['root'],f['state']['version'],'large-spec',{'kind':'fixture','payload':{'spec':spec,'spec_pair':pair,'approval':{**pair,'confirmed':True},'runs':runs}})
        response=run_lifecycle_hook('prepare-context',{'root':str(f['root']),'run_id':'current','item_ids':['W1']},required=True)
        self.assertEqual(response['reason_code'],'CONTEXT_BUDGET_EXCEEDED');self.assertLessEqual(len(canonical(response)),8192)
        self.assertEqual(response['details']['phase'],'composition');self.assertNotIn('PRIVATE_DETAIL',canonical(response).decode())

    def test_selected_brief_excludes_unrelated_attempt_result(self):
        from workflow_lib.briefs import assemble_brief
        from workflow_lib.runs import issue_attempt,record_result
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);f=make_context_project(Path(temp.name)/'project')
        run=issue_attempt(f['run'],'W2');token=run['active_attempt']['token']
        run=record_result(run,token,{'outcome':'failed','note':'UNRELATED_HISTORY'*3000})
        value=assemble_brief(run,{}, {'name':'implementation','required_slices':[]},['W1'],20000)
        self.assertNotIn('UNRELATED_HISTORY',canonical(value).decode())
        self.assertNotIn('W2',value['latest_attempts'])
