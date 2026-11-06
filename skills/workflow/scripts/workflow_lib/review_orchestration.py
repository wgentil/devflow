"""Pure opt-in bounded repair steps; descriptors never claim an effect occurred."""
from copy import deepcopy
import math
from .document_units import digest
from .store import WorkflowError
from .review_policy import bounded,require_review_policy

PROTOCOL='devflow.review-orchestration/v1'
TERMINAL={'completed','failed','reconciled','interrupted'}
DISPOSED={'resolved','waived','rejected','deferred'}


def need(ok,message):
    if not ok:raise WorkflowError('ORCHESTRATION_BLOCKED',message)


def selected(subject):return subject.get('review_orchestration',{})


def _scope(subject):
    findings=[f for f in subject.get('unresolved_findings',[]) if f.get('status','open') not in DISPOSED]
    if subject.get('review_contract_hash'):
        return {'role':'session','finding_ids':[f['id'] for f in findings]}
    cycle=_active_cycle(subject)
    if cycle:
        scope=deepcopy(cycle['scope']);scope['finding_ids']=[f['id'] for f in findings if not f.get('item_id') or f.get('item_id')==scope.get('item_id')]
        return scope
    items=sorted({f['item_id'] for f in findings if f.get('item_id')})
    if not items:
        items=[key for key,row in subject.get('items',{}).items() if row.get('status')!='complete']
    item=items[0] if items else None
    return {'role':'item' if item else 'branch',**({'item_id':item} if item else {}),
        'finding_ids':[f['id'] for f in findings if not f.get('item_id') or f.get('item_id')==item]}


def logical(scope):return {k:scope[k] for k in ('role','item_id') if k in scope}


def progress_facts(subject):
    from .finding_index import finding_progress
    progress=finding_progress(subject)
    checks=set(selected(subject).get('verified_check_history',[]))
    for key in subject.get('required_hardening_gates',[]):
        proof=subject.get('hardening_proofs',{}).get(key,{})
        if proof.get('passed') is True and proof.get('source_identity')==subject.get('source_identity') and proof.get('config_hash')==subject.get('hardening_config_hash'):
            checks.add(digest({'id':key,'config':subject.get('hardening_config',{}).get(key)}))
    return {'obligations':progress['verified_obligation_hashes'],'checks':sorted(checks)}


def progress_improved(before,after):
    return bool(set(after.get('obligations',[]))-set(before.get('obligations',[])) or
                set(after.get('checks',[]))-set(before.get('checks',[])))


def progress_signature(subject):
    """Only verified obligations/positive checks count; source/receipt churn does not."""
    return digest(progress_facts(subject))


def input_binding(subject):
    material={k:subject.get(k) for k in ('source_identity','review_policy','review_contract_hash','plan','items',
        'clarifications','implementation_contracts','fix_rationales','verification_proofs','verifier_proofs',
        'hardening_config','hardening_proofs','test_extensions','verification_failures','review_packages','reviews','unresolved_findings','finding_index',
        'effects','effect_policy','native_invocations','model_receipts','model_overrides','active_attempt','review_orchestration')}
    from .stored_records import package_metadata
    material['review_packages']={key:package_metadata(value).get('package_hash') for key,value in subject.get('review_packages',{}).items()}
    material['review_orchestration']={k:v for k,v in selected(subject).items() if k!='blocker'}
    return digest(material)


def _descriptor(subject,kind,reason,scope,*,required=(),**extra):
    from .clarifications import clarification_blockers,current_questions
    pending={q['id'] for q in clarification_blockers(subject,{'item_id':scope['item_id']} if scope.get('item_id') else {})}
    questions=[q for q in current_questions(subject,{}) if q['id'] in pending]
    return {**({'questions':questions} if questions else {}),'schema_version':1,'kind':kind,'scope':deepcopy(scope),'input_hash':input_binding(subject),
        'reason_code':reason,'required_evidence':list(required),'executed':False,**extra}


def _active_cycle(subject):
    return next((c for c in reversed(selected(subject).get('cycles',[])) if c.get('status')=='active'),None)


def _worker(subject,cycle):
    if not cycle:return None
    for action in reversed(cycle.get('actions',[])):
        if action.get('kind')!='implement' or action.get('status')!='recorded':continue
        ref=action.get('result_ref');native=subject.get('native_invocations',{}).get(ref,{})
        receipt=subject.get('model_receipts',{}).get(ref,{})
        if native.get('status')=='completed' and native.get('stage')=='implementation' and receipt.get('status')=='allow' and receipt.get('invocation_ref'):return action
    return None


def _proofs(subject,scope,phase,worker=None):
    rows=[];item=scope.get('item_id');attempts=subject.get('items',{}).get(item,{}).get('attempts',[]) if item else []
    for proof in subject.get('verification_proofs',{}).values():
        if proof.get('phase')!=phase or proof.get('passed') is not True or proof.get('fresh') is False:continue
        extension=subject.get('test_extensions',{}).get(item or 'session')
        if extension and proof.get('integrity',{}).get('contract',{}).get('test_extension_hash')!=extension.get('extension_hash'):continue
        if item and (proof.get('item_id')!=item or not attempts or proof.get('token')!=attempts[-1].get('token')):continue
        if subject.get('review_contract_hash') and proof.get('contract_hash')!=subject['review_contract_hash']:continue
        if phase=='RED':
            if worker:
                if proof.get('id') not in worker.get('baseline_proof_ids',[]):continue
            elif proof.get('source_identity')!=subject.get('source_identity') and proof.get('id') not in ((_active_cycle(subject) or {}).get('carried_baseline_ids',[])):continue
            integrity=proof.get('integrity',{});contract=integrity.get('contract',{});targets=contract.get('targets',[])
            from .clarifications import clarification_binding
            if contract.get('clarification_binding')!=clarification_binding(subject,{'item_id':item} if item else {}):continue
            if item and contract.get('spec_hash')!=subject.get('plan',{}).get('spec_hash'):continue
            if not item and contract.get('session_contract_hash')!=subject.get('review_contract_hash'):continue
            if not targets or not any(integrity.get('outcomes',{}).get(t)=='failed' and integrity.get('classification',{}).get(t)=='assertion' for t in targets):continue
        elif (proof.get('source_identity')!=subject.get('source_identity') or not worker or
                not any(rid in subject.get('verification_proofs',{}) and (proof.get('red_proof_id')==rid or (proof.get('integrity',{}).get('baseline_source') and proof.get('integrity',{}).get('baseline_source')==subject['verification_proofs'][rid].get('source_identity') and proof.get('integrity',{}).get('contract')==subject['verification_proofs'][rid].get('integrity',{}).get('contract'))) for rid in worker.get('baseline_proof_ids',[]))):continue
        rows.append(proof)
    return rows


def orchestration_next(subject:dict,now_ms:int)->dict:
    need(type(now_ms) is int and now_ms>=0,'Current nonnegative time required.')
    state=selected(subject);policy=state.get('policy',{});scope=_scope(subject)
    out=lambda kind,reason,**extra:_descriptor(subject,kind,reason,scope,**extra)
    if not state:return out('blocked','REPAIR_DISABLED')
    if policy.get('protocol')!=PROTOCOL or policy.get('schema_version')!=1:return out('blocked','UNSUPPORTED_ORCHESTRATION_POLICY')
    if policy.get('enabled') is not True:return out('blocked','REPAIR_DISABLED')
    if subject.get('status')!='active':return out('blocked','SCOPE_NOT_ACTIVE')
    if policy.get('effect_policy_hash')!=digest(subject.get('effect_policy',{})):return out('blocked','SHARED_BUDGET_CHANGED',required=['explicit current shared-budget extension'])
    if now_ms-state['started_ms']>=policy['max_elapsed_ms']:return out('blocked','TIME_LIMIT')
    if now_ms<state['started_ms']:return out('blocked','CLOCK_REGRESSION')
    effects=subject.get('effects',{});shared=sum(max(r.get('estimated_cost',0),r.get('observed_cost',0)) for r in effects.values())
    legacy=sum(r.get('estimated_cost',0) for r in subject.get('repair_cycles',[]))
    if max(shared,legacy)>policy['max_estimated_cost']:return out('blocked','SPEND_LIMIT')
    cycle=_active_cycle(subject);cycles=state.get('cycles',[])
    if scope['finding_ids'] and not cycle and len(cycles)+len(subject.get('repair_cycles',[]))>=policy['max_attempts']:return out('blocked','ATTEMPT_LIMIT')
    recent=cycles[-policy['no_progress_window']:]
    if scope['finding_ids'] and not cycle and len(recent)==policy['no_progress_window'] and all(c.get('status')=='recorded' and not c.get('made_progress',c.get('before_progress')!=c.get('after_progress')) for c in recent):return out('blocked','NO_PROGRESS')
    active={key:row for key,row in {**effects,**subject.get('active_executions',{}),**subject.get('executions',{})}.items() if row.get('status') not in TERMINAL}
    if any(a.get('status')=='claimed' for a in (cycle.get('actions',[]) if cycle else state.get('final_actions',[]))):
        return out('reconcile','ORCHESTRATION_ACTION_UNCERTAIN',required=['original action completion or observed recovery'])
    if active:return out('reconcile','ACTIVE_OR_UNCERTAIN_EFFECT',invocation_ids=sorted(active),required=['original worker stopped/reconciled or actual completion'])
    from .clarifications import clarification_blockers,current_questions
    ids={q['id'] for q in clarification_blockers(subject,{'item_id':scope['item_id']} if scope.get('item_id') else {})}
    questions=[q for q in current_questions(subject,{}) if q['id'] in ids]
    if questions:return out('ask-user','BUSINESS_CLARIFICATION_REQUIRED',questions=questions,required=['actual user answer for exact question version'])
    blocker=state.get('blocker',{})
    if blocker.get('input_hash')==input_binding(subject):return out('blocked',blocker['reason_code'],required=blocker.get('required_evidence',[]),evidence_refs=blocker.get('evidence_refs',[]))
    if subject.get('repair_human_decision_required'):return out('ask-user','MATERIAL_AMENDMENT_REQUIRED',required=['approved governing amendment and replanning'])
    from .implementation_contracts import implementation_prerequisites,rationale_current
    prerequisites=implementation_prerequisites(subject,logical(scope))
    if prerequisites['status']!='allow':return out('contract','IMPLEMENTATION_CONTRACT_MISSING_OR_STALE',required=prerequisites['reason_codes'])
    findings=scope['finding_ids'];worker=_worker(subject,cycle)
    if findings and not worker:
        if scope['role']=='branch':return out('blocked','AFFECTED_ITEM_MAPPING_REQUIRED',required=['actual affected work item mapping for global findings'])
        if scope.get('item_id') and subject.get('items',{}).get(scope['item_id'],{}).get('status')=='complete':return out('retry-item','AFFECTED_ITEM_RETRY_REQUIRED',required=['existing authorized item retry/invalidation transition'])
        reds=_proofs(subject,scope,'RED')
        if not reds:return out('verify','REGRESSION_BASELINE_REQUIRED',phase='RED',required=['explicit applicable verifier argv/targets','actual relevant assertion failure before implementation'])
        if any(not rationale_current(subject,fid) for fid in findings):return out('rationale','FIX_RATIONALE_REQUIRED',required=['current observed failure/cause or hypothesis/correction rationale'])
        return out('implement','REVIEW_DRIVEN_REPAIR_AVAILABLE',baseline_proof_ids=[p['id'] for p in reds],required=['independent actual implementer','eligible model and known finite cost','current declared repair authorization'])
    if worker:
        # A successful native receipt alone never establishes corrected behavior.
        from .implementation_contracts import review_prerequisites
        prereq=review_prerequisites(subject,logical(scope))
        cheap=[c for c in prereq.get('missing_checks',[]) if not c.startswith('focused-test:')]
        if cheap:return out('check','CONFIGURED_CHEAP_CHECK_REQUIRED',gate_id=cheap[0],required=['actual configured prerequisite command'])
        if not _proofs(subject,scope,'GREEN',worker):return out('verify','CORRECTED_VERIFICATION_REQUIRED',phase='GREEN',required=['actual linked current GREEN preserving baseline contract'])
    from .adversarial_reviews import review_coverage
    from .session_evidence import package_current as session_current
    from .review_enforcement import review_bindings_current
    packages=[p for p in subject.get('review_packages',{}).values() if p.get('role')==scope['role'] and p.get('item_id')==scope.get('item_id')]
    current=[p for p in packages if (session_current(subject,p) if scope['role']=='session' else review_bindings_current(subject,p,live=False))]
    if not current:return out('package','CURRENT_REVIEW_PACKAGE_REQUIRED',required=['fresh exact scope and full input artifact'])
    # Individual findings can close in an overall request-changes assessment.
    # Never wait for unrelated findings to disappear before admitting real progress.
    if findings:
        from .finding_closure import validate_closure
        closures=[]
        for fid in findings:
            refs=[r['review_id'] for r in subject.get('reviews',{}).get(scope['role'],[]) if any(
                d.get('finding_id')==fid and d.get('disposition')=='resolved' for d in r.get('closure_dispositions',[]))]
            if not refs:continue
            try:validate_closure(subject,{'finding_id':fid,'review_ids':refs})
            except WorkflowError:continue
            closures.append({'finding_id':fid,'review_ids':refs})
        if closures:return out('close-findings','INDEPENDENT_FINDING_CLOSURE_REQUIRED',closures=closures,
            required=['live current source/protection and actual dispositions for every selected original obligation'])
    coverage=review_coverage(subject,scope['role'],scope.get('item_id'))
    if not coverage['complete']:
        required=set(coverage.get('required_perspectives',[]));assessed=set()
        from .finding_index import _recorded_review
        for review in subject.get('reviews',{}).get(scope['role'],[]):
            if review.get('item_id')!=scope.get('item_id') or review.get('package_hash') not in {p['package_hash'] for p in current}:continue
            try:_recorded_review(subject,review['review_id'],diagnostic_allowed=False)
            except WorkflowError:continue
            assessed.add(review.get('perspective'))
        if cycle and worker and required and required.issubset(assessed):
            return out('finish-cycle','INDEPENDENT_REWORK_REMAINS')
        missing=coverage.get('missing_perspectives',[])
        return out('review','INDEPENDENT_REVIEW_REQUIRED',perspective=missing[0] if missing else None,required=coverage.get('reason_codes',[]))
    if findings:return out('close-findings','INDEPENDENT_FINDING_CLOSURE_REQUIRED',required=['each original current proof, independent disposition and required perspectives'])
    if scope.get('item_id') and subject.get('active_attempt') and subject['active_attempt'].get('item_id')==scope['item_id']:
        return out('complete-attempt','INDEPENDENT_ITEM_PROOF_ACCEPTED',required=['existing run.result with actual accepted verifier proof'])
    if cycle:return out('finish-cycle','PROGRESS_EVALUATION_REQUIRED')
    if scope['role']=='session':return out('complete','CURRENT_SESSION_COVERAGE_COMPLETE')
    from .gates import gate_status
    stage=gate_status(subject,live=False)
    return out('complete' if stage.get('stage')=='delivery' else 'workflow-stage','ALL_CHECKS_PASS' if stage.get('stage')=='delivery' else 'DISTINCT_WORKFLOW_GATE_REQUIRED',stage=stage.get('stage'))


def apply_orchestration(subject:dict,action:str,record:dict)->dict:
    bounded(record);require_review_policy(subject);updated=deepcopy(subject)
    need(subject.get('status')=='active','Only active subjects can change orchestration.')
    if action in {'configure','extend'}:
        policy=record.get('policy',{});auth=record.get('authorization',{})
        need(set(policy)=={'protocol','schema_version','enabled','max_attempts','max_elapsed_ms','max_estimated_cost','no_progress_window','effect_policy_hash'} and
            policy.get('protocol')==PROTOCOL and policy.get('schema_version')==1 and type(policy.get('enabled')) is bool,'Exact supported policy fields required.')
        need(all(type(policy[k]) is int and policy[k]>0 for k in ('max_attempts','max_elapsed_ms','no_progress_window')) and policy['no_progress_window']>=2
             and type(policy['max_estimated_cost']) in (int,float) and math.isfinite(policy['max_estimated_cost']) and policy['max_estimated_cost']>=0,'Explicit finite orchestration limits required.')
        need(policy['effect_policy_hash']==digest(subject.get('effect_policy',{})) and subject.get('effect_policy'),'Bind the existing explicitly authorized shared effect budget.')
        need(auth.get('approved') is True and auth.get('actor_id') and auth.get('policy_hash')==digest(policy)
            and auth.get('provenance',{}).get('kind')=='user-message' and auth['provenance'].get('ref'),'Actual user authorization must bind the exact policy.')
        stamp=record.get('now_ms');need(type(stamp) is int and stamp>=0,'Actual configuration time required.')
        if action=='configure':
            need(not selected(subject),'Existing orchestration needs an explicit monotonic extension; no counter/clock reset.')
            clocks=[stamp]+[subject[k] for k in ('repair_started_ms','effects_started_ms') if type(subject.get(k)) is int]
            updated['review_orchestration']={'schema_version':1,'policy':deepcopy(policy),'authorization':deepcopy(auth),'started_ms':min(clocks),'cycles':[],'history':[]}
        else:
            previous=selected(subject);need(previous and record.get('previous_policy_hash')==digest(previous['policy']),'Exact existing policy required for extension.')
            need(all(policy[k]>=previous['policy'][k] for k in ('max_attempts','max_elapsed_ms','max_estimated_cost','no_progress_window')),'Limits can only be explicitly extended.')
            need(not any(a.get('status')=='claimed' for c in selected(subject).get('cycles',[]) for a in c.get('actions',[])) and
                 not any(e.get('status') not in TERMINAL for e in {**subject.get('effects',{}),**subject.get('active_executions',{}),**subject.get('executions',{})}.values()),'Reconcile all work before extension; an idle waiting cycle retains its identity.')
            updated['review_orchestration'].setdefault('history',[]).append({'policy':deepcopy(previous['policy']),'authorization':deepcopy(auth)})
            updated['review_orchestration']['policy']=deepcopy(policy)
        return updated
    state=updated.get('review_orchestration');need(state,'Explicit policy required.')
    if action=='recover-driver':
        operations=state.get('driver_operations',{});row=operations.get(record.get('operation_id'),{})
        need(row.get('status')=='claimed' and row.get('request_hash')==record.get('request_hash'),'Recover the original outstanding driver claim only.')
        from .enforcement_recovery import validate_tool_observation
        validate_tool_observation({'id':record['operation_id'],'owner_pid':row['owner_pid']},record.get('observation',{}))
        need(not any(e.get('status') not in TERMINAL for e in {**subject.get('effects',{}),**subject.get('active_executions',{}),**subject.get('executions',{})}.values()),'Reconcile each actual native/tool worker before driver recovery.')
        actions=[a for c in state.get('cycles',[]) for a in c.get('actions',[])]+state.get('final_actions',[])
        action_row=next((a for a in actions if a.get('action_id')==record['operation_id']),None)
        ref=record.get('result_ref')
        if action_row and action_row['status']=='claimed':
            if ref:
                _require_result(subject,action_row,ref)
                action_row.update(status='recorded',result_ref=ref,record_hash=digest(record),recovered=True)
            else:action_row.update(status='reconciled',recovery=deepcopy(record['observation']))
        row.update(status='completed' if ref else 'reconciled',recovery=deepcopy(record['observation']),
            result={'advanced':bool(ref),'executed':bool(ref),'result_ref':ref,'recovered':True})
        return updated
    if action in {'driver-claim','driver-finish'}:
        identifier=record.get('operation_id');operations=state.setdefault('driver_operations',{})
        need(isinstance(identifier,str) and identifier,'Explicit driver operation required.')
        previous=operations.get(identifier)
        if action=='driver-claim':
            if previous:
                need(previous.get('request_hash')==record.get('request_hash'),'Driver operation belongs to another request.')
                return updated
            need(record.get('input_hash')==input_binding(subject) and type(record.get('owner_pid')) is int and record['owner_pid']>0,'Exact current driver predecessor and actual owner required.')
            operations[identifier]={**deepcopy(record),'status':'claimed'}
        else:
            need(previous and previous.get('status')=='claimed' and previous.get('request_hash')==record.get('request_hash'),'Exact outstanding driver request required.')
            need(isinstance(record.get('result'),dict),'Retain the actual bounded action result.')
            previous.update(status='completed',result=deepcopy(record['result']))
        return updated
    if action=='block':
        need(record.get('input_hash')==input_binding(subject) and isinstance(record.get('reason_code'),str) and record['reason_code']
             and isinstance(record.get('required_evidence'),list) and record.get('evidence_refs'),'Current actual preflight blocker and evidence required.')
        state['blocker']=deepcopy(record)
        if record['reason_code']=='NO_PROGRESS':
            identity=digest({'reason_code':record['reason_code'],'evidence_refs':record['evidence_refs']})
            state.setdefault('stop_records',{})[identity]=deepcopy(record)
            state['blocker']['input_hash']=input_binding(updated)
        return updated
    if action=='clear-blocker':
        need(record.get('input_hash')==input_binding(subject),'Explicit retry must bind the current predecessor; it cannot refund limits.')
        state.pop('blocker',None)
        return updated
    if action=='begin-cycle':
        existing=next((c for c in state['cycles'] if c.get('cycle_id')==record.get('cycle_id')),None)
        if existing:
            need(existing.get('claim_hash')==digest(record),'Cycle identity belongs to another request.')
            return updated
        next_=orchestration_next(subject,record.get('now_ms'))
        need(not _active_cycle(subject) and record.get('cycle_id') and next_['kind'] not in {'blocked','ask-user','reconcile','complete'} and next_['input_hash']==record.get('input_hash'),'Exact current eligible predecessor required.')
        from .finding_closure import finding_hash
        hashes={f['id']:finding_hash(f) for f in subject.get('unresolved_findings',[]) if f['id'] in next_['scope']['finding_ids']}
        previous=state['cycles'][-1] if state['cycles'] else {}
        carried=previous.get('baseline_proof_ids',[]) if previous.get('outcome')=='rework' and previous.get('finding_hashes')==hashes else []
        state['cycles'].append({'finding_hashes':hashes,'carried_baseline_ids':carried,'cycle_id':record['cycle_id'],'status':'active','started_ms':record['now_ms'],
            'claim_hash':digest(record),'scope':deepcopy(next_['scope']),'before_progress':progress_signature(subject),'before_facts':progress_facts(subject),'actions':[]})
        return updated
    if action=='end-rework':
        cycle=_active_cycle(updated);need(cycle and cycle['cycle_id']==record.get('cycle_id'),'Current failed repair cycle required.')
        action_row=next((a for a in cycle['actions'] if a['action_id']==record.get('action_id')),None)
        failure=record.get('failure',{});worker=_worker(subject,cycle)
        need(action_row and action_row['kind']=='verify' and action_row.get('phase')=='GREEN' and action_row['status']=='failed' and worker,'Only a real failed corrected verification can end a rework cycle.')
        execution=subject.get('executions',{}).get(failure.get('execution_id'),{})
        stored=(execution.get('result',{}) if execution.get('status')=='failed' else subject.get('verification_failures',{}).get(failure.get('execution_id'),{}).get('result',{}))
        integrity=failure.get('integrity',{});targets=integrity.get('contract',{}).get('targets',[])
        need(stored.get('integrity')==integrity and stored.get('passed') is False and failure.get('source_identity')==subject.get('source_identity')
             and type(integrity.get('exit_code')) is int and integrity['exit_code']!=0 and targets
             and all(integrity.get('outcomes',{}).get(t) in {'failed','passed'} for t in targets)
             and any(integrity['outcomes'][t]=='failed' for t in targets)
             and all(integrity['classification'].get(t)=='assertion' for t in targets if integrity['outcomes'][t]=='failed'),
             'Actual relevant assertion failure required; missing tools/setup/imports/unknown phases cannot authorize automatic rework.')
        baselines=_proofs(subject,cycle['scope'],'RED',worker)
        need(any(p.get('integrity',{}).get('contract')==integrity['contract'] for p in baselines),'Preserve the original actual regression contract and current authority/answers.')
        facts=progress_facts(subject)
        cycle.update(status='recorded',outcome='rework',finished_ms=record['now_ms'],after_progress=progress_signature(subject),after_facts=facts,
            made_progress=progress_improved(cycle.get('before_facts',{}),facts),failure=deepcopy(failure),baseline_proof_ids=worker['baseline_proof_ids'])
        return updated
    if action=='fail-action':
        cycle=_active_cycle(updated);actions=cycle['actions'] if cycle else state.get('final_actions',[])
        row=next((a for a in actions if a.get('action_id')==record.get('action_id')),None)
        need(row and row['status']=='claimed' and not any(e.get('status') not in TERMINAL for e in {**subject.get('effects',{}),**subject.get('active_executions',{}),**subject.get('executions',{})}.values()),'Only known ended/non-dispatched work can fail an action; uncertainty requires recovery.')
        row.update(status='failed',reason_code=record.get('reason_code'))
        return updated
    if action in {'claim-action','record-action'}:
        cycle=_active_cycle(updated);need((cycle and cycle['cycle_id']==record.get('cycle_id')) or (not cycle and record.get('cycle_id')=='final'),'Current cycle/final-validation identity required.')
        actions=cycle['actions'] if cycle else state.setdefault('final_actions',[]);existing=next((r for r in actions if r['action_id']==record.get('action_id')),None)
        if action=='claim-action':
            if existing:
                need(existing['claim_hash']==digest(record),'Action belongs to another predecessor.')
                return updated
            next_=orchestration_next(subject,record.get('now_ms'))
            need(next_['input_hash']==record.get('input_hash') and next_['kind'] not in {'blocked','ask-user','reconcile','complete','finish-cycle'},'Exact executable predecessor required.')
            need(isinstance(record.get('action_id'),str) and record['action_id'],'Explicit action identity required.')
            actions.append({**deepcopy(next_),'action_id':record['action_id'],'status':'claimed','claim_hash':digest(record),
                'claimed_ms':record['now_ms'],'source_identity':subject.get('source_identity')})
            return updated
        need(existing and existing['input_hash']==record.get('input_hash'),'Recorded result belongs to the original claimed action.')
        if existing.get('status')=='recorded':
            need(existing.get('record_hash')==digest(record),'Immutable result identity required.')
            return updated
        need(type(record.get('now_ms')) is int and record['now_ms']>=existing['claimed_ms'],'Monotonic result time required.')
        _require_result(subject,existing,record.get('result_ref'))
        existing.update(status='recorded',result_ref=record['result_ref'],record_hash=digest(record),finished_ms=record['now_ms'])
        return updated
    if action=='finish-cycle':
        cycle=_active_cycle(updated);need(cycle and cycle['cycle_id']==record.get('cycle_id'),'Current active cycle required.')
        next_=orchestration_next(subject,record.get('now_ms'))
        need(record.get('input_hash')==next_['input_hash'] and next_['kind']=='finish-cycle','Actual verification, independent review and closure must precede cycle completion.')
        facts=progress_facts(subject)
        cycle.update(status='recorded',finished_ms=record['now_ms'],after_progress=progress_signature(subject),
            after_facts=facts,made_progress=progress_improved(cycle.get('before_facts',{}),facts))
        state['verified_check_history']=facts['checks']
        return updated
    raise WorkflowError('ORCHESTRATION_BLOCKED','Unknown orchestration transition.')


def _require_result(subject,action,ref):
    kind=action['kind'];scope=action['scope']
    need(isinstance(ref,str) and ref,'Actual retained result reference required.')
    if kind=='implement':
        native=subject.get('native_invocations',{}).get(ref,{})
        receipt=subject.get('model_receipts',{}).get(ref,{})
        need(native.get('status')=='completed' and native.get('stage')=='implementation' and receipt.get('status')=='allow'
             and receipt.get('invocation_ref') and receipt.get('scope',{}).get('actor_id')==subject.get('actors',{}).get('implementer'),
             'Only the actual completed implementer can finish implementation; verification still follows.')
        effect=subject.get('effects',{}).get(ref,{})
        need(effect.get('source_identity')==action.get('source_identity') and effect.get('claimed_at_ms',-1)>=action.get('claimed_ms',0),
             'Worker reservation must follow this action on the same original source.')
        if scope.get('item_id'):
            attempts=subject.get('items',{}).get(scope['item_id'],{}).get('attempts',[])
            need(attempts and receipt.get('scope',{}).get('item_id')==scope['item_id'] and receipt['scope'].get('token')==attempts[-1].get('token'),
                 'Worker result must bind the selected current item attempt.')
        else:need(receipt.get('scope',{}).get('session_id')==subject.get('id'),'Worker result must bind this actual standalone session.')
    elif kind=='verify':
        worker=_worker(subject,_active_cycle(subject))
        proofs=_proofs(subject,scope,action['phase'],worker)
        need(any(p.get('id')==ref for p in proofs),'Actual applicable current proof required; setup/import failure and unrelated evidence do not qualify.')
    elif kind=='check':
        proof=subject.get('hardening_proofs',{}).get(action['gate_id'],{})
        need(ref==action['gate_id'] and proof.get('passed') is True and proof.get('source_identity')==subject.get('source_identity')
             and proof.get('config_hash')==subject.get('hardening_config_hash'),'Current configured check evidence required.')
    elif kind=='package':
        package=subject.get('review_packages',{}).get(ref,{})
        need(package.get('source_identity')==subject.get('source_identity') and package.get('role')==scope['role'] and package.get('item_id')==scope.get('item_id'),'Exact current package required.')
    elif kind=='review':
        from .finding_index import _recorded_review
        review,_=_recorded_review(subject,ref)
        need(review.get('role')==scope['role'] and review.get('item_id')==scope.get('item_id') and review.get('perspective')==action.get('perspective'),'Actual scoped specialist result required.')
    elif kind=='close-findings':
        ids={r['finding_id'] for r in action.get('closures',[])}
        need(ref==digest(sorted(ids)) and ids and all(f.get('status')=='resolved' for f in subject.get('unresolved_findings',[]) if f['id'] in ids),'Original member closure transitions required.')
    elif kind=='contract':
        from .implementation_contracts import implementation_prerequisites
        need(implementation_prerequisites(subject,logical(scope))['status']=='allow','Current derived contract required.')
    elif kind=='rationale':
        from .implementation_contracts import rationale_current
        need(all(rationale_current(subject,fid) for fid in scope['finding_ids']),'Current rationale required for every selected finding.')
    elif kind=='complete-attempt':
        item=subject.get('items',{}).get(scope.get('item_id'),{})
        need(item.get('status')=='complete' and item.get('attempts') and item['attempts'][-1].get('result',{}).get('verifier_proof_id')==ref,'Actual existing item result transition required.')
    elif kind=='retry-item':
        need(subject.get('active_attempt',{}).get('item_id')==scope.get('item_id'),'Actual existing retry/attempt transition required.')
    else:raise WorkflowError('ORCHESTRATION_BLOCKED','Unsupported recorded action kind.')


def remaining_seconds(subject,now_ms):
    state=selected(subject);policy=state.get('policy',{})
    if not state or policy.get('enabled') is not True:return None
    need(policy.get('protocol')==PROTOCOL and policy.get('schema_version')==1 and
         policy.get('effect_policy_hash')==digest(subject.get('effect_policy',{})),'Current supported orchestration/shared-budget binding required.')
    remaining=policy['max_elapsed_ms']-(now_ms-state['started_ms'])
    need(now_ms>=state['started_ms'] and remaining>0,'Orchestration elapsed limit reached before effect.')
    return remaining/1000


def allow_reservation(subject,cost,now_ms):
    remaining=remaining_seconds(subject,now_ms)
    if remaining is None:return
    need(type(cost) in (int,float) and math.isfinite(cost) and cost>=0,'Known finite cost required before actual dispatch.')
    spent=sum(max(row.get('estimated_cost',0),row.get('observed_cost',0)) for row in subject.get('effects',{}).values())
    legacy=sum(row.get('estimated_cost',0) for row in subject.get('repair_cycles',[]))
    need(max(spent,legacy)+cost<=selected(subject)['policy']['max_estimated_cost'],'Orchestration spending limit reached before actual reservation.')
