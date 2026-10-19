"""Read-only task completion and compact resume policy shared by both hosts."""
import hashlib
import json
from pathlib import Path
from .hosts import validate_binding, receipt_matches_task, task_stage
from .store import WorkflowError
from .gates import _required_proof, gate_status
from .model_policy import check_model_receipt
from .git_paths import git_paths, resolve_repo_path


def _decision(status, reason, blockers=None, **extra):
    return {'status':status,'reason_code':reason,'blockers':blockers or [],'evidence_refs':[],**extra}


def package_current(run, package):
    from .reviews import _git
    plan_hash=hashlib.sha256(json.dumps(run.get('plan',{}),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    if package.get('plan_hash') != plan_hash or package.get('spec_hash') != run.get('plan',{}).get('spec_hash'):return False
    if package.get('role') == 'pr':
        from .pr_reviews import _git, _hash
        if package.get('run_governing_digest') != run.get('governing_digest'):return False
        pending=run.get('pending_pr',{})
        if any(str(pending.get(key)) != str(package.get(key)) for key in
               ('pr_id','pr_number','owner','repo','base_branch','base_sha','head_sha')):return False
        try:
            location=Path(package['location'])
            if _git(location,'rev-parse','HEAD').decode().strip() != package['head_sha']:return False
            if _git(location,'status','--porcelain','--untracked-files=all').strip():return False
            return _hash({key:value for key,value in package.items() if key != 'package_hash'}) == package['package_hash']
        except (KeyError,OSError,ValueError):return False
    try:
        for repo in package.get('repositories',{}).values():
            location=Path(repo['location'])
            if not repo.get('head_verified') or _git(location,'rev-parse','HEAD').strip() != repo['head'] or _git(location,'status','--porcelain','--untracked-files=all') != repo['worktree_status'] or _git(location,'diff','--binary','HEAD') != repo['worktree_diff']: return False
            current={name:hashlib.sha256(resolve_repo_path(location,name).read_bytes()).hexdigest() for name in git_paths(location,'ls-files','--others','--exclude-standard')}
            if current != repo['untracked_hashes']:return False
    except (KeyError,OSError,ValueError):return False
    return bool(package.get('repositories'))


def check_completion(state: dict, binding: dict, task_id: str, live: bool = True, installed_release: dict | None = None, control_root: Path | None = None) -> dict:
    key=binding['host']+':'+binding['session_id']+':'+task_id
    task=state.get('host_tasks',{}).get(key)
    if not task:return _decision('inactive','TASK_UNMAPPED')
    if installed_release is not None:
        from .releases import check_release
        parity=check_release(binding['release'],installed_release,1)
        if parity['status'] != 'allow':return _decision('block','RELEASE_MISMATCH',message=parity['message'],parity=parity)
    try:
        current=validate_binding(state,binding['binding_id'],task['revision'])
        if binding['revision'] != current['revision'] or task['binding_id'] != current['binding_id']:
            return _decision('block','STALE_BINDING')
    except WorkflowError:return _decision('block','STALE_BINDING')
    run=state.get('runs',{}).get(task['run_id'])
    if not run:return _decision('block','RUN_UNAVAILABLE')
    if any(row.get('status') == 'claimed' for row in run.get('repair_cycles', [])):
        return _decision('block', 'REPAIR_LEASE_ACTIVE')
    from .model_policy import effective_preferences
    stage=task_stage(binding,task)
    mode=effective_preferences(run,stage,binding['host']).get('mode','advisory')
    native=run.get('native_invocations',{}).get(task.get('invocation_id'),{})
    if native and native.get('status')=='running':return _decision('block','NATIVE_INVOCATION_ACTIVE')
    receipt=run.get('model_receipts',{}).get(task.get('invocation_id'),{})
    if receipt:
        if not receipt_matches_task(receipt,binding,task):return _decision('block','INVOCATION_SCOPE_MISMATCH')
        mode=receipt.get('mode',mode)
    else:
        from .model_policy import resolve_host_profile
        eligibility=resolve_host_profile(state,binding,stage,control_root)
        if eligibility['reason_code']=='DETERMINISTIC':receipt=eligibility
        elif eligibility['status']=='block' and mode != 'strict':return _decision('block',eligibility['reason_code'])
    if any(i.get('invocation_id') == task.get('invocation_id') for i in run.get('model_interruptions',[])):
        return _decision('block','INVOCATION_INTERRUPTED')
    model=check_model_receipt(receipt,mode)
    if model['status'] == 'block':return _decision('block',model['reason_code'])
    if task['scope'] == 'item':
        item=next((i for i in run.get('plan',{}).get('work_items',[]) if i['id']==task['item_id']),None)
        attempts=run.get('items',{}).get(task['item_id'],{}).get('attempts',[])
        if not attempts or attempts[-1].get('token') != task.get('token'):return _decision('block','TASK_ATTEMPT_STALE')
        active=run.get('active_attempt')
        if active and active.get('item_id') == task['item_id']:return _decision('block','ACTIVE_ATTEMPT')
        if not item or not _required_proof(run,item,live):return _decision('block','FINAL_PROOF_REQUIRED')
        if run['items'][task['item_id']].get('status') != 'complete':return _decision('block','VERIFIED_RESULT_REQUIRED')
        return _decision('allow','ITEM_VERIFIED',evidence_refs=[{'run_id':run['id'],'item_id':task['item_id'],'token':task['token']}])
    if task['scope'] == 'review':
        role=binding['role'].removesuffix('-reviewer')
        package=run.get('review_packages',{}).get(task['package_hash'],{})
        if not package or package.get('role') != role or live and not package_current(run,package):return _decision('block','REVIEW_PACKAGE_STALE')
        history=set(run.get('implementer_actors',[]))|{run.get('actors',{}).get('implementer')}
        if binding['actor_id'] in history:return _decision('block','REVIEWER_NOT_INDEPENDENT')
        review=next((r for r in reversed(run.get('reviews',{}).get(role,[])) if r.get('package_hash')==task['package_hash'] and r.get('actor_id')==binding['actor_id'] and r.get('invocation_ref') and r.get('fresh',True) and r.get('verdict') in ({'pass','changes-requested','human-decision-required','blocked'} if role=='pr' else {'pass','request-changes','block'}) and (role!='item' or r.get('item_id')==task.get('item_id'))),None)
        return _decision('allow','ASSESSMENT_RECORDED',evidence_refs=[{'review_id':review.get('review_id'),'package_hash':task['package_hash']}]) if review else _decision('block','ASSESSMENT_REQUIRED')
    delivery=run.get('delivery',{})
    if run.get('status') != 'delivered' or not delivery.get('actual_result') or not delivery.get('manifest_hash'):
        return _decision('block','TERMINAL_DELIVERY_REQUIRED')
    return _decision('allow','DELIVERY_RECORDED',evidence_refs=[{'manifest_hash':delivery['manifest_hash']}])


def host_brief(state: dict, binding: dict, *, control_root: Path | None = None,
               max_bytes: int = 20000, representation: str = 'markdown', output_mode: str = 'full') -> dict:
    run=state.get('runs',{}).get(binding['run_id'],{})
    tasks=[t for t in state.get('host_tasks',{}).values() if t['binding_id']==binding['binding_id']]
    selected={t.get('item_id') for t in tasks if t.get('revision')==binding['revision']}
    if binding.get('item_id'):selected.add(binding['item_id'])
    if run.get('active_attempt'):selected.add(run['active_attempt'].get('item_id'))
    work_items=[item for item in run.get('plan',{}).get('work_items',[]) if item['id'] in selected]
    required=run.get('plan',{}).get('stage',{}).get('required_slices',[])
    values=run.get('context',{}).get('values',{})
    context={'values':{key:values[key] for key in required if key in values},
             'missing':[key for key in required if key not in values],
             'conflicts':[c for c in run.get('context',{}).get('conflicts',[]) if c.get('slice') in required]}
    package=run.get('review_packages',{}).get(binding.get('package_hash'),{})
    relevant={'work_items':work_items,'context':context,'package':package,'binding_id' :binding['binding_id'],'revision':binding['revision'],'role':binding['role'],
              'run_id':binding['run_id'],'active_attempt':run.get('active_attempt'),
              'stage':gate_status(run,live=False),'tasks':tasks,'model_policy':run.get('model_overrides',[]),
              'budget':run.get('context',{}).get('budgets',{}),'proofs':run.get('verification_proofs',{}),
              'reviews':run.get('reviews',{}),'acceptances':run.get('acceptances',[]),'delivery':run.get('delivery')}
    digest=hashlib.sha256(json.dumps(relevant,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    envelope = {'fingerprint':digest,'binding_id':binding['binding_id'],'revision':binding['revision'],
            'run_id':binding['run_id'],'role':binding['role'],'stage':relevant['stage']['stage'],
            'active_attempt':run.get('active_attempt'),'mapped_tasks':[t['task_id'] for t in tasks],
            'unmapped_tasks':'unaffected','blockers':relevant['stage']['blocking_findings'],
            'budget':relevant['budget'],'work_items':work_items,'context':context,'package_hash':binding.get('package_hash'),'evidence_refs':['journal:'+binding['run_id']]}
    if control_root is None:
        return envelope
    from .task_views import prepare_task_view
    from .document_units import digest as content_digest
    view = prepare_task_view(control_root, run, envelope, [item['id'] for item in work_items],
                             stage=envelope['stage'], max_bytes=max_bytes,
                             representation=representation, output_mode=output_mode)
    view['fingerprint'] = content_digest({'envelope': digest, 'context': view['task_view'].get('artifact_id')})
    return view
