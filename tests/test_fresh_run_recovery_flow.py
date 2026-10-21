"""Offline real-Git/CLI lifecycle; reviewer seats are fixtures, not live host reviews."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib.specs import content_hash
from workflow_lib.store import transact,read_state,WorkflowError
from workflow_lib.evidence import _report,capture_evidence
ENTRY=ROOT/'skills/workflow/scripts/run.py'


class FreshRunRecoveryFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='devflow recovery 東京 ');self.addCleanup(self.temp.cleanup)
        self.repo=Path(self.temp.name).resolve()/'application';self.repo.mkdir();self.control=Path(self.temp.name).resolve()/'control'
        self.env={**os.environ,'PYTHONUTF8':'1'}
        self.git('init','-q');self.git('config','user.email','test@example.test');self.git('config','user.name','Fixture')
        (self.repo/'tests').mkdir()
        for index in range(1,4):
            (self.repo/f'app_w{index}.py').write_text('def value(): return None\n',encoding='utf-8')
            expected="['ok']" if index==1 else str(index)
            (self.repo/'tests'/f'W{index}.py').write_text(f'def check(value): return value == {expected}\n',encoding='utf-8')
        (self.repo/'runner.py').write_text("import importlib.util,json,sys\nfrom pathlib import Path\ndef load(path,name):\n s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m\nitem=sys.argv[1]\napp=load(Path('app_'+item.lower()+'.py'),'app')\ntest=load(Path('tests')/(item+'.py'),'test')\nok=test.check(app.value())\nprint(json.dumps({'tests':[{'id':item+'.target','outcome':'passed' if ok else 'failed'}]}))\nsys.exit(0 if ok else 1)\n",encoding='utf-8')
        self.git('add','.');self.git('commit','-qm','base');self.base=self.git('rev-parse','HEAD')
        spec={'mode':'new','requirements':[{'id':f'R{i}','text':f'Feature {i}','acceptance_criteria':[f'W{i} target passes'],
            'provenance':{'kind':'authored'}} for i in range(1,4)]}
        plan={'spec_hash':content_hash(spec),'work_items':[{'id':f'W{i}','kind':'code','repo_id':'app',
            'requirement_ids':[f'R{i}'],'dependencies':[],'acceptance_criteria':[{'kind':'code-test','text':f'W{i} target passes'}]} for i in range(1,4)]}
        transact(self.control,0,'seed',{'kind':'fixture','payload':{'spec':spec,'approval':{'confirmed':True,'content_hash':content_hash(spec)},
            'plan':plan,'plan_validation':{'valid':True,'spec_hash':content_hash(spec)},'repositories':{'app':{'location':str(self.repo)}}}})
    def git(self,*args):
        result=subprocess.run(['git',*args],cwd=self.repo,capture_output=True,text=True,encoding='utf-8',env=self.env)
        self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
    def cli(self,*args,ok=True):
        result=subprocess.run([sys.executable,str(ENTRY),*map(str,args)],capture_output=True,text=True,encoding='utf-8',env=self.env)
        self.assertEqual(result.returncode,0 if ok else 2,result.stdout+result.stderr)
        return json.loads(result.stdout)
    def run_cli(self,operation,*args,**kw):return self.cli('run',operation,'--root',self.control,'--run-id','flow',*args,**kw)
    def verify(self,item,token,phase,red=None):
        argv=['build','verify','--root',self.control,'--run-id','flow','--attempt-id',token,'--phase',phase,
            '--argv-json',json.dumps([sys.executable,'-B','runner.py',item]),'--test-path',f'tests/{item}.py',
            '--test-path','runner.py','--target-id',item+'.target']
        if red:argv+=['--red-proof-id',red]
        result=self.cli(*argv);self.assertTrue(result['passed'],result);self.assertEqual(result['id'],result['proof_id']);return result['proof_id']
    def result(self,token,proof):return self.run_cli('result','--attempt-id',token,'--result',json.dumps({'outcome':'passed','verifier_proof_id':proof}))
    def repos(self):return {'app':{'location':str(self.repo),'base':self.base,'head':self.git('rev-parse','HEAD')}}
    def review(self,role,item=None,changes=False):
        args=['review','package','--root',self.control,'--run-id','flow','--role',role,'--repositories-json',json.dumps(self.repos())]
        if item:args+=['--item',item,'--input-paths-json',json.dumps({'app':[f'app_{item.lower()}.py',f'tests/{item}.py','runner.py']})]
        pkg=self.cli(*args)['package']
        report={'package_hash':pkg['package_hash'],'verdict':'request-changes' if changes else 'pass',
                'findings':[{'id':'F1','severity':'important','path':'app_w1.py','line':1,'message':'Return an independent result for each caller.'}] if changes else []}
        if item:report['item_id']=item
        self.cli('review','record','--root',self.control,'--run-id','flow','--package-hash',pkg['package_hash'],
            '--actor-id',role+'-reviewer','--invocation-ref','fixture://'+pkg['package_hash'],'--tool-available','--report-json',json.dumps(report))
        return pkg['package_hash']
    def test_one_run_three_items_review_fix_and_final_delivery_without_file_swapping(self):
        self.run_cli('start','--actor-id','implementer')
        red={}
        for index in range(1,4):
            item=f'W{index}';token=self.run_cli('next','--item',item)['attempt_id'];red[item]=self.verify(item,token,'red')
            code="RESULT=['ok']\ndef value(): return RESULT\n" if index==1 else f'def value(): return {index}\n'
            (self.repo/f'app_w{index}.py').write_text(code,encoding='utf-8')
            self.git('add','.');self.git('commit','-qm',f'Implement {item}\n\nWork-Item: {item}')
            self.result(token,self.verify(item,token,'green'))
        self.assertIn('W1',self.run_cli('gate-status')['unverified_items'])
        for item in ('W1','W2'):
            token=self.run_cli('reverify','--item',item)['attempt_id'];self.result(token,self.verify(item,token,'green',red[item]))
        self.review('item','W1',changes=True)
        for rebuild in (False,True):
            if rebuild:(self.control/'state.json').unlink()
            gate=self.run_cli('gate-status')
            self.assertEqual(gate['stage'],'implementation')
            self.assertIn('W1',gate['unverified_items'])
        token=self.run_cli('retry','--item','W1')['attempt_id']
        (self.repo/'app_w1.py').write_text("def value(): return ['ok']\n",encoding='utf-8')
        self.git('add','.');self.git('commit','-qm','Fix isolation\n\nWork-Item: W1')
        self.result(token,self.verify('W1',token,'green',red['W1']))
        for item in ('W2','W3'):
            token=self.run_cli('reverify','--item',item)['attempt_id'];self.result(token,self.verify(item,token,'green',red[item]))
        for item in ('W1','W2','W3'):self.review('item',item)
        self.review('branch');acceptance=self.review('acceptance')
        report={'package_hash':acceptance,'requirements':[{'id':f'R{i}','verdict':'MET',
            'citations':[{'repo_id':'app','path':f'app_w{i}.py','line':1}]} for i in range(1,4)]}
        self.run_cli('accept','--report-json',json.dumps(report),'--repositories-json',json.dumps(self.repos()))
        self.assertEqual(self.run_cli('gate-status')['stage'],'delivery')
        manifest=self.cli('delivery','prepare','--root',self.control,'--run-id','flow','--repositories-json',json.dumps(self.repos()),'--outcome','retained-branch')
        manifest_file=Path(self.temp.name)/'manifest.json';manifest_file.write_text(json.dumps(manifest),encoding='utf-8')
        checked=self.cli('delivery','verify','--root',self.control,'--run-id','flow','--manifest-file',manifest_file,
            '--confirm-hash',manifest['manifest_hash'],'--repositories-json',json.dumps(self.repos()))
        manifest_file.write_text(json.dumps(checked),encoding='utf-8')
        actual={'authorization':{'approved':True,'actor_id':'owner','manifest_hash':manifest['manifest_hash'],'action':'delivery.retained-branch'},
            'outcome':'retained-branch','repository_heads':{'app':self.git('rev-parse','HEAD')}}
        actual_file=Path(self.temp.name)/'actual.json';actual_file.write_text(json.dumps(actual),encoding='utf-8')
        delivered=self.cli('delivery','record','--root',self.control,'--run-id','flow','--manifest-file',manifest_file,'--actual-result-file',actual_file)
        self.assertEqual(delivered['status'],'delivered')
        data=read_state(self.control)['data'];self.assertEqual(list(data['runs']),['flow'])
        run=data['runs']['flow'];self.assertTrue(all(item['status']=='complete' for item in run['items'].values()))
        self.assertFalse(any(attempt['status']=='abandoned' for item in run['items'].values() for attempt in item['attempts']))
        self.assertTrue(all((self.repo/f'app_w{i}.py').is_file() for i in range(1,4)))
        self.assertEqual(run['actors']['item_reviewer'],'item-reviewer')
    def test_shipped_runner_examples_parse_to_the_same_non_python_target(self):
        examples=ROOT/'docs/examples'
        json_text=(examples/'target-test-report.json').read_text(encoding='utf-8')
        xml=(examples/'target-test-report.junit.xml').read_text(encoding='utf-8')
        self.assertEqual(_report(json_text,'','json'),{'sync.upserts_existing_row':'failed'})
        self.assertEqual(_report(xml,'','junit'),{'sync.upserts_existing_row':'failed'})
        prior=json.loads((examples/'prior-findings.json').read_text(encoding='utf-8'))
        self.assertEqual(prior[0]['severity'],'important');self.assertEqual(prior[0]['item_id'],'W1')
    def test_import_failure_without_target_results_is_not_red(self):
        self.run_cli('start','--actor-id','implementer');token=self.run_cli('next','--item','W1')['attempt_id']
        result=capture_evidence(self.control,'flow',token,'RED',[sys.executable,'-c','raise ImportError("fixture")'],
            ['tests/W1.py'],['W1.target'],10)
        self.assertFalse(result['passed']);self.assertNotIn('id',result)

    def test_malformed_prior_findings_are_rejected_without_mutation(self):
        from workflow_lib.reviews import prepare_review
        run={'id':'fixture','plan':{'spec_hash':'spec','work_items':[]},'artifacts':{}}
        repos=self.repos()
        for prior in ('not-an-array',[{'item_id':'W1'}],[{'id':'F1','severity':'low'}],[{'id':'F1'},{'id':'F1'}]):
            with self.subTest(prior=prior),self.assertRaises(ValueError):prepare_review(run,'branch',repos,prior)

    def test_deployment_prompts_are_guidance_for_unresolved_existing_topics(self):
        from workflow_lib.ground_interview import inspect_ground_interview,TOPICS
        missing=inspect_ground_interview(self.repo)
        self.assertIn('cached', ' '.join(missing['prompts']['deployment-release']).lower())
        self.assertIn('version', ' '.join(missing['prompts']['performance-reliability']).lower())
        (self.repo/'docs').mkdir()
        answered={'schema_version':1,'topics':{name:{'status':'not-applicable','material':False,'reason':'Fixture excludes this topic.'} for name in TOPICS}}
        (self.repo/'docs/devflow-ground-interview.json').write_text(json.dumps(answered),encoding='utf-8')
        ready=inspect_ground_interview(self.repo)
        self.assertTrue(ready['ready']);self.assertEqual(ready['prompts'],{})
