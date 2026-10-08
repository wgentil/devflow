import json, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.usage import import_usage
from workflow_lib.pricing import store_prices,price_usage
from workflow_lib.reporting import rollup
from workflow_lib.store import read_state
from workflow_lib.ground_interview import TOPICS

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/workflow/scripts/run.py'


class RepositoryEvidenceFlowTests(unittest.TestCase):
 def test_org_url_separate_approvals_and_policy_drift_block_handoff(self):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory); project=base/'project'; org=base/'organization'
   for repo in (project,org):
    repo.mkdir(); subprocess.run(['git','init','-q',str(repo)],check=True)
   def commit(repo,message):
    subprocess.run(['git','-C',str(repo),'add','.'],check=True)
    subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.com','commit','-qm',message],check=True)
   (project/'README.md').write_text('A clean application repository.\n');commit(project,'Initial project')
   (org/'docs').mkdir();(org/'docs/policy.md').write_text('## CODE-1: Review changes\nEvery change needs a review.\n')
   (org/'docs/devflow-org.json').write_text(json.dumps({'schema_version':1,'id':'team','documents':[{'category':'coding-standards','path':'docs/policy.md','rule_ids':['CODE-1']}]})+'\n')
   commit(org,'Initial policy')
   root=project/'.devflow/control'
   def source(name,value):
    path=base/name;path.write_text(json.dumps(value));return path
   def call(*args, expected=0):
    process=subprocess.run([sys.executable,'-B',str(SCRIPT),*map(str,args)],cwd=project,capture_output=True,text=True)
    self.assertEqual(process.returncode,expected,process.stdout+process.stderr)
    return json.loads(process.stdout)
   inspected=call('setup','inspect','--project-dir',project)
   self.assertEqual(inspected['default'],'project-only')
   self.assertFalse((project/'docs/devflow-context.json').exists())
   setup=call('setup','initialize','--project-dir',project,'--choice',source('setup.json',{'mode':'attach-org','url':str(org)}),'--operation-id','setup')
   self.assertEqual(setup['portability'],'local-only')
   self.assertEqual(setup['manifest']['org']['id'],'team')
   (project/'docs/devflow-ground-interview.json').write_text(json.dumps({
    'schema_version':1,'topics':{name:{'status':'answered','material':True,'decision':'Fixture decision for '+name}
                                 for name in TOPICS}})+'\n')
   self.assertFalse(subprocess.run(['git','-C',str(project),'check-ignore','-q','.devflow/control'],check=False).returncode)
   call('repo','register','--root',root,'--repo-id','app','--location',project,'--operation-id','register-app')
   call('repo','register','--root',root,'--repo-id','team','--location',setup['org_checkout'],'--operation-id','register-team')
   spec={'mode':'new','title':'Greeting','requirements':[{'id':'R1','text':'Return a greeting','acceptance_criteria':['greet Ada returns Hello, Ada'],'provenance':{'kind':'authored'}}], 'gaps':[]}
   stored=call('spec','store','--root',root,'--file',source('spec.json',spec),'--repo-id','app','--path','docs/specs/greeting.json','--operation-id','store-spec')
   pair=stored['spec_pair'];self.assertTrue((project/pair['json_path']).is_file());self.assertTrue((project/pair['markdown_path']).is_file())
   plan={'spec_hash':stored['content_hash'],'work_items':[{'id':'W1','kind':'code','repo_id':'app','requirement_ids':['R1'],'dependencies':[],'acceptance_criteria':[{'kind':'code-test','text':'greeting test passes'}]}]}
   plan_file=source('plan.json',plan)
   self.assertEqual(call('plan','validate','--root',root,'--file',plan_file,'--operation-id','plan-too-early',expected=2)['error'],'SPEC_NOT_APPROVED')
   call('spec','approve','--root',root,'--confirm-hash',stored['content_hash'],'--actor-id','human-spec','--operation-id','approve-spec')
   blocked=call('plan','validate','--root',root,'--file',plan_file,'--operation-id','plan-needs-docs',expected=2)
   self.assertEqual(blocked['error'],'DOCUMENT_APPROVAL_REQUIRED')
   self.assertEqual(blocked['path'],'docs/devflow-context.json')
   proposal=call('document','propose','--root',root,'--repo-id','app','--paths','docs/devflow-context.json')
   self.assertIn('docs/devflow-context.json',proposal['files'])
   call('document','approve','--root',root,'--proposal-hash',proposal['proposal_hash'],'--actor-id','human-policy')
   self.assertIn('validation',call('plan','validate','--root',root,'--file',plan_file,'--operation-id','plan-approved'))
   self.assertEqual(read_state(root)['data']['governing_input_receipt']['applicable_rule_ids'],['CODE-1'])
   call('run','start','--root',root,'--run-id','run-1','--operation-id','run-start')
   first=call('run','next','--root',root,'--run-id','run-1','--operation-id','first-attempt')
   call('run','abandon','--root',root,'--run-id','run-1','--attempt-id',first['attempt_id'],'--operation-id','abandon-first')
   release=source('release.json',call('version'))
   owner={'binding_id':'owner','host':'codex','session_id':'source-session','actor_id':'implementer','role':'implementer','run_id':'run-1','project_dir':str(project)}
   call('host','attach','--root',root,'--file',source('owner.json',owner),'--loaded-release',release,'--operation-id','attach-owner')
   (Path(setup['org_checkout'])/'docs/policy.md').write_text('## CODE-1: Review changes\nEvery change needs two reviewers.\n')
   handoff={'binding_id':'owner','revision':1,'handoff_id':'handoff-1','target_host':'claude','target_actor_id':'next-implementer'}
   blocked=call('host','handoff-prepare','--root',root,'--file',source('handoff.json',handoff),'--operation-id','handoff-after-drift',expected=2)
   self.assertEqual(blocked['error'],'DOCUMENT_APPROVAL_REQUIRED')
   self.assertEqual(blocked['repo_id'],'team')
   self.assertEqual(read_state(root)['data']['host_bindings']['owner']['status'],'active')
   proposal=call('document','propose','--root',root,'--repo-id','team','--paths','docs/policy.md')
   call('document','approve','--root',root,'--proposal-hash',proposal['proposal_hash'],'--actor-id','human-policy')
   original_run=read_state(root)['data']['runs']['run-1']
   for attempt in range(2):
    blocked=call('run','next','--root',root,'--run-id','run-1','--operation-id',f'next-stale-{attempt}',expected=2)
    self.assertEqual(blocked['error'],'GOVERNING_REASSESSMENT_REQUIRED')
   self.assertTrue(read_state(root)['data']['governing_reassessment_required'])
   self.assertEqual(call('plan','validate','--root',root,'--file',plan_file,'--operation-id','missing-assessment',expected=2)['error'],'GOVERNING_REASSESSMENT_REQUIRED')
   reassessed=call('plan','validate','--root',root,'--file',plan_file,'--governing-reassessment','Reviewed policy: require two reviewers and rerun verification.','--operation-id','reassess')
   self.assertEqual(reassessed['validation']['governing_digest'],read_state(root)['data']['governing_input_receipt']['effective_digest'])
   self.assertEqual(call('run','next','--root',root,'--run-id','run-1','--operation-id','old-run',expected=2)['error'],'RUN_GOVERNING_INPUTS_STALE')
   self.assertEqual(call('host','handoff-prepare','--root',root,'--file',source('handoff.json',handoff),'--operation-id','old-handoff',expected=2)['error'],'RUN_GOVERNING_INPUTS_STALE')
   self.assertEqual(read_state(root)['data']['runs']['run-1'],original_run)
   call('run','start','--root',root,'--run-id','run-2','--operation-id','fresh-run')
   call('run','next','--root',root,'--run-id','run-2','--operation-id','fresh-attempt')
   self.assertIsNotNone(read_state(root)['data']['runs']['run-2']['active_attempt'])
class FullFlowTests(unittest.TestCase):
 def test_full_workflow_reporting(self):
  u=import_usage([{'source_id':'s','event_id':'e','provider':'p','model':'m','input_tokens':10,'cached_tokens':0,'output_tokens':2}],'v1',{})
  p=store_prices({},'v1',{'source':'fixture'},{'p/m':{'input':1,'cached':1,'output':2}}); cost=price_usage(u,p,{'coverage':1}); self.assertTrue(cost['eligible']); self.assertIsNotNone(rollup([{'id':'r','numerator':1,'denominator':1}],{})['ratio'])
 def test_unavailable_conditions_remain_visible(self):
  self.assertFalse(price_usage({'events':[]},{'rates':{}},{'coverage':.5})['eligible'])
