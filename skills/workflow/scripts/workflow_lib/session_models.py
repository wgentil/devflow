"""Actual standalone native transport, shared claims, private producer receipts."""
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path
import hashlib,json,os,time
from .document_units import digest
from .store import WorkflowError
from .native_models import CodexBackend,ClaudeBackend,NativeError
from .review_sessions import read_session
from .session_evidence import _commit

SESSION_MODEL=ContextVar('devflow_session_model',default=None)


def need(ok,message):
    if not ok:raise WorkflowError('SESSION_MODEL_BLOCKED',message)


def now():return int(time.time()*1000)


def guard(path,subject,action,record):
    if not action.startswith('session-model-'):return
    active=SESSION_MODEL.get();identifier=record.get('invocation_id')
    need(active and active.get('path')==str(Path(path).resolve()) and active.get('id')==identifier,'Only the actual session model producer can record native claims/results.')
    if action=='session-model-reconcile':
        from .process_liveness import process_alive
        need(active.get('mode')=='recovery' and process_alive(subject.get('native_invocations',{}).get(identifier,{}).get('owner_pid')) is False,'Observed absent coordinator and held recovery lease required.')
    else:
        owner=record.get('owner_pid') if action=='session-model-claim' else subject.get('native_invocations',{}).get(identifier,{}).get('owner_pid')
        need(active.get('mode')=='dispatch' and owner==os.getpid(),'Native output belongs to its real coordinator.')


def transport_scope(subject,record):
    if record.get('purpose','review')=='review':
        from .review_dispatch import specialist_scope
        return specialist_scope(subject,{'role':'session-reviewer','perspective':record.get('perspective')})
    from .review_policy import review_bindings
    need(subject.get('repair_authorization') and record.get('actor_id')==subject.get('actors',{}).get('implementer'),'Actual scoped repair authorization and implementing actor required.')
    ids=record.get('finding_ids');known={f['id'] for f in subject.get('unresolved_findings',[]) if f.get('status','open') not in {'resolved','waived','rejected','deferred'}}
    need(isinstance(ids,list) and ids and set(ids).issubset(known),'Select actual unresolved original findings.')
    return {'role':'implementation','bindings_hash':digest(review_bindings(subject,{'role':'session'})),
        'finding_ids':sorted(ids),'rationale_hash':digest(subject.get('fix_rationales',{})),
        'authorization_hash':digest(subject['repair_authorization'])}


def reduce_model(subject,action,record):
    from .review_dispatch import specialist_scope
    from .effect_claims import claim_effect,transition_effect
    identifier=record['invocation_id'];updated=deepcopy(subject);rows=updated.setdefault('native_invocations',{})
    if action=='session-model-claim':
        need(identifier not in rows and record.get('scope')==transport_scope(subject,record),'Exact current specialist scope and fresh identity required.')
        request=record['claim'];need(request.get('effect_id')==identifier and request.get('owner_pid')==record.get('owner_pid'),'Exact actual effect owner required.')
        updated=claim_effect(updated,request);rows=updated.setdefault('native_invocations',{})
        rows[identifier]={**deepcopy(record),'status':'claimed'}
    elif action=='session-model-launch':
        row=rows.get(identifier,{});need(row.get('status')=='claimed' and row['scope']==transport_scope(subject,row),'Scope changed before actual model launch.')
        decision=record.get('decision',{});need(decision.get('status')=='allow' and decision.get('dispatch') is True and decision.get('capability_validated') is True,'Actual eligible model decision required.')
        updated=transition_effect(updated,{'effect_id':identifier,'status':'launching','now_ms':record['now_ms']})
        updated['native_invocations'][identifier].update(status='launching',decision=deepcopy(decision),package_hash=record['package_hash'],diagnostic=record['diagnostic'],started_ms=record['now_ms'],policy_revision=len(subject.get('model_overrides',[])))
        updated['review_dispatch_sequence']=subject.get('review_dispatch_sequence',0)+1
        updated['native_invocations'][identifier]['review_sequence']=updated['review_dispatch_sequence']
    elif action=='session-model-finish':
        row=rows.get(identifier,{});need(row.get('status') in {'claimed','launching'},'Only an outstanding actual producer can finish once.')
        result=record['result'];completed=result.get('status')=='completed' and bool(result.get('invocation_ref'))
        if row['status']=='claimed':
            need(not completed and result.get('dispatch') is False,'Prelaunch failures must disclose no dispatch.')
            updated=transition_effect(updated,{'effect_id':identifier,'status':'failed','now_ms':record['now_ms']})
        elif result.get('dispatch') is False:
            updated=transition_effect(updated,{'effect_id':identifier,'status':'failed','now_ms':record['now_ms'],'dispatch_started':False})
        elif completed or result.get('transport_completed') is True:
            updated=transition_effect(updated,{'effect_id':identifier,'status':'running','now_ms':record['now_ms'],'worker_ref':result['invocation_ref']})
            updated=transition_effect(updated,{'effect_id':identifier,'status':'completed','now_ms':record['now_ms']})
        else:updated=transition_effect(updated,{'effect_id':identifier,'status':'uncertain','now_ms':record['now_ms'],'worker_ref':result.get('invocation_ref') or identifier})
        row=updated['native_invocations'][identifier]
        decision=deepcopy(row.get('decision',{}));receipt={**decision,'status':'block','reason_code':result.get('reason_code','SESSION_MODEL_INCOMPLETE'),
            'dispatch':row.get('status')=='launching' and result.get('dispatch') is not False,'transport_completed':completed or result.get('transport_completed') is True,'invocation_id':identifier,'invocation_ref':result.get('invocation_ref'),
            'policy_revision':row.get('policy_revision',len(subject.get('model_overrides',[]))),'review_sequence':row.get('review_sequence'),
            'diagnostic':row.get('diagnostic',True),'scope':{'role':'implementer' if row.get('purpose')=='repair' else 'session-reviewer','actor_id':row['actor_id'],'session_id':subject['id'],
                'perspective':row['perspective'],'package_hash':row.get('package_hash'),'review_scope':row['scope']},
            'started_ms':row.get('started_ms'),'finished_ms':record['now_ms'],
            **{k:deepcopy(result[k]) for k in ('observed','observation_source','usage','output_ref','review_report_hash','review_input_validation') if k in result}}
        if completed:
            from .model_policy import check_model_receipt
            receipt['status']='allow'
            compliance=check_model_receipt(receipt,'strict')
            if receipt.get('observed',{}).get('provider')!=receipt.get('resolved',{}).get('provider'):
                compliance={'status':'block','reason_code':'MODEL_SUBSTITUTED'}
            receipt.update(status=compliance['status'],reason_code=compliance.get('reason_code','SESSION_MODEL_COMPLETED'))
        row.update(status='completed' if completed or result.get('transport_completed') is True else 'failed' if result.get('dispatch') is False else 'uncertain',receipt=deepcopy(receipt))
        updated.setdefault('model_receipts',{})[identifier]=receipt
    elif action=='session-model-reconcile':
        from .enforcement_recovery import validate_tool_observation
        row=rows.get(identifier,{});need(row.get('status') in {'claimed','launching','uncertain'},'Known interrupted session worker required.')
        observation=record['observation'];validate_tool_observation({'id':identifier,'owner_pid':row['owner_pid']},observation)
        effect=updated['effects'][identifier]
        if effect['status']=='claimed':updated=transition_effect(updated,{'effect_id':identifier,'status':'failed','now_ms':observation['now_ms']})
        else:
            if effect['status']!='uncertain':updated=transition_effect(updated,{'effect_id':identifier,'status':'uncertain','now_ms':observation['now_ms'],'worker_ref':identifier})
            updated.setdefault('worker_termination_observations',{})[record['observation_id']]=deepcopy(observation)
            updated=transition_effect(updated,{'effect_id':identifier,'status':'reconciled','now_ms':observation['now_ms'],
                'termination_observation_id':record['observation_id'],'termination_receipt':observation})
        updated['native_invocations'][identifier].update(status='reconciled',recovery=record['observation_id'])
    else:raise WorkflowError('SESSION_MODEL_BLOCKED','Unknown native session event.')
    return updated


def dispatch(path,request,operation_id,*,purpose='review'):
    from .native_runtime import _native_lease,policy
    from .review_dispatch import specialist_scope,select_review_route
    from .implementation_contracts import review_prerequisites
    from .session_evidence import prepare,_live
    from .adversarial_reviews import publish_review_input,specialist_prompt,seal_actual_report,verify_review_input
    from .storage_objects import put_object
    from .effect_claims import validate_active_dispatch
    path=Path(path).resolve();identifier=operation_id
    need(isinstance(identifier,str) and identifier and isinstance(request,dict),'Explicit operation ID and request required.')
    need(not set(request)-{'perspective','host','actor_id','estimated_cost','diagnostic','timeout_seconds','prompt','preferences','finding_ids','expected_source_identity'},'Session review accepts only bounded read-only specialist settings.')
    need(request.get('host') in {'codex','claude'} and request.get('actor_id'),'Actual independent actor and supported host required.')
    from .review_policy import bounded
    bounded(request);session_preferences(subject=read_session(path)['subject'],request=request,stage='implementation' if purpose=='repair' else 'review')
    need('prompt' not in request or isinstance(request['prompt'],str) and request['prompt'].strip(),'Prompt must be a nonempty string.')
    timeout=request.get('timeout_seconds',300);need(type(timeout) in (int,float) and 1<=timeout<=3600,'Finite native timeout from 1 to 3600 seconds required.')
    lease=path.with_name(path.name+'.leases')/hashlib.sha256(identifier.encode()).hexdigest();lease.parent.mkdir(parents=True,exist_ok=True)
    token=SESSION_MODEL.set({'path':str(path),'id':identifier,'mode':'dispatch'})
    backend=None
    try:
        with _native_lease(lease):
            state=read_session(path);subject=state['subject'];prior=subject.get('native_invocations',{}).get(identifier)
            if prior:
                need(prior.get('purpose','review')==purpose,'An invocation cannot change execution purpose.')
                need(prior.get('request_hash')==digest(request),'Session operation belongs to different exact settings.')
                if prior.get('receipt'):return finalize_receipt(path,identifier,replayed=True)
                raise WorkflowError('SESSION_MODEL_UNCERTAIN','Observe/reconcile the original stopped worker; do not relaunch.')
            scope=transport_scope(subject,{**request,'purpose':purpose})
            from .implementation_contracts import implementation_prerequisites
            prerequisites=(implementation_prerequisites(subject,{'role':'session'}) if purpose=='repair' else review_prerequisites(subject,{'role':'session',**({'diagnostic':True} if request.get('diagnostic') is True else {})}))
            if prerequisites['status']!='allow':return {'status':'block','reason_code':'REVIEW_PREREQUISITES_REQUIRED','prerequisites':prerequisites}
            _live(subject,diagnostic=purpose=='review')
            need(request.get('expected_source_identity',subject['source_identity'])==subject['source_identity'],'Source changed before this bound action.')
            package=prepare(path,identifier+':package');state=read_session(path);subject=state['subject']
            artifact=publish_review_input(path.with_name(path.name+'.artifacts'),package)
            from .review_orchestration import allow_reservation
            allow_reservation(subject,request.get('estimated_cost'),now())
            claim={'effect_id':identifier,'scope':('implementation:session' if purpose=='repair' else 'review:session:'+request['perspective']+':'+package['package_hash']),
                'action_scope':({'purpose':'repair','role':'session','finding_ids':request['finding_ids']} if purpose=='repair' else {'purpose':'review'}),'actor_id':request['actor_id'],'owner_pid':os.getpid(),
                'source_identity':subject['source_identity'],'estimated_cost':request.get('estimated_cost'),'now_ms':now()}
            _commit(path,state,identifier+':claim','session-model-claim',{'invocation_id':identifier,'owner_pid':os.getpid(),
                'scope':scope,'purpose':purpose,'stage':'implementation' if purpose=='repair' else 'review','finding_ids':request.get('finding_ids',[]),'perspective':request.get('perspective'),'actor_id':request['actor_id'],'request_hash':digest(request),'claim':claim})
            launched=False;invoked=False;configuration={};result=None
            try:
                backend=(CodexBackend if request['host']=='codex' else ClaudeBackend)(subject['repositories']['repo-1']['location'])
                context=backend.discover();preferences={**session_preferences(subject,request,stage='implementation' if purpose=='repair' else 'review'),
                    'host':request['host'],'stage':'implementation' if purpose=='repair' else 'review','mode':'strict',
                    **({'perspective':request['perspective'],'assessment':scope['assessment']} if purpose=='review' else {})}
                from .model_policy import resolve_profile
                resolver=select_review_route if purpose=='review' else resolve_profile
                decision=resolver(policy(),preferences,context.get('capabilities',{}),context.get('discovery',{}),None)
                need(decision.get('status')=='allow' and decision.get('capability_validated') is True,'No actual eligible model is available under current specialist settings.')
                state=read_session(path);latest=state['subject'];_live(latest,diagnostic=True)
                need(transport_scope(latest,{**request,'purpose':purpose})==scope,'Policy, source, contract or questions changed before model launch.')
                _commit(path,state,identifier+':launch','session-model-launch',{'invocation_id':identifier,'decision':decision,
                    'package_hash':package['package_hash'],'diagnostic':request.get('diagnostic') is True,'now_ms':now()});launched=True
                if request['host']=='codex':
                    configuration=backend.configure(decision['resolved'],'DevFlow actor '+request['actor_id'],'workspace-write' if purpose=='repair' else 'read-only')
                    if any(configuration.get('observed',{}).get(k)!=decision['resolved'].get(k) for k in ('provider','model','effort')):
                        raise WorkflowError('MODEL_SUBSTITUTED','Configured model/effort/provider differs before turn execution.')
                state=read_session(path);latest=state['subject'];_live(latest,diagnostic=True)
                need(len(latest.get('model_overrides',[]))==latest['native_invocations'][identifier]['policy_revision'],'Model preferences changed before invocation.')
                validate_active_dispatch(latest,identifier,{'source_identity':latest['source_identity'],'now_ms':now()})
                need(transport_scope(latest,{**request,'purpose':purpose})==scope,'Scope changed immediately before invocation.')
                prereq=(implementation_prerequisites(latest,{'role':'session'}) if purpose=='repair' else review_prerequisites(latest,{'role':'session',**({'diagnostic':True} if request.get('diagnostic') is True else {})}))
                need(prereq['status']=='allow','Prerequisites changed before actual invocation.')
                remaining=(latest['effect_policy']['max_elapsed_ms']-(now()-latest['effects_started_ms']))/1000
                from .review_orchestration import remaining_seconds
                loop_remaining=remaining_seconds(latest,now())
                if loop_remaining is not None:remaining=min(remaining,loop_remaining)
                need(remaining>0,'Elapsed budget exhausted before invocation.')
                task=request.get('prompt','Fix only the selected findings using current intent and recorded rationale; preserve locked inputs and ask about business uncertainty.' if purpose=='repair' else 'Review only the selected source and report actual evidence.')
                prompt=(specialist_prompt(task) if purpose=='review' else task)+'\n'+json.dumps({'review_input':artifact,'perspective':request.get('perspective'),'finding_ids':request.get('finding_ids',[]),'limitations':subject.get('limitations',[])},separators=(',',':'))
                need(len(prompt.encode())<=20000,'Known specialist prompt exceeds budget; use bound artifacts.')
                input_before=verify_review_input(path.with_name(path.name+'.artifacts'),package)
                invoked=True
                result=backend.invoke(decision['resolved'],prompt,request['actor_id'],'workspace-write' if purpose=='repair' else 'read-only',min(timeout,remaining))
                input_after=verify_review_input(path.with_name(path.name+'.artifacts'),package)
                result['review_input_validation']={'before':input_before,'after':input_after}
                output=result.pop('output','')
                if purpose=='review':result['review_report_hash']=seal_actual_report(output)
                result['output_ref']=put_object(path.with_name(path.name+'.artifacts'),'session-model-output',output.encode())
            except (WorkflowError,OSError,ValueError) as exc:
                actual=result if isinstance(result,dict) else {}
                result={**configuration,**actual,'status':'interrupted','reason_code':getattr(exc,'code','SESSION_MODEL_FAILED')}
                if actual.get('status')=='completed' and actual.get('invocation_ref'):
                    result['transport_completed']=True
                    result['output_ref']=put_object(path.with_name(path.name+'.artifacts'),'session-model-output',str(result.pop('output','')).encode())
                if not invoked:result['dispatch']=False
            state=read_session(path)
            _commit(path,state,identifier+':finish','session-model-finish',{'invocation_id':identifier,'result':result,'now_ms':now()})
            receipt=read_session(path)['subject']['model_receipts'][identifier]
            return finalize_receipt(path,identifier)
    finally:
        try:
            if backend:backend.close()
        finally:SESSION_MODEL.reset(token)


def finalize_receipt(path,identifier,*,replayed=False):
    from .storage_objects import read_object
    from .session_evidence import record_review
    subject=read_session(path)['subject'];receipt=subject['model_receipts'][identifier]
    response={**receipt,'replayed':replayed}
    if subject['native_invocations'][identifier].get('purpose')=='repair':return {**response,'report_status':'not-applicable'}
    if not receipt.get('review_report_hash'):return {**response,'report_status':'unavailable'}
    try:
        raw=read_object(Path(path).with_name(Path(path).name+'.artifacts'),receipt['output_ref'],max_bytes=2*1024*1024)
        report=json.loads(raw)
        if isinstance(report,dict) and isinstance(report.get('review'),dict):report=report['review']
        scope=receipt['scope']
        need(isinstance(report,dict) and report.get('package_hash',scope['package_hash'])==scope['package_hash']
             and report.get('perspective',scope['perspective'])==scope['perspective'],'Actual output belongs to another package/perspective.')
        report={**report,'package_hash':scope['package_hash'],'perspective':scope['perspective'],
            'actor_id':scope['actor_id'],'invocation_ref':receipt['invocation_ref'],'model_invocation_id':identifier}
        recorded=record_review(path,report,identifier+':review')
        return {**response,'report_status':'recorded','review_id':recorded['review_id'],'verdict':recorded['verdict']}
    except (WorkflowError,ValueError,KeyError) as exc:
        return {**response,'model_status':receipt['status'],'status':'block','report_status':'blocked',
            'report_reason_code':getattr(exc,'code','SESSION_REPORT_INVALID'),'report_message':str(exc)[:2048],'next_action':'inspect-actual-output-and-renew-required-evidence'}


def session_preferences(subject,request,stage='review'):
    import math
    from .model_policy import effective_preferences,PREFERENCE_KEYS
    values=request.get('preferences',{})
    need(isinstance(values,dict) and not set(values)-PREFERENCE_KEYS,'Use known model preference fields only.')
    need(values.get('mode','strict')=='strict' and values.get('allow_unvalidated',False) is False,'Standalone specialists require validated strict routes.')
    for key in ('pin','profile','effort','price_version'):
        need(key not in values or isinstance(values[key],str) and values[key],'Model preference identifiers must be explicit nonempty strings.')
    need('allowed_models' not in values or isinstance(values['allowed_models'],list) and all(isinstance(m,str) and m for m in values['allowed_models']),'Allowed models must be an explicit array.')
    need('max_cost' not in values or type(values['max_cost']) in (int,float) and math.isfinite(values['max_cost']) and values['max_cost']>=0,'Model cost cap must be finite.')
    if 'estimated_tokens' in values:
        tokens=values['estimated_tokens'];need(isinstance(tokens,dict) and set(tokens)=={'input','output'} and all(type(v) is int and v>=0 for v in tokens.values()),'Explicit finite input/output token estimate required.')
    base=effective_preferences(subject,stage,request.get('host'));merged={**base,**values,'mode':'strict'}
    if base.get('allowed_models') is not None and values.get('allowed_models') is not None:
        merged['allowed_models']=[m for m in values['allowed_models'] if m in base['allowed_models']]
    if base.get('max_cost') is not None and values.get('max_cost') is not None:merged['max_cost']=min(base['max_cost'],values['max_cost'])
    return merged


def dispatch_implementation(path,request,operation_id):
    from .native_runtime import policy
    subject=read_session(path)['subject']
    need(subject.get('editable_source') is True and subject.get('repair_authorization') and request.get('actor_id')==subject.get('actors',{}).get('implementer'),
        'Explicit actual editable-scope repair authorization required; report-only snapshots cannot launch writers.')
    if operation_id in subject.get('native_invocations',{}):return dispatch(path,request,operation_id,purpose='repair')
    host=request.get('host');profile=policy().get('stages',{}).get('implementation')
    if not policy().get('hosts',{}).get(host,{}).get(profile):return {'status':'block','reason_code':'NO_VALIDATED_PERMITTED_MODEL'}
    return dispatch(path,request,operation_id,purpose='repair')
