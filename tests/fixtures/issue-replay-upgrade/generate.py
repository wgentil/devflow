import io,json,pathlib,subprocess,tarfile,tempfile,hashlib
repo=pathlib.Path(__file__).resolve().parents[3];out=repo/'tests/fixtures/issue-replay-upgrade';out.mkdir(parents=True,exist_ok=True)
worker=r'''
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'skills/workflow/scripts'))
from workflow_lib import store
from workflow_lib.specs import content_hash,approval_record
from workflow_lib.journal_domains import digest
from workflow_lib.runs import start_run
root=Path(sys.argv[1]);(root/'events').mkdir(parents=True)
spec={'mode':'new','requirements':[{'id':'R1','text':'One','acceptance_criteria':['one'],'provenance':{'kind':'authored'}}]}
h=content_hash(spec);plan={'spec_hash':h,'work_items':[{'id':'W1','kind':'code','requirement_ids':['R1'],'dependencies':[],'acceptance_criteria':[{'kind':'code-test','text':'test one'}]}]}
data={'spec':spec,'approval':approval_record(spec,h),'plan':plan,'plan_validation':{'valid':True,'spec_hash':h}}
def put(k,p):
 s=store.read_state(root);store.transact(root,s['version'],'fixture-'+str(s['version']),{'kind':k,'payload':p})
put('fixture',data)
if sys.argv[2]=='plain':
 put('run.started',{'run':start_run(data,'plain',plan)})
else:
 snap={'complete':True,'repo_id':'app','pages':[1],'expected_pages':1,'issues':[{'id':'i'}]}
 put('domain.issues.snapshot',{'request':{'snapshot':snap}})
 put('domain.issues.group',{'request':{'snapshot_hash':digest(snap),'groups':[{'id':'g','issue_ids':['i'],'requirement_ids':{'i':['R1']}}]}})
 put('domain.issues.start',{'request':{'snapshot_hash':digest(snap),'group_id':'g','intent':'build'}})
 if sys.argv[2]=='proof':
  r=next(iter(store.read_state(root)['data']['runs'].values()));rid=r['id']
  put('run.attempt.issued',{'run_id':rid,'attempt':{'token':'owned-token','item_id':'W1','state_version':1,'status':'active','result':None}})
  proof={k:'owned-fixture' for k in ('id','kind','phase','run_id','item_id','token','repo_id','started_at','finished_at','repository_head','worktree_digest','stdout_ref','stderr_ref')}
  proof.update(kind='code',phase='RED',run_id=rid,item_id='W1',token='owned-token',exit_code=1,passed=True,argv=['owned-fixture-test'],test_hashes={'test.py':'a'*64},target_outcomes={'test_x':'failed'})
  put('verification.recorded',{'run_id':rid,'proof':proof})
 if sys.argv[2]=='question':
  r=next(iter(store.read_state(root)['data']['runs'].values()))
  put('domain.enforcement.question',{'request':{'run_id':r['id'],'record':{'id':'q','text':'Retention?','scope':['W1'],'source_identity':'fixture-source','spec_hash':h}}})
state=store.read_state(root)
Path(sys.argv[3]).write_text(json.dumps({'events':[json.loads(p.read_text()) for p in sorted((root/'events').glob('*.json'))],'expected':state},ensure_ascii=False,sort_keys=True,indent=2)+'\n')
'''
provenance={'generator':'generate.py','cases':{}}
for tag,mode in [('v0.3.17','proof'),('v0.3.17','plain'),('v0.3.18','start'),('v0.3.18','question')]:
 with tempfile.TemporaryDirectory(prefix='devflow7-oracle-') as tmp:
  tmp=pathlib.Path(tmp);source=tmp/'source';source.mkdir()
  archive=subprocess.run(['git','archive',tag,'skills/workflow/scripts'],cwd=repo,capture_output=True,check=True).stdout
  with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(source,filter='data')
  name=tag+'-'+mode+'.json';subprocess.run(['python3','-B','-c',worker,str(tmp/'control'),mode,str(out/name)],cwd=source,check=True)
  provenance['cases'][name]={'source_commit':subprocess.check_output(['git','rev-parse',tag+'^{commit}'],cwd=repo,text=True).strip(),'sha256':hashlib.sha256((out/name).read_bytes()).hexdigest()}
(out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
