"""Disposable real-Git context projects; historical metadata is explicitly synthetic."""
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.store import _apply_event,_empty,read_state,_atomic_json
from workflow_lib.specs import content_hash
from workflow_lib.repo_specs import write_spec_pair
from workflow_lib.runs import start_run


def make_context_project(base: Path, *, delivered_runs: int=0,event_count: int=0,history_bytes: int=0,requirement_count: int=12) -> dict:
    base=Path(base).resolve();repo=base/'repo';root=base/'control';repo.mkdir(parents=True);(root/'events').mkdir(parents=True)
    def git(*argv):return subprocess.run(['git',*argv],cwd=repo,check=True,capture_output=True,text=True,encoding='utf-8').stdout.strip()
    git('init','-q');git('config','user.name','Offline Fixture');git('config','user.email','offline@example.test')
    spec={'mode':'new','title':'Scoped context fixture','diagrams':[{'title':'Shared boundary','mermaid':'flowchart LR\n    Shared --> Boundary'}],
          'requirements':[{'id':f'R{i}','title':f'Behavior {i}','text':f'Return scoped value {i}.','acceptance_criteria':[f'Target {i} passes.'],'provenance':{'kind':'authored'}} for i in range(1,requirement_count+1)]}
    pair={'repo_id':'app',**write_spec_pair(repo,'docs/spec.json',spec)};git('add','.');git('commit','-qm','Fixture specification')
    plan={'spec_hash':content_hash(spec),'work_items':[{'id':f'W{i}','kind':'code','repo_id':'app','requirement_ids':[f'R{i}'],'dependencies':[],
          'acceptance_criteria':[{'kind':'code-test','text':f'Target {i} passes.'}]} for i in range(1,requirement_count+1)]}
    history={}
    for i in range(delivered_runs):
        size=history_bytes//max(1,delivered_runs)+(i<history_bytes%max(1,delivered_runs))
        history[f'historical-{i}']={'id':f'historical-{i}','status':'delivered','synthetic_fixture':True,
            'review_packages':{'offline':{'body':'H'*size}},'plan':{'work_items':[]},'items':{},'active_attempt':None}
    seed={'spec':spec,'spec_pair':pair,'approval':{**pair,'confirmed':True,'actor_id':'offline-user'},'plan':plan,
          'plan_validation':{'valid':True,'spec_hash':content_hash(spec)},'repositories':{'app':{'location':str(repo)}},'runs':history}
    state=_empty()
    def append(kind,payload):
        event={'schema_version':1,'sequence':state['version']+1,'operation_id':f"fixture-{state['version']+1}",'kind':kind,'payload':payload}
        _apply_event(state,event);state['version']=event['sequence'];state['operations'][event['operation_id']]=event
        # Fixtures build a fresh offline journal, never alter a supplied project.
        (root/'events'/f"{event['sequence']:08d}.json").write_text(json.dumps(event,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    append('fixture',seed)
    for i in range(max(2,event_count)-2):append('fixture',{'synthetic_history_tick':i})
    run=start_run(state['data'],'current',plan);append('run.started',{'run':run})
    _atomic_json(root/'state.json',{k:v for k,v in state.items() if k!='operations'})
    verified=read_state(root)
    return {'root':root,'repo':repo,'run_id':'current','item_id':'W1','state':verified,'run':verified['data']['runs']['current'],
            'statistics':{'events':verified['version'],'delivered_runs':delivered_runs,'journal_bytes':sum(p.stat().st_size for p in (root/'events').glob('*.json')),'state_bytes':(root/'state.json').stat().st_size}}
