"""Read-only host event evaluation and brief cache (never authoritative)."""
import json
from pathlib import Path
from .bootstrap import discover_project
from .host_locators import read_locator, locator_path, read_task_index
from .hosts import binding_for_session
from .host_completion import check_completion, host_brief
from .store import read_state, WorkflowError, _atomic_json


def evaluate(project_dir, session_id, event, task_id=None):
    if event == 'Stop':return {'status':'inactive','reason_code':'PAUSE_ALLOWED'}
    try: project=discover_project(Path(project_dir))
    except (WorkflowError,OSError):return {'status':'inactive','reason_code':'NO_PROJECT'}
    issue=None
    try: locator=read_locator(project,'claude',session_id)
    except WorkflowError as exc:locator=None;issue=exc.code
    index=read_task_index(project,'claude',session_id)
    known_mapped=event == 'TaskCompleted' and index and task_id in index['task_ids']
    if locator and index and Path(locator['control_root']).resolve() != Path(index['control_root']).resolve():
        issue='LOCATOR_ROOT_MISMATCH'
    root=Path(locator['control_root']) if locator else Path(index['control_root']) if index else project/'.devflow/control'
    if not locator and index:issue=issue or 'LOCATOR_MISSING' 
    if not root.is_dir():
        return {'status':'block' if known_mapped else 'inactive','reason_code':'CONTROL_ROOT_UNAVAILABLE'}
    state=read_state(root)['data']
    binding=binding_for_session(state,'claude',session_id)
    if locator:
        pointed=state.get('host_bindings',{}).get(locator['binding_id'])
        if not pointed or pointed.get('session_id') != session_id or pointed.get('host') != 'claude':
            issue='LOCATOR_BINDING_MISMATCH'
        elif pointed['status'] != 'active':issue='BINDING_DETACHED'
        elif binding and pointed['binding_id'] != binding['binding_id']:issue='LOCATOR_BINDING_MISMATCH'
    if not binding or known_mapped and issue:
        return {'status':'block' if known_mapped else 'inactive','reason_code':issue or 'NOT_ATTACHED',
                'message':'Repair locator by retrying explicit attachment against the task index control root.'}
    if Path(binding['project_dir']).resolve() != project:issue='PROJECT_BINDING_MISMATCH'
    if event == 'TaskCompleted':
        from .releases import release_descriptor
        decision=check_completion(state,binding,task_id,installed_release=release_descriptor(),control_root=root)
        if known_mapped and decision['status'] == 'inactive':
            return {'status':'block','reason_code':'TASK_MAPPING_UNAVAILABLE','message':'Repair the task index/locator against the authoritative journal.'}
        if decision['status'] != 'inactive' and issue:
            return {'status':'block','reason_code':issue,'message':'Repair locator by retrying explicit attachment.'}
        return decision
    if issue:return {'status':'inactive','reason_code':issue,'message':'Repair locator by retrying explicit attachment.'}
    try:
        brief=host_brief(state,binding,control_root=root)
    except WorkflowError as exc:
        return {'status':'block','reason_code':exc.code,'message':str(exc),'evidence_refs':['journal:'+binding['run_id']]}
    path=locator_path(project,'claude',session_id).with_suffix('.brief.json')
    try:prior=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    except (OSError,ValueError):prior={}
    if event != 'SessionStart' and prior.get('fingerprint') == brief['fingerprint']:return {'status':'inactive','reason_code':'BRIEF_UNCHANGED'}
    from .context_checkpoints import checkpoint_read
    try:
        brief=checkpoint_read(root,brief,{'consumer_id':session_id,'run_id':binding['run_id'],
            'binding_id':binding['binding_id'],'session_id':session_id,'revision':binding['revision'],
            'stage':brief['stage'],'role':binding['role'],'task_ids':[item['id'] for item in brief['work_items']]},
            since=prior.get('checkpoint_id') if event != 'SessionStart' else None,
            recovery_reason='session-start' if event == 'SessionStart' else None)
    except WorkflowError as exc:
        return {'status':'block','reason_code':exc.code,'message':str(exc)}
    fingerprint=brief['fingerprint']
    checkpoint_id=brief['checkpoint']['id']
    encoded=json.dumps(brief,separators=(',',':'))
    if len(encoded.encode()) > 8192:
        from .context_artifacts import store_context_artifact
        ref=store_context_artifact(root,brief,{'binding_id':binding['binding_id'],'revision':binding['revision']})
        brief={key:value for key,value in brief.items() if key not in {'task_view','budget'}}
        brief.update(reason_code='FULL_CONTEXT_REFERENCE',context_complete=False,artifact_ref=ref,
            message='Load the complete context artifact before proceeding; this inline envelope contains control state only.')
        if len(json.dumps(brief,separators=(',',':')).encode('utf-8')) > 8192:
            return {'status':'block','reason_code':'HOOK_OUTPUT_OVERFLOW','message':'Mandatory control state exceeds inline budget; inspect host brief.'}
    path.parent.mkdir(parents=True,exist_ok=True)
    _atomic_json(path,{'fingerprint':fingerprint,'checkpoint_id':checkpoint_id})
    return {'status':'allow','brief':brief}
