import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib.document_units import digest


class RoutingEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.policy={'version':'fixture','task_routing':{'schema_version':1}}
        scope={'host':'codex','host_version':'1.2.3','model_id':'fixture','model_revision':'r1',
               'effort':'medium','execution_path':'isolated-native','policy_hash':digest(self.policy)}
        body={'case_id':'discovery','approved_by':'fixture-reviewer','scoring_version':1,
              'kind':'discovery','required_ids':['R1'],'required_facts':['Required behavior'],'binding':scope}
        self.cases=[{**body,'case_hash':digest(body)}]
        self.results=[{'case_id':'discovery','case_hash':self.cases[0]['case_hash'],'binding':scope,
            'passed':True,'supplied_ids':['R1'],'supplied_facts':['Required behavior'],
            'findings':[],'retries':0,'escalations':0,'duration_ms':3,'context_bytes':1000}]
    def evaluate(self,results=None,cases=None):
        from workflow_lib.routing_evaluation import evaluate_routing
        return evaluate_routing(self.cases if cases is None else cases,self.results if results is None else results,self.policy)
    def test_missing_facts_fail_even_when_payload_is_smaller(self):
        report=self.evaluate();self.assertEqual(report['status'],'passed')
        smaller={**self.results[0],'context_bytes':1,'supplied_facts':[]}
        report=self.evaluate([smaller]);self.assertEqual(report['status'],'failed')
        self.assertEqual(report['cases'][0]['missing_facts'],['Required behavior'])
        self.assertIsNone(report['cost_usd'])
    def test_drift_or_missing_case_does_not_establish_comparable_success(self):
        for field in ('policy_hash','model_revision','host_version','model_id','execution_path'):
            with self.subTest(field=field):
                row=copy.deepcopy(self.results[0]);row['binding'][field]='changed'
                self.assertEqual(self.evaluate([row])['status'],'failed')
        self.assertEqual(self.evaluate([])['coverage'],0)
        self.assertNotEqual(self.evaluate([],[])['status'],'passed')
    def test_unreviewed_changed_or_duplicate_cases_are_invalid(self):
        for rows in ([{**self.cases[0],'approved_by':None}],self.cases*2,
                     [{**self.cases[0],'required_facts':[]} ]):
            with self.subTest(rows=rows):self.assertEqual(self.evaluate(cases=rows)['status'],'failed')
    def test_evaluation_never_executes_providers_and_is_not_suitability_promotion(self):
        from unittest.mock import patch
        from workflow_lib.model_validation import promotion_decision
        with patch('subprocess.run',side_effect=AssertionError('offline only')):
            report=self.evaluate()
        self.assertEqual(report['status'],'passed')
        self.assertFalse(report['promotion_eligible'])
        self.assertNotEqual(promotion_decision(report,{'version':'fixture','thresholds':{}})['status'],'eligible')
    def test_statistics_deduplicate_operations_and_disclose_usage_gaps(self):
        from workflow_lib.routing_evaluation import routing_statistics
        routing={'task_facts':{'task_id':'T1'},'escalation_index':1,'known_payload':{'known_payload_bytes':100}}
        record={'operation_id':'same','scope':{'run_id':'run','stage':'implementation'},
                'status':'completed','decision':{'routing':routing},'result':{'status':'completed','usage':{'input_tokens':10,'output_tokens':2}}}
        data={'runs':{'run':{'native_invocations':{'i':record,'duplicate':copy.deepcopy(record)}}}}
        value=routing_statistics(data,{})
        self.assertEqual(value['invocations'],1)
        self.assertEqual(value['runtime_usage']['input_tokens'],10)
        self.assertEqual(value['escalations'],1)
        self.assertIsNone(value['cost_usd'])
        self.assertEqual(routing_statistics(data,{'task_id':'other'})['invocations'],0)

    def test_cli_routing_projection_and_optional_model_evaluation_are_read_only(self):
        import subprocess,tempfile
        from workflow_lib.store import transact,read_state
        actual_policy=json.loads((ROOT/'definitions/model-policy.json').read_text())
        case=copy.deepcopy(self.cases[0]);case['binding']['policy_hash']=digest(actual_policy)
        case['case_hash']=digest({key:value for key,value in case.items() if key!='case_hash'})
        row={**self.results[0],'binding':case['binding'],'case_hash':case['case_hash']}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{},'improvement_cases':{'discovery':case}}})
            runner=[sys.executable,str(ROOT/'skills/workflow/scripts/run.py')]
            response=subprocess.run(runner+['stats','routing','--root',str(root)],text=True,capture_output=True)
            self.assertEqual(response.returncode,0,response.stderr)
            self.assertEqual(json.loads(response.stdout)['invocations'],0)
            request={'host':'codex','model_id':'fixture','host_version':'1.2.3','case_ids':[],
                     'routing_evaluation':{'case_ids':['discovery'],'results':[row]}}
            file=root/'eval.json';file.write_text(json.dumps(request))
            response=subprocess.run(runner+['improve','model-evaluate','--root',str(root),'--input',str(file)],text=True,capture_output=True)
            self.assertEqual(response.returncode,0,response.stderr)
            value=json.loads(response.stdout)
            self.assertEqual(value['routing_report']['status'],'passed')
            self.assertNotEqual(value['decision']['status'],'eligible')
            self.assertEqual(read_state(root)['version'],1)

    def test_fixed_fixture_cases_fail_independently_when_required_facts_disappear(self):
        from workflow_lib.routing_evaluation import evaluate_routing
        fixture=json.loads((ROOT/'tests/fixtures/task-routing/cases.json').read_text())
        self.assertEqual({row['kind'] for row in fixture['cases']},{'discovery','implementation','debugging','review'})
        self.assertEqual(evaluate_routing(fixture['cases'],fixture['results'],fixture['policy'])['status'],'passed')
        for index in range(4):
            rows=copy.deepcopy(fixture['results']);rows[index]['supplied_facts']=[];rows[index]['context_bytes']=1
            self.assertEqual(evaluate_routing(fixture['cases'],rows,fixture['policy'])['status'],'failed')

    def test_existing_reviewed_case_snapshot_hash_and_expected_routing_are_preserved(self):
        from workflow_lib.routing_evaluation import evaluate_routing
        from workflow_lib.improvement_cases import propose_case
        expected={key:value for key,value in self.cases[0].items() if key not in {'case_id','case_hash','approved_by','scoring_version'}}
        proposed=propose_case({'run_id':'run'},{'owner':'host-adapter','observation':'Routing must retain R1',
            'command':['python3','fixture.py'],'expected':{'routing':expected},'scoring_version':1})
        approved={**proposed,'approved_by':'independent-reviewer','feedback_id':'f'}
        row={**self.results[0],'case_id':approved['case_id'],'case_hash':approved['case_hash']}
        self.assertEqual(evaluate_routing([approved],[row],self.policy)['status'],'passed')
        changed=copy.deepcopy(approved);changed['expected']['routing']['required_facts']=[]
        self.assertEqual(evaluate_routing([changed],[row],self.policy)['status'],'failed')
