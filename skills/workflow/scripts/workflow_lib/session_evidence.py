"""Standalone enforcement primitives. No workflow plan, run or model orchestration."""
from copy import deepcopy
from contextvars import ContextVar
from pathlib import Path
import time
import os
import uuid
from .store import WorkflowError
from .document_units import digest
from .action_policy import require_action, subject_decision
from .clarifications import clarification_binding,current_questions
from .test_integrity import parse_test_evidence, validate_test_pair
from .protection_receipts import validate_receipts
from .test_extensions import session_verification


SESSION_EXECUTION=ContextVar('devflow_session_execution',default=None)

def need(ok, message):
    if not ok: raise WorkflowError('SESSION_EVIDENCE_BLOCKED', message)


def context(subject):
    return {'contract_hash':subject['review_contract_hash'],'source_identity':subject.get('source_identity'),
        'clarification_binding':clarification_binding(subject,{}),'question_answers':current_questions(subject,{}),
        'proof_ids':sorted(p['id'] for p in subject.get('verification_proofs',{}).values()
            if p.get('source_identity')==subject.get('source_identity') and p.get('fresh') is not False),
        'findings':{f['id']:{k:v for k,v in f.items() if k not in {'status','resolution'}}
            for f in subject.get('unresolved_findings',[])}}


def package_current(subject, package):
    if not isinstance(package,dict) or package.get('session_id')!=subject['id']:
        return False
    from .review_policy import review_version
    if review_version(subject) is not None:
        if (package.get('review_contract')!=subject.get('review_contract')
                or package.get('review_contract_hash')!=subject.get('review_contract_hash')
                or digest(package.get('review_contract'))!=subject.get('review_contract_hash')):return False
        from .adversarial_reviews import adversarial_bindings
        if package.get('adversarial_bindings')!=adversarial_bindings(subject,{'role':'session'}):return False
    bound=package.get('context',{});current=context(subject)
    # New findings are review output; packaged input obligations must remain exact.
    return ({k:v for k,v in bound.items() if k!='findings'}=={k:v for k,v in current.items() if k!='findings'}
        and all(current['findings'].get(k)==v for k,v in bound.get('findings',{}).items())
        and package.get('package_hash')==digest({k:v for k,v in package.items() if k!='package_hash'}))


def reduce_session(subject, action, record):
    need(subject.get('review_contract_hash'),'Standalone contract required.')
    updated=deepcopy(subject)
    if action=='execution-claim':
        require_action(subject_decision(subject,'proof',{}))
        need(record.get('id') not in subject.get('executions',{}) and record.get('contract_hash')==subject['review_contract_hash']
             and record.get('clarification_binding')==clarification_binding(subject,{}),'Fresh execution identity and contract required.')
        need(not any(e['status'] in {'launching','uncertain'} for e in subject.get('executions',{}).values()),'An execution is active or uncertain.')
        observation=record.get('source_observation',{})
        need(observation.get('source_identity')==digest(observation.get('snapshots',{})),'Actual source observation required.')
        updated['source_identity']=observation['source_identity'];updated['source_observation']=observation
        updated.setdefault('executions',{})[record['id']]={**deepcopy(record),'status':'launching'}
    elif action=='execution-finish':
        row=updated.get('executions',{}).get(record.get('id'))
        need(row and row['status']=='launching' and record.get('status') in {'completed','failed','uncertain'},'Known active execution required.')
        row.update(deepcopy(record))
    elif action=='execution-reconcile':
        claimed=updated.get('executions',{}).get(record.get('id'),{})
        need(claimed.get('status') in {'launching','uncertain'},'Known uncertain execution required.')
        from .enforcement_recovery import validate_tool_observation
        validate_tool_observation(claimed,record.get('observation',{}))
        claimed.update(status='reconciled',termination_observation=deepcopy(record['observation']))
    elif action=='session-proof':
        require_action(subject_decision(subject,'proof',{}))
        proof=record['proof'];contract=proof['integrity']['contract'];execution=subject.get('executions',{}).get(proof.get('execution_id'))
        need(execution and execution['status']=='launching' and proof.get('session_id')==subject['id']
             and proof.get('contract_hash')==subject['review_contract_hash']
             and contract.get('clarification_binding')==clarification_binding(subject,{})
             and execution.get('source_observation')==proof.get('source_observation')
             and execution.get('verification_contract')==contract
             and execution.get('protection_receipts')==proof.get('protection_receipts'), 'Current exact session execution, source, protection and user decisions required.')
        observation=proof.get('source_observation',{})
        need(observation.get('source_identity')==digest(observation.get('snapshots',{}))==proof.get('source_identity'),'Bound executed source required.')
        verification=session_verification(subject)
        need(contract.get('tool')==verification.get('argv') and contract.get('targets')==sorted(set(verification.get('target_ids',[])))
             and set(contract.get('input_hashes',{}))==set(verification.get('input_paths',[]))
             and contract.get('oracle_authority')==verification.get('authority_refs')
             and contract.get('session_contract_hash')==subject['review_contract_hash'],'Declared standalone verification contract required.')
        from .test_extensions import current_extension,session_item
        extension=current_extension(subject,session_item(subject))
        need(not extension or all(contract.get('input_bindings',{}).get(name)==value for name,value in extension['input_bindings'].items()),'Supplemental regression inputs changed.')
        need(not extension or contract.get('test_extension_hash')==extension['extension_hash'],'Current supplemental test contract required.')
        validate_receipts(subject,proof.get('protection_receipts'))
        need(contract.get('protection_context_hash')==digest(proof['protection_receipts']),'Protected test context must match execution.')
        integrity=proof['integrity'];targets=contract['targets']
        if proof['phase']=='RED':
            need(type(integrity.get('exit_code')) is int and integrity['exit_code']!=0 and all(t in integrity['outcomes'] and integrity['outcomes'][t] in {'failed','passed'} for t in targets)
                 and any(integrity['outcomes'][t]=='failed' and integrity['classification'].get(t)=='assertion' for t in targets),'Relevant target assertion RED required.')
        else:
            red=subject.get('verification_proofs',{}).get(proof.get('red_proof_id'),{})
            validate_test_pair(red.get('integrity',{}),integrity,contract,require_review=False)
        updated['source_identity']=proof['source_identity'];updated['source_observation']=observation
        updated.setdefault('verification_proofs',{})[proof['id']]=deepcopy(proof)
        updated['executions'][proof['execution_id']].update(status='completed',proof_id=proof['id'])
    elif action=='session-package':
        package=record['package']
        need(package_current(subject,package),'Current source/contract/proof/question package required.')
        from .protection_receipts import validate_diagnostic_observations
        validate_diagnostic_observations(subject,package.get('protection_observations'))
        updated.setdefault('review_packages',{})[package['package_hash']]=deepcopy(package)
    elif action=='session-review':
        review=record['review'];package=subject.get('review_packages',{}).get(review.get('package_hash'))
        need(package_current(subject,package) and review.get('actor_id') and review.get('invocation_ref')
             and review['actor_id']!=subject.get('actors',{}).get('implementer')
             and review.get('verdict') in {'pass','request-changes','block'},'Current independent session assessment required.')
        need(not any(r.get('invocation_ref')==review['invocation_ref'] for rows in subject.get('reviews',{}).values() for r in rows),'Each assessment requires a fresh actual invocation.')
        from .review_policy import review_version
        if review_version(subject) is not None:
            from .adversarial_reviews import validate_adversarial_review
            review={**review,'role':'session','review_id':digest(review),'fresh':True,
                'adversarial_bindings':package.get('adversarial_bindings')}
            validate_adversarial_review(subject,package,review)
        owns_oracles=review_version(subject) is None or review.get('perspective')=='test'
        approvals=[]
        for oracle in (review.get('test_oracles',[]) if owns_oracles else []):
            green=subject.get('verification_proofs',{}).get(oracle.get('green_proof_id'),{})
            red=subject.get('verification_proofs',{}).get(oracle.get('red_proof_id'),{})
            need(green.get('source_identity')==subject['source_identity'] and green.get('red_proof_id')==red.get('id'), 'Current actual linked pair required.')
            need(all(green.get('protection_receipts',{}).get(k,{}).get('after_hash')==digest(v['after']) for k,v in package['protection_observations'].items()),'Renew proof after protected context changes.')
            contract=green['integrity']['contract'];validate_test_pair(red['integrity'],green['integrity'],contract,require_review=False)
            need(oracle.get('input_hashes')==contract['input_hashes'] and oracle.get('authority_refs')==contract['oracle_authority']
                 and oracle.get('failure_relevance'),'Independent actual oracle/failure relevance required.')
            approvals.append(green['id'])
        greens=[p['id'] for p in subject.get('verification_proofs',{}).values() if p['phase']=='GREEN' and p['source_identity']==subject['source_identity'] and p.get('fresh') is not False]
        if owns_oracles and review['verdict']=='pass' and greens:need(set(greens).issubset(approvals),'Passing assessment must independently assess current test oracles.')
        if owns_oracles and review['verdict']=='pass' and not greens:
            need(not subject['review_contract']['request'].get('verification'),'Declared verification cannot be waived by a report.')
            applicable=review.get('execution_inapplicable',{})
            need(applicable.get('reason') and 'package:'+package['package_hash'] in applicable.get('evidence_refs',[]),'Explicit independent execution applicability required.')
        from .review_policy import review_version
        if review_version(subject)==1 and review.get('verdict')=='pass' and review.get('perspective')=='test':
            from .test_challenges import validate_test_quality
            validate_test_quality(subject,package,{**review,'role':'session'})
        review={**deepcopy(review),'role':'session','review_id':digest(record['review']),'fresh':True}
        updated.setdefault('reviews',{}).setdefault('session',[]).append(review)
        for proof_id in approvals:
            updated.setdefault('verifier_proofs',{})[proof_id]={'passed':True,'fresh':True,'evidence_id':proof_id,
                'source_identity':subject['source_identity'],'semantic_status':'reviewed','session_id':subject['id'],
                'contract_hash':subject['review_contract_hash'],'review_id':review['review_id']}
        if review_version(subject) is not None:
            from .adversarial_reviews import ingest_report_findings
            updated=ingest_report_findings(updated,review)
        for finding in ([] if review_version(subject) is not None else review.get('findings',[])):
            need(finding.get('id') and finding.get('severity') in {'critical','important','minor','info'},'Structured finding identity and severity required.')
            existing=next((f for f in updated.get('unresolved_findings',[]) if f['id']==finding['id']),None)
            normalized={**finding,'status':finding.get('status','open')}
            need(existing is not None or normalized['status']=='open','New report findings start open; resolution/waiver needs its own authorized transition.')
            need(existing is None or {**existing,'status':existing.get('status','open')}==normalized,'Finding identity cannot silently replace another obligation.')
            if existing is None:updated.setdefault('unresolved_findings',[]).append(deepcopy(normalized))
    elif action=='authorize-session-repair':
        authorization=record.get('authorization',{})
        need(record.get('contract_hash')==subject['review_contract_hash'] and authorization.get('approved') is True
             and authorization.get('actor_id') and authorization.get('reason') and record.get('implementer_actor')
             and authorization.get('provenance',{}).get('kind')=='user-message' and authorization['provenance'].get('ref'), 'Explicit exact-scope user repair authorization required.')
        need(not subject.get('repair_authorization'),'Repair authorization cannot be silently replaced.')
        updated['repair_authorization']=deepcopy(record);updated.setdefault('actors',{})['implementer']=record['implementer_actor']
        need(all(r['actor_id']!=record['implementer_actor'] for rows in subject.get('reviews',{}).values() for r in rows),'Repair actor must be distinct from reviewers.')
    elif action=='session-complete':
        from .review_policy import review_version
        if review_version(subject) is not None:
            from .adversarial_reviews import review_coverage
            need(review_coverage(subject,'session')['complete'],'Current independent specialist coverage required before session completion.')
        require_action(subject_decision(subject,'completion',{}))
        need(not any(e['status'] in {'launching','uncertain'} for e in subject.get('executions',{}).values()),'Stop/reconcile active execution first.')
        current=[r for r in subject.get('reviews',{}).get('session',[]) if r.get('fresh') is not False and package_current(subject,subject.get('review_packages',{}).get(r['package_hash']))]
        need(current,'Current independent assessment required.')
        required=set(subject['review_contract']['request'].get('required_perspectives',[]))
        need(required.issubset({r.get('perspective') for r in current}),'Every required independent perspective must report.')
        need(independent_coverage(required,current),'Required perspectives need a distinct actual actor assignment.')
        if subject.get('repair_authorization'):
            need(all(r['verdict']=='pass' for r in current),'Authorized repair needs current passing reviews.')
            need(not any(f.get('status') not in {'resolved','waived','duplicate'} for f in subject.get('unresolved_findings',[])),'Repair findings remain unresolved.')
            if subject['review_contract']['request'].get('verification'):
                need(any(p.get('source_identity')==subject['source_identity'] and p.get('semantic_status')=='reviewed' and p.get('fresh') is not False for p in subject.get('verifier_proofs',{}).values()),'Current independently accepted repair proof required.')
        updated['status']='complete';updated['completion']={'outcome':'verified-repair' if subject.get('repair_authorization') else 'assessed',
            'verified_repair':bool(subject.get('repair_authorization')),'source_identity':subject['source_identity'],
            'contract_hash':subject['review_contract_hash'],'review_ids':[r['review_id'] for r in current],
            'finding_states':{f['id']:f.get('status','open') for f in subject.get('unresolved_findings',[])}}
    else:raise WorkflowError('INVALID_SESSION_EVENT','Unsupported session evidence event.')
    return updated


def _retry(path, operation_id, kind, client):
    from .review_sessions import lookup_operation, read_session
    receipt=lookup_operation(path,operation_id)
    if not receipt:return None
    need(receipt.get('client_request_hash')==digest({'kind':kind,'client':client}), 'Operation belongs to another request.')
    subject=read_session(path)['subject']
    if kind=='package':return subject['review_packages'][receipt['artifact_id']]
    if kind=='review':return next(r for r in subject['reviews']['session'] if r['review_id']==receipt['artifact_id'])
    if kind=='complete':return subject['completion']
    return {**receipt,'replayed':True}


def _read(path):
    from .review_sessions import read_session
    state=read_session(path);need(state['subject'].get('status','active')=='active','Completed sessions are immutable; start a new session.')
    return state


def _commit(path,state,op,action,record,*,client=None,kind=None):
    from .review_sessions import transact_session
    if kind is not None:record={**record,'_client_request_hash':digest({'kind':kind,'client':client})}
    return transact_session(path,state['version'],op,{'action':action,'record':record})


def _live(subject, *, diagnostic=False):
    from .standalone_reviews import assert_selection_current
    assert_selection_current(subject)
    from .enforcement_live import source_observation,assert_protection_current
    observation=source_observation(subject)
    need(observation['source_identity']==subject['source_identity'],'Observe/capture current source before acceptance.')
    if diagnostic:
        from .enforcement_live import protection_observations
        return protection_observations(subject)
    protection=assert_protection_current(subject)
    from .test_inputs import proof_inputs_current
    for proof in subject.get('verification_proofs',{}).values():
        if proof['phase']=='GREEN' and proof['source_identity']==subject['source_identity'] and proof.get('fresh') is not False:
            need(proof_inputs_current(subject,proof) and proof.get('protection_receipts')==protection,'Renew changed verification inputs/context.')
    return protection


def capture(path,phase,operation_id,timeout=300,*,expected_source_identity=None):
    marker=SESSION_EXECUTION.set({'path':str(Path(path).resolve()),'id':operation_id,'mode':'execution'})
    try:return _capture(path,phase,operation_id,timeout,expected_source_identity=expected_source_identity)
    finally:SESSION_EXECUTION.reset(marker)


def _capture(path,phase,operation_id,timeout=300,*,expected_source_identity=None):
    from .review_sessions import read_session
    from .enforcement_live import source_observation,assert_protection_current
    from .test_inputs import capture_input_bindings
    from .native_models import run_bounded
    from .storage_objects import put_object
    path=Path(path);state=read_session(path);subject=state['subject']
    verification=session_verification(subject)
    client_hash=digest({'phase':phase,'timeout':timeout,'contract_hash':subject['review_contract_hash'],**({'expected_source_identity':expected_source_identity} if expected_source_identity is not None else {})})
    prior=subject.get('executions',{}).get(operation_id)
    if prior:
        need(prior.get('client_request_hash')==client_hash,'Operation belongs to another execution request.')
        if prior.get('status')=='failed':return {'passed':False,'failure':'EXECUTION_FAILED','replayed':True}
        if prior.get('proof_id'):return {**subject['verification_proofs'][prior['proof_id']],'replayed':True}
        raise WorkflowError('EXECUTION_UNCERTAIN','Execution already reserved; inspect/reconcile rather than rerun.')
    need(subject.get('status','active')=='active' and phase in {'RED','GREEN'} and type(timeout) in (int,float) and 0<timeout<=3600,'Active session, phase and bounded timeout required.')
    need(verification.get('authority_refs') and verification.get('input_paths') and verification.get('target_ids') and verification.get('argv'),'Declare verification inputs, targets, tool and authority in the review contract.')
    need(all(isinstance(verification.get(k),list) and verification[k] and all(isinstance(v,str) and v for v in verification[k]) for k in ('input_paths','target_ids','argv','authority_refs')),'Verification lists must contain explicit nonempty strings.')
    repo=Path(subject['repositories'][verification['repo_id']]['location']);inputs=capture_input_bindings(repo,verification['input_paths'])
    from .test_extensions import current_extension,session_item
    extension=current_extension(subject,session_item(subject))
    need(not extension or all(inputs.get(name)==value for name,value in extension['input_bindings'].items()),'Supplemental regression inputs changed.')
    protection=assert_protection_current(subject);observation=source_observation(subject)
    need(expected_source_identity is None or observation['source_identity']==expected_source_identity,'Source changed before the bound verification action.')
    contract={'schema_version':2,'targets':sorted(set(verification['target_ids'])),'input_hashes':{k:v['sha256'] for k,v in inputs.items()},
        'input_bindings':inputs,'tool':verification['argv'],'report_format':verification.get('report_format','json'),
        'oracle_authority':verification['authority_refs'],'session_contract_hash':subject['review_contract_hash'],
        'clarification_binding':clarification_binding(subject,{}),'protection_context_hash':digest(protection)}
    if extension:contract['test_extension_hash']=extension['extension_hash']
    _commit(path,state,operation_id+':reserve','execution-claim',{'id':operation_id,'owner_pid':os.getpid(),'client_request_hash':client_hash,
        'contract_hash':subject['review_contract_hash'],'clarification_binding':clarification_binding(subject,{}),'source_observation':observation,'verification_contract':contract,'protection_receipts':protection})
    state=read_session(path);ended=False;proof=None
    try:
        # Observe files, then take the final decision snapshot immediately before spawn.
        need(source_observation(subject)==observation and capture_input_bindings(repo,verification['input_paths'])==inputs
             and assert_protection_current(subject)==protection,'Launch inputs changed after reservation.')
        latest=read_session(path)['subject']
        require_action(subject_decision(latest,'proof',{}))
        need(latest['review_contract_hash']==subject['review_contract_hash']
             and clarification_binding(latest,{})==contract['clarification_binding']
             and latest.get('executions',{}).get(operation_id,{}).get('status')=='launching','Launch contract or decisions changed.')
        from .review_orchestration import remaining_seconds
        remaining=remaining_seconds(latest,int(time.time()*1000))
        if remaining is not None:timeout=min(timeout,remaining)
        result=run_bounded(verification['argv'],repo,timeout);ended=True
        logs=path.with_name(path.name+'.artifacts')
        need(not any(logs.resolve().is_relative_to(Path(r['location']).resolve()) for r in subject['repositories'].values()),'Evidence artifacts must remain outside reviewed scope.')
        stdout=put_object(logs,'execution-log',result.stdout.encode());stderr=put_object(logs,'execution-log',result.stderr.encode())
        need(source_observation(subject)==observation and capture_input_bindings(repo,verification['input_paths'])==inputs
             and assert_protection_current(subject)==protection,'Source, test inputs or protected context changed during verification.')
        integrity={**parse_test_evidence(result.stdout,result.stderr,contract['report_format']),'phase':phase,'contract':contract,
            'source_identity':observation['source_identity'],'passed':True,'exit_code':result.returncode,
            'stdout_ref':stdout,'stderr_ref':stderr,'semantic_status':'pending-review'}
        proof={'id':uuid.uuid4().hex,'session_id':subject['id'],'contract_hash':subject['review_contract_hash'],'phase':phase,
            'execution_id':operation_id,'source_identity':observation['source_identity'],'source_observation':observation,
            'repo_id':verification['repo_id'],'integrity':integrity,'protection_receipts':protection,'passed':True,'fresh':True}
        if phase=='GREEN':
            reds=[p for p in subject.get('verification_proofs',{}).values() if p['phase']=='RED' and p['integrity']['contract']==contract]
            need(reds,'Matching actual RED required.')
            proof['red_proof_id']=reds[-1]['id'];integrity['baseline_source']=reds[-1]['source_identity']
        _commit(path,state,operation_id+':proof','session-proof',{'proof':proof})
        return proof
    except BaseException:
        current=read_session(path)
        if current['subject'].get('executions',{}).get(operation_id,{}).get('status')=='launching':
            _commit(path,current,operation_id+':failed','execution-finish',{'id':operation_id,'status':'failed' if ended else 'uncertain',
                **({'result':{**proof,'passed':False,'valid_proof':False,'integrity':{**proof['integrity'],'passed':False}}} if ended and proof else {})})
        raise


def prepare(path,operation_id):
    prior=_retry(path,operation_id,'package',{})
    if prior:return prior
    state=_read(path);subject=state['subject'];protection=_live(subject,diagnostic=True)
    package={'schema_version':1,'role':'session','session_id':subject['id'],'source_identity':subject['source_identity'],
        'context':context(subject),'protection_observations':protection}
    from .review_policy import review_version
    if review_version(subject) is not None:
        from .adversarial_reviews import adversarial_bindings
        from .adversarial_reviews import assessment
        package['review_contract']=deepcopy(subject['review_contract'])
        package['review_contract_hash']=subject['review_contract_hash']
        package['adversarial_bindings']=adversarial_bindings(subject,{'role':'session'})
        package['review_inputs']=subject['review_contract']['request'].get('review_inputs',[])
        package['review_requirements']=assessment(subject,{'role':'session'})
        from .adversarial_reviews import report_contract
        package['report_contract']=report_contract()
        from .adversarial_reviews import review_material
        package.update(review_material(subject,{'role':'session'}))
        package['risk_record']=subject.get('risk_assessments',{}).get(digest({'role':'session'}))
        if subject.get('standalone_scope'):
            package.update(standalone_scope=deepcopy(subject['standalone_scope']),repositories=deepcopy(subject['repositories']),
                governing_evidence=deepcopy(subject.get('governing_evidence',{})),limitations=deepcopy(subject.get('limitations',[])))
    package['package_hash']=digest(package)
    _commit(path,state,operation_id,'session-package',{'package':package},client={},kind='package');return package


def record_review(path,report,operation_id):
    prior=_retry(path,operation_id,'review',report)
    if prior:return prior
    state=_read(path);observations=_live(state['subject'],diagnostic=True)
    package=state['subject'].get('review_packages',{}).get(report.get('package_hash'),{})
    need(package.get('protection_observations')==observations,'Protection observation changed since review preparation.')
    from .storage_objects import read_object
    for oracle in report.get('test_oracles',[]):
        for key in ('red_proof_id','green_proof_id'):
            proof=state['subject']['verification_proofs'][oracle[key]];integrity=proof['integrity']
            if key=='green_proof_id':
                from .test_inputs import proof_inputs_current
                need(proof_inputs_current(state['subject'],proof),'Current declared verification inputs required.')
            logs=Path(path).with_name(Path(path).name+'.artifacts')
            parsed=parse_test_evidence(read_object(logs,integrity['stdout_ref'],max_bytes=8*1024*1024).decode(),
                read_object(logs,integrity['stderr_ref'],max_bytes=8*1024*1024).decode(),integrity['contract']['report_format'])
            need(parsed['outcomes']==integrity['outcomes'] and parsed['classification']==integrity['classification'],'Retained raw report differs from proof.')
    _commit(path,state,operation_id,'session-review',{'review':report},client=report,kind='review')
    from .review_sessions import read_session
    return next(r for r in read_session(path)['subject']['reviews']['session'] if r['review_id']==digest(report))


def complete(path,operation_id):
    prior=_retry(path,operation_id,'complete',{})
    if prior:return prior
    state=_read(path);_live(state['subject'],diagnostic=not bool(state['subject'].get('repair_authorization')))
    _commit(path,state,operation_id,'session-complete',{},client={},kind='complete')
    from .review_sessions import read_session
    return read_session(path)['subject']['completion']


def independent_coverage(required,reviews):
    candidates={p:{r['actor_id'] for r in reviews if r.get('perspective')==p} for p in required}
    assigned={}
    def assign(p,seen):
        for actor in sorted(candidates[p]):
            if actor in seen:continue
            seen.add(actor)
            if actor not in assigned or assign(assigned[actor],seen):
                assigned[actor]=p
                return True
        return False
    return all(assign(p,set()) for p in sorted(required))


def guard_execution_event(path,subject,action,record):
    if action not in {'execution-claim','execution-finish','session-proof','execution-reconcile'}:return
    identifier=record.get('proof',{}).get('execution_id') if action=='session-proof' else record.get('id')
    active=SESSION_EXECUTION.get()
    need(active and active.get('path')==str(Path(path).resolve()) and active.get('id')==identifier,
         'Execution events belong to the live capture/recovery adapter; generic session events cannot manufacture them.')
    if action=='execution-reconcile':
        from .process_liveness import process_alive
        claimed=subject.get('executions',{}).get(identifier,{})
        need(active.get('mode')=='recovery' and process_alive(claimed.get('owner_pid')) is False,
             'Actual absent coordinator and recovery observation required.')
    else:
        owner=record if action=='execution-claim' else subject.get('executions',{}).get(identifier,{})
        need(active.get('mode')=='execution' and owner.get('owner_pid')==os.getpid(),'Only the actual execution coordinator may record proof/finish.')
