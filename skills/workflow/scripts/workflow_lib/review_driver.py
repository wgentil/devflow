"""One explicit claimed step at a time; native/tool producers remain authoritative."""
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
from .store import WorkflowError
from .document_units import digest
from .review_orchestration import orchestration_next,input_binding,logical

DRIVER=ContextVar('devflow_review_driver',default=None)


def need(ok,message):
    if not ok:raise WorkflowError('REVIEW_DRIVER_BLOCKED',message)


def now():return int(time.time()*1000)


class Subject:
    def __init__(self,location,request):
        self.location=Path(location).resolve();self.run_id=request.get('run_id');self.session=request.get('session') is True
        need(self.session != bool(self.run_id),'Select standalone session or actual workflow run explicitly.')
    def read(self):
        if self.session:
            from .review_sessions import read_session
            state=read_session(self.location);return state,state['subject']
        from .storage_access import read_current
        state=read_current(self.location,run_id=self.run_id)
        subject=state['data'].get('runs',{}).get(self.run_id);need(subject,'Known workflow run required.')
        return state,subject
    def event(self,action,record,operation):
        state,subject=self.read()
        if self.session:
            from .review_sessions import transact_session
            return transact_session(self.location,state['version'],operation,{'action':action,'record':record})
        from .store import transact
        from .storage_access import operation_lookup
        kind=('domain.repair.'+action if action.startswith('orchestration-') else 'domain.enforcement.'+action)
        event={'kind':kind,'payload':{'request':{'run_id':self.run_id,'record':record}}}
        prior=operation_lookup(self.location,operation)
        if prior:need(prior['kind']==kind and prior['payload']==event['payload'],'Operation belongs to different exact inputs.')
        result=transact(self.location,state['version'],operation,event)
        need(result['event']['kind']==kind and result['event']['payload']==event['payload'],'Concurrent operation identity conflict.')
        return result
    def root_event(self,kind,payload,operation):
        from .store import transact
        state,_=self.read();return transact(self.location,state['version'],operation,{'kind':kind,'payload':payload})
    def live(self,subject):
        from .enforcement_live import assert_source_current,assert_protection_current
        from .standalone_reviews import assert_selection_current
        assert_selection_current(subject);assert_source_current(subject);assert_protection_current(subject)
    def observe(self,operation):
        from .enforcement_live import source_observation
        _,subject=self.read();return self.event('observe-source',source_observation(subject),operation)
    def cli(self,*args):
        entry=Path(__file__).resolve().parents[1]/'run.py'
        result=subprocess.run([sys.executable,str(entry),*map(str,args)],capture_output=True,text=True,timeout=120)
        if result.returncode:
            try:error=json.loads(result.stdout)
            except ValueError:error={}
            raise WorkflowError(error.get('error','REVIEW_DRIVER_BLOCKED'),error.get('message') or result.stderr or result.stdout)
        return json.loads(result.stdout)


def guard(location,subject,action,record):
    if action not in {'driver-claim','driver-finish','fail-action','recover-driver','end-rework'}:return
    active=DRIVER.get();need(active and active['location']==str(Path(location).resolve()),'Only the actual held driver lease may record execution ownership/results.')
    need(active['operation_id']==record.get('operation_id',active['operation_id']),'Driver operation differs from the actual coordinator.')
    if action=='recover-driver':
        from .process_liveness import process_alive
        row=subject.get('review_orchestration',{}).get('driver_operations',{}).get(record.get('operation_id'),{})
        need(active.get('mode')=='recovery' and process_alive(row.get('owner_pid')) is False,'Observe the original coordinator absent under the same actual lease.')
    if action=='driver-claim':need(record.get('owner_pid')==os.getpid(),'Actual driver process required.')


def _contract(adapter,request,action,operation):
    from .implementation_contracts import scope_key,selected_contracts,contract_binding
    _,subject=adapter.read();scope=logical(action['scope']);provided=request.get('contract')
    rows=[provided] if provided else selected_contracts(subject,scope)
    need(rows and all(isinstance(row,dict) for row in rows),'Provide an evidence-derived implementation contract; do not guess business intent.')
    fields={'scope','behaviors','invariants','non_goals','interfaces','neighboring','neighboring_disposition','checks','intent_decision'}
    for index,row in enumerate(rows):
        record={k:deepcopy(v) for k,v in row.items() if k in fields}
        record.setdefault('scope',scope);record['source_identity']=subject['source_identity']
        adapter.event('implementation-contract',record,operation+':'+str(index))
    _,subject=adapter.read();return contract_binding(subject,scope)


def _execute(adapter,request,action,operation):
    _,subject=adapter.read();adapter.live(subject)
    kind=action['kind'];scope=action['scope'];item_id=scope.get('item_id')
    if kind=='contract':return _contract(adapter,request,action,operation),False
    if kind=='rationale':
        from .implementation_contracts import scope_key
        contract=subject['implementation_contracts'][scope_key(scope)]
        for fid in scope['finding_ids']:
            rationale=request.get('rationales',{}).get(fid)
            need(rationale,'Provide the actual observed failure, evidence and cause/hypothesis; the driver cannot invent it.')
            record={**rationale,'scope':logical(scope),'source_identity':subject['source_identity'],'contract_hash':contract['contract_hash'],'finding_id':fid}
            adapter.event('fix-rationale',record,operation+':'+fid)
        _,subject=adapter.read();return digest({fid:subject['fix_rationales'][fid]['rationale_hash'] for fid in scope['finding_ids']}),False
    if kind=='retry-item':
        command='reverify' if subject['items'][item_id]['status']=='complete' else 'retry'
        adapter.cli('run',command,'--root',adapter.location,'--run-id',adapter.run_id,'--item',item_id,'--operation-id',operation)
        return adapter.read()[1]['active_attempt']['token'],False
    if kind=='verify':
        if adapter.session:
            from .session_evidence import capture
            proof=capture(adapter.location,action['phase'],operation,request.get('verification_timeout',300),expected_source_identity=subject['source_identity'])
        else:
            from .evidence import capture_evidence
            verification=request.get('verification',{})
            need(verification and subject.get('active_attempt',{}).get('item_id')==item_id,'An actual current attempt and explicit verifier command/targets are required.')
            proof=capture_evidence(adapter.location,adapter.run_id,subject['active_attempt']['token'],action['phase'],
                verification['argv'],verification['input_paths'],verification['target_ids'],verification.get('timeout_seconds',300),
                verification.get('report_format','json'),operation_id=operation,expected_source_identity=subject['source_identity'])
        need(proof.get('passed') is True and proof.get('id'),'Actual applicable assertion evidence unavailable; do not infer RED/GREEN from exit alone.')
        if action['phase']=='GREEN':
            for fid in scope['finding_ids']:
                _,current=adapter.read()
                adapter.event('propose-fix',{'finding_id':fid,'source_identity':current['source_identity'],'proof_ids':[proof['id']],
                    'rationale':'Actual corrected execution; independent assessment must establish applicability and closure.'},operation+':candidate:'+fid)
        return proof['id'],True
    if kind=='implement':
        worker=request.get('implementer',{})
        need(worker,'Supply the actual eligible implementer settings and known finite cost.')
        if adapter.session:
            from .session_models import dispatch_implementation
            result=dispatch_implementation(adapter.location,{**worker,'finding_ids':scope['finding_ids'],
                'expected_source_identity':subject['source_identity']},operation+':worker')
        else:
            from .native_runtime import invoke
            result=invoke(adapter.location,{**worker,'invocation_id':operation+':worker','stage':'implementation','access':'workspace-write',
                'prompt':worker.get('prompt','Repair only the selected findings, preserving approved intent and locked tests; use the current contract and rationale.'),
                'expected_source_identity':subject['source_identity'],'repair_scope':{'finding_ids':scope['finding_ids']}},operation+':worker')
        need(result.get('status')=='allow' and result.get('dispatch') is True,'Actual implementer is blocked/uncertain; inspect retained native evidence and do not launch a replacement.')
        adapter.observe(operation+':source')
        return operation+':worker',True
    if kind=='check':
        need(not adapter.session,'Standalone checks require explicit session verification targets; no workflow gates are invented.')
        from .repair_runtime import _run_gate
        _run_gate(adapter.location,adapter.run_id,action['gate_id'],operation)
        return action['gate_id'],True
    if kind=='package':
        if adapter.session:
            from .session_evidence import prepare
            package=prepare(adapter.location,operation)
        else:
            from .reviews import prepare_review
            repositories=request.get('repositories');need(repositories,'Supply explicit repository base/head review manifests; never guess a comparison branch.')
            package=prepare_review(subject,scope['role'],repositories,item_id=item_id)
            adapter.root_event('review.package.prepared',{'run_id':adapter.run_id,'package':package},operation)
        return package['package_hash'],False
    if kind=='review':
        perspective=action.get('perspective');settings=request.get('reviewers',{})
        if not adapter.session:settings=settings.get(scope['role'],{})
        reviewer=settings.get(perspective);need(reviewer,'Supply a distinct actual reviewer for the required role/perspective, or execute the recorded host handoff.')
        if adapter.session:
            from .review_dispatch import dispatch_session_review
            result=dispatch_session_review(adapter.location,{**reviewer,'perspective':perspective},operation)
            need(result.get('report_status')=='recorded','Independent assessment blocked: '+str(result.get('report_reason_code') or result.get('reason_code'))+' '+str(result.get('report_message','')))
            return result['review_id'],True
        return _workflow_review(adapter,subject,scope,perspective,reviewer,operation),True
    if kind=='close-findings':
        from .finding_index import guard_live_finding
        ids=[]
        for closure in action.get('closures',[]):
            _,current=adapter.read();guard_live_finding(current,'close-finding',closure)
            adapter.event('close-finding',closure,operation+':'+closure['finding_id']);ids.append(closure['finding_id'])
        return digest(sorted(ids)),False
    if kind=='complete-attempt':
        proofs=[(key,p) for key,p in subject.get('verifier_proofs',{}).items() if p.get('item_id')==item_id and p.get('semantic_status')=='reviewed' and p.get('source_identity')==subject['source_identity'] and p.get('passed') is True]
        need(proofs and subject.get('active_attempt'),'Current independently accepted proof and actual active attempt required.')
        adapter.cli('run','result','--root',adapter.location,'--run-id',adapter.run_id,'--attempt-id',subject['active_attempt']['token'],
            '--result',json.dumps({'outcome':'passed','verifier_proof_id':proofs[-1][0]}),'--operation-id',operation)
        return proofs[-1][0],False
    raise WorkflowError('REVIEW_DRIVER_HANDOFF','Use the actual returned workflow stage/host instruction; no missing command or authority is invented.')


def _workflow_review(adapter,subject,scope,perspective,settings,operation):
    from .host_projection import read_host
    from .review_dispatch import dispatch_workflow_review
    from .releases import release_descriptor
    from .reviews import record_review
    from .stored_records import require_package
    packages=[require_package(p) for p in subject.get('review_packages',{}).values()]
    from .adversarial_reviews import adversarial_bindings
    package=next(p for p in reversed(packages) if p.get('role')==scope['role'] and p.get('item_id')==scope.get('item_id') and p.get('adversarial_bindings')==adversarial_bindings(subject,logical(scope)))
    state=read_host(adapter.location,run_id=adapter.run_id);binding_id=settings.get('binding_id')
    binding=state['data'].get('host_bindings',{}).get(binding_id)
    if binding:
        need(binding.get('role')==scope['role']+'-reviewer' and binding.get('perspective')==perspective,'Keep actual role/perspective reviewer identity.')
        if binding.get('package_hash')!=package['package_hash']:
            request={k:binding[k] for k in ('binding_id','session_id','actor_id','host','project_dir','run_id','role','release')}
            request.update(refresh=True,perspective=perspective,package_hash=package['package_hash'])
            if scope.get('item_id'):request['item_id']=scope['item_id']
            adapter.root_event('domain.host.attach',{'request':request},operation+':attach')
            binding=read_host(adapter.location,binding_id=binding_id)['data']['host_bindings'][binding_id]
    else:
        need(binding_id and all(settings.get(k) for k in ('actor_id','session_id','host')),'Provide a genuine reviewer binding or explicit independent actor/host/session identity.')
        request={k:settings[k] for k in ('binding_id','actor_id','session_id','host')}
        request.update(run_id=adapter.run_id,role=scope['role']+'-reviewer',project_dir=next(iter(subject['repositories'].values()))['location'],
            release=release_descriptor(),perspective=perspective,package_hash=package['package_hash'])
        if scope.get('item_id'):request['item_id']=scope['item_id']
        adapter.root_event('domain.host.attach',{'request':request},operation+':attach')
        binding=read_host(adapter.location,binding_id=binding_id)['data']['host_bindings'][binding_id]
    result=dispatch_workflow_review(adapter.location,{'binding_id':binding_id,'revision':binding['revision'],'run_id':adapter.run_id,
        'perspective':perspective,'invocation_id':operation+':model','estimated_cost':settings.get('estimated_cost'),
        'prompt':settings.get('prompt','Assess the full current package and all original obligations.')},operation)
    need(result.get('status')=='allow','Actual independent specialist unavailable or uncertain.')
    ref=result.get('output_ref');target=(adapter.location/ref).resolve() if isinstance(ref,str) else None
    need(target and target.is_relative_to(adapter.location/'artifacts') and target.is_file() and target.stat().st_size<=2*1024*1024,'Retained bounded actual model output required.')
    report=json.loads(target.read_bytes());report.update(package_hash=package['package_hash'],perspective=perspective)
    if scope.get('item_id'):report['item_id']=scope['item_id']
    _,current=adapter.read();review=record_review(current,package['package_hash'],{'role':scope['role'],'actor_id':binding['actor_id'],
        'invocation_ref':result['invocation_ref'],'tool_available':True,'model_invocation_id':result['invocation_id']},report)
    adapter.root_event('review.recorded',{'run_id':adapter.run_id,'review':review},operation+':report')
    return review['review_id']


def advance_orchestration(location:Path,request:dict,operation_id:str)->dict:
    return _advance(location,request,operation_id,digest({'request':request,'max_actions':1}))


def _advance(location,request,operation_id,request_hash):
    from .native_runtime import _native_lease
    from .review_policy import bounded
    bounded(request);need(isinstance(operation_id,str) and operation_id,'Explicit operation identity required.')
    need(not set(request)-{'session','run_id','contract','rationales','implementer','reviewers','repositories','verification','verification_timeout','resume'},'Driver accepts explicit scoped settings only; it never executes commands from findings.')
    adapter=Subject(location,request);key=hashlib.sha256((adapter.run_id or 'session').encode()).hexdigest()
    directory=adapter.location.with_name(adapter.location.name+'.driver-leases') if adapter.session else adapter.location/'review-driver-leases'
    directory.mkdir(parents=True,exist_ok=True);token=DRIVER.set({'location':str(adapter.location),'operation_id':operation_id})
    try:
        with _native_lease(directory/key):
            _,subject=adapter.read();orch=subject.get('review_orchestration',{})
            previous=orch.get('driver_operations',{}).get(operation_id)
            if previous:
                need(previous['request_hash']==request_hash,'Driver identity belongs to a different exact request/action bound.')
                if previous.get('status')=='completed':return {**previous['result'],'replayed':True,'next_action':orchestration_next(subject,now())}
                return {'advanced':False,'executed':False,'kind':'reconcile','reason_code':'DRIVER_OPERATION_UNCERTAIN','replayed':True,'next_action':orchestration_next(subject,now())}
            if request.get('resume') is True and orch.get('blocker'):
                adapter.event('orchestration-clear-blocker',{'input_hash':input_binding(subject)},operation_id+':resume')
                _,subject=adapter.read()
            action=orchestration_next(subject,now())
            if action['kind'] in {'blocked','ask-user','reconcile'}:
                if action['reason_code']=='NO_PROGRESS' and not subject['review_orchestration'].get('blocker'):
                    adapter.event('orchestration-block',{'input_hash':input_binding(subject),'reason_code':'NO_PROGRESS',
                        'required_evidence':action['required_evidence'],'evidence_refs':[c['cycle_id'] for c in subject['review_orchestration']['cycles']]},operation_id+':stop-decision')
                return {'advanced':False,'executed':False,'next_action':action}
            if action['kind']=='complete':
                if adapter.session:
                    from .session_evidence import complete
                    result=complete(adapter.location,operation_id+':complete')
                    return {'advanced':True,'executed':False,'status':'complete','completion':result,'next_action':action}
                return {'advanced':False,'executed':False,'next_action':action}
            if action['kind']=='workflow-stage':return {'advanced':False,'executed':False,'next_action':action,'handoff':'Use the distinct actual workflow gate; this driver cannot fabricate acceptance or delivery.'}
            adapter.live(subject)
            adapter.event('orchestration-driver-claim',{'operation_id':operation_id,'request_hash':request_hash,'owner_pid':os.getpid(),'input_hash':input_binding(subject)},operation_id+':driver-claim')
            _,subject=adapter.read();cycle=next((c for c in subject['review_orchestration']['cycles'] if c['status']=='active'),None)
            if not cycle and action['scope']['finding_ids']:
                action=orchestration_next(subject,now())
                adapter.event('orchestration-begin-cycle',{'cycle_id':operation_id+':cycle','now_ms':now(),'input_hash':action['input_hash']},operation_id+':begin')
                _,subject=adapter.read();cycle=subject['review_orchestration']['cycles'][-1]
            action=orchestration_next(subject,now());cycle_id=cycle['cycle_id'] if cycle else 'final'
            if action['kind']=='finish-cycle':
                adapter.event('orchestration-finish-cycle',{'cycle_id':cycle_id,'now_ms':now(),'input_hash':action['input_hash']},operation_id+':finish-cycle')
                result={'advanced':True,'executed':False,'action':action,'recorded':True}
            else:
                adapter.event('orchestration-claim-action',{'cycle_id':cycle_id,'action_id':operation_id,'now_ms':now(),'input_hash':action['input_hash']},operation_id+':action-claim')
                try:
                    ref,executed=_execute(adapter,request,action,operation_id+':effect')
                    adapter.event('orchestration-record-action',{'cycle_id':cycle_id,'action_id':operation_id,'now_ms':now(),
                        'input_hash':action['input_hash'],'result_ref':ref},operation_id+':action-result')
                    result={'advanced':True,'executed':executed,'action':action,'result_ref':ref}
                except (WorkflowError,ValueError,KeyError,OSError) as exc:
                    result={'advanced':False,'executed':False,'action':action,'reason_code':getattr(exc,'code','REVIEW_DRIVER_BLOCKED'),'message':str(exc)}
                    _,current=adapter.read();active=[row for row in list(current.get('effects',{}).values())+list(current.get('active_executions',{}).values())+list(current.get('executions',{}).values()) if row.get('status') not in {'completed','failed','reconciled'}]
                    if active:
                        result['executed']=None
                    else:
                        execution_id=operation_id+':effect'
                        if adapter.session:
                            executed=current.get('executions',{}).get(execution_id,{})
                            result['executed']=executed.get('status') in {'completed','failed'}
                        else:
                            from .storage_access import operation_lookup
                            finished=operation_lookup(adapter.location,execution_id+':tool-finish')
                            if finished:result['executed']=finished['payload']['request']['record'].get('started') is True
                        if current.get('native_invocations',{}).get(execution_id+':worker',{}).get('status')=='completed':result['executed']=True
                    if not active:
                        adapter.event('orchestration-fail-action',{'operation_id':operation_id,'action_id':operation_id,'cycle_id':cycle_id,'reason_code':result['reason_code']},operation_id+':action-failed')
                        if action['kind']=='verify' and action.get('phase')=='GREEN':
                            failure=_verification_failure(adapter,operation_id+':effect')
                            if failure:
                                try:
                                    adapter.event('orchestration-end-rework',{'operation_id':operation_id,'action_id':operation_id,'cycle_id':cycle_id,'now_ms':now(),'failure':failure},operation_id+':rework')
                                    result.update(advanced=True,executed=True,reason_code='ACTUAL_REGRESSION_REMAINS')
                                except WorkflowError:pass
            adapter.event('orchestration-driver-finish',{'operation_id':operation_id,'request_hash':request_hash,'result':result},operation_id+':driver-finish')
            _,current=adapter.read()
            if not result.get('advanced') and result.get('executed') is not None:
                adapter.event('orchestration-block',{'input_hash':input_binding(current),'reason_code':result['reason_code'],
                    'required_evidence':['resolve the retained failure and request explicit retry'],
                    'evidence_refs':[operation_id+':driver-finish']},operation_id+':block')
            return {**result,'next_action':orchestration_next(adapter.read()[1],now())}
    except WorkflowError as exc:
        if exc.code=='NATIVE_INVOCATION_ACTIVE':return {'advanced':False,'executed':False,'kind':'reconcile','reason_code':'DRIVER_LEASE_HELD'}
        raise
    finally:DRIVER.reset(token)


def run_orchestration(location:Path,request:dict,operation_id:str,max_actions:int)->dict:
    need(type(max_actions) is int and 1<=max_actions<=100,'Explicit finite action count from 1 to 100 required.')
    identity=digest({'request':request,'max_actions':max_actions});steps=[]
    for index in range(max_actions):
        result=_advance(location,request,operation_id+':'+str(index),identity);steps.append(result)
        if not result.get('advanced') or result.get('status')=='complete':break
    return {'steps':steps,'status':'complete' if steps[-1].get('status')=='complete' else 'blocked' if not steps[-1].get('advanced') else 'action-limit',
        'next_action':steps[-1].get('next_action'),'actions':len(steps)}


def _verification_failure(adapter,execution_id):
    """Re-read retained raw failure; this never creates a passing verifier proof."""
    from .test_integrity import parse_test_evidence
    _,subject=adapter.read()
    if adapter.session:
        execution=subject.get('executions',{}).get(execution_id,{})
        result=execution.get('result',{}) if execution.get('status')=='failed' else {}
        source=execution.get('source_observation',{}).get('source_identity')
    else:
        execution=subject.get('verification_failures',{}).get(execution_id,{})
        result=execution.get('result',{});source=execution.get('source_identity')
    integrity=result.get('integrity',{})
    if not integrity or result.get('passed') is not False:return None
    try:
        adapter.live(subject)
        if adapter.session:
            from .storage_objects import read_object
            logs=adapter.location.with_name(adapter.location.name+'.artifacts')
            stdout=read_object(logs,integrity['stdout_ref'],max_bytes=2*1024*1024).decode()
            stderr=read_object(logs,integrity['stderr_ref'],max_bytes=2*1024*1024).decode()
        else:
            def raw(ref):
                target=(adapter.location/ref).resolve();need(target.is_relative_to(adapter.location/'artifacts'),'Actual retained raw report required.')
                value=target.read_bytes();need(hashlib.sha256(value).hexdigest()==target.parent.name+target.name,'Raw failure content changed.')
                return value.decode()
            stdout=raw(integrity['stdout_ref']);stderr=raw(integrity['stderr_ref'])
        parsed=parse_test_evidence(stdout,stderr,integrity['contract']['report_format'])
        need(parsed['outcomes']==integrity['outcomes'] and parsed['classification']==integrity['classification'],'Actual raw failure differs from recorded outcome.')
        return {'execution_id':execution_id,'source_identity':source,'integrity':deepcopy(integrity)}
    except (WorkflowError,KeyError,OSError,UnicodeError,ValueError):return None


def recover_orchestration(location:Path,request:dict,operation_id:str)->dict:
    from .native_runtime import _native_lease
    from .enforcement_recovery import observe
    from .review_sessions import lookup_operation
    from .storage_access import operation_lookup
    adapter=Subject(location,request);original=request.get('original_operation_id')
    need(isinstance(original,str) and original and isinstance(operation_id,str) and operation_id,'Exact original and recovery operation identities required.')
    client_hash=digest({'kind':'driver-recovery','request':request})
    prior=(lookup_operation(adapter.location,operation_id) if adapter.session else operation_lookup(adapter.location,operation_id))
    if prior:
        old=prior.get('client_request_hash') if adapter.session else prior['payload']['request']['record'].get('_client_request_hash')
        need(old==client_hash,'Recovery identity belongs to another exact request.')
        return {'replayed':True,'next_action':orchestration_next(adapter.read()[1],now())}
    key=hashlib.sha256((adapter.run_id or 'session').encode()).hexdigest()
    directory=adapter.location.with_name(adapter.location.name+'.driver-leases') if adapter.session else adapter.location/'review-driver-leases'
    directory.mkdir(parents=True,exist_ok=True)
    with _native_lease(directory/key):
        _,subject=adapter.read();row=subject.get('review_orchestration',{}).get('driver_operations',{}).get(original,{})
        need(row.get('status')=='claimed','Only an outstanding original driver operation needs observed recovery.')
        observation=observe(original,row.get('owner_pid'),original,request.get('worker_stop_confirmation',{}),key)
        active=[e for e in list(subject.get('effects',{}).values())+list(subject.get('active_executions',{}).values())+list(subject.get('executions',{}).values()) if e.get('status') not in {'completed','failed','reconciled'}]
        need(not active,'Reconcile the actual stopped model/tool workers first; driver recovery never relaunches or refunds them.')
        actions=[a for c in subject['review_orchestration'].get('cycles',[]) for a in c.get('actions',[])]+subject['review_orchestration'].get('final_actions',[])
        action=next((a for a in actions if a.get('action_id')==original),None);ref=None
        if action and action['kind']=='verify':
            try:
                adapter.live(subject)
                ref=next((p['id'] for p in subject.get('verification_proofs',{}).values() if p.get('execution_id')==original+':effect'),None)
            except WorkflowError:ref=None
        elif action and action['kind']=='implement':
            candidate=original+':effect:worker'
            try:
                from .review_orchestration import _require_result
                _require_result(subject,action,candidate)
                adapter.observe(operation_id+':source');ref=candidate
            except WorkflowError:ref=None
        token=DRIVER.set({'location':str(adapter.location),'operation_id':original,'mode':'recovery'})
        try:
            adapter.event('orchestration-recover-driver',{'operation_id':original,'request_hash':row['request_hash'],
                'observation':observation,'result_ref':ref,'_client_request_hash':client_hash},operation_id)
        finally:DRIVER.reset(token)
        return {'replayed':False,'recovered_result_ref':ref,'next_action':orchestration_next(adapter.read()[1],now())}
