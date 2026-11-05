"""Standalone enforcement primitives. No workflow plan, run or model orchestration."""
from copy import deepcopy
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
    return (isinstance(package,dict) and package.get('session_id')==subject['id']
        and package.get('context')==context(subject)
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
             and contract.get('clarification_binding')==clarification_binding(subject,{}),'Current session execution and user decisions required.')
        observation=proof.get('source_observation',{})
        need(observation.get('source_identity')==digest(observation.get('snapshots',{}))==proof.get('source_identity'),'Bound executed source required.')
        verification=subject['review_contract']['request'].get('verification',{})
        need(contract.get('tool')==verification.get('argv') and contract.get('targets')==sorted(set(verification.get('target_ids',[])))
             and set(contract.get('input_hashes',{}))==set(verification.get('input_paths',[]))
             and contract.get('oracle_authority')==verification.get('authority_refs')
             and contract.get('session_contract_hash')==subject['review_contract_hash'],'Declared standalone verification contract required.')
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
        validate_receipts(subject,package.get('protection_receipts'))
        updated.setdefault('review_packages',{})[package['package_hash']]=deepcopy(package)
    elif action=='session-review':
        review=record['review'];package=subject.get('review_packages',{}).get(review.get('package_hash'))
        need(package_current(subject,package) and review.get('actor_id') and review.get('invocation_ref')
             and review['actor_id']!=subject.get('actors',{}).get('implementer')
             and review.get('verdict') in {'pass','request-changes','block'},'Current independent session assessment required.')
        need(not any(r.get('invocation_ref')==review['invocation_ref'] for rows in subject.get('reviews',{}).values() for r in rows),'Each assessment requires a fresh actual invocation.')
        approvals=[]
        for oracle in review.get('test_oracles',[]):
            green=subject.get('verification_proofs',{}).get(oracle.get('green_proof_id'),{})
            red=subject.get('verification_proofs',{}).get(oracle.get('red_proof_id'),{})
            need(green.get('source_identity')==subject['source_identity'] and green.get('red_proof_id')==red.get('id'), 'Current actual linked pair required.')
            contract=green['integrity']['contract'];validate_test_pair(red['integrity'],green['integrity'],contract,require_review=False)
            need(oracle.get('input_hashes')==contract['input_hashes'] and oracle.get('authority_refs')==contract['oracle_authority']
                 and oracle.get('failure_relevance'),'Independent actual oracle/failure relevance required.')
            approvals.append(green['id'])
        greens=[p['id'] for p in subject.get('verification_proofs',{}).values() if p['phase']=='GREEN' and p['source_identity']==subject['source_identity'] and p.get('fresh') is not False]
        if review['verdict']=='pass' and greens:need(set(greens).issubset(approvals),'Passing assessment must independently assess current test oracles.')
        if review['verdict']=='pass' and not greens:
            need(not subject['review_contract']['request'].get('verification'),'Declared verification cannot be waived by a report.')
            applicable=review.get('execution_inapplicable',{})
            need(applicable.get('reason') and 'package:'+package['package_hash'] in applicable.get('evidence_refs',[]),'Explicit independent execution applicability required.')
        review={**deepcopy(review),'role':'session','review_id':digest(review),'fresh':True}
        updated.setdefault('reviews',{}).setdefault('session',[]).append(review)
        for proof_id in approvals:
            updated.setdefault('verifier_proofs',{})[proof_id]={'passed':True,'fresh':True,'evidence_id':proof_id,
                'source_identity':subject['source_identity'],'semantic_status':'reviewed','session_id':subject['id'],
                'contract_hash':subject['review_contract_hash'],'review_id':review['review_id']}
        for finding in review.get('findings',[]):
            need(finding.get('id') and finding.get('severity') in {'critical','important','minor','info'},'Structured finding identity and severity required.')
            existing=next((f for f in updated.get('unresolved_findings',[]) if f['id']==finding['id']),None)
            need(not existing or existing==finding,'Finding identity cannot silently replace another obligation.')
            if not existing:updated.setdefault('unresolved_findings',[]).append(deepcopy(finding))
    elif action=='authorize-session-repair':
        authorization=record.get('authorization',{})
        need(record.get('contract_hash')==subject['review_contract_hash'] and authorization.get('approved') is True
             and authorization.get('actor_id') and authorization.get('reason') and record.get('implementer_actor')
             and authorization.get('provenance',{}).get('kind')=='user-message' and authorization['provenance'].get('ref'), 'Explicit exact-scope user repair authorization required.')
        need(not subject.get('repair_authorization'),'Repair authorization cannot be silently replaced.')
        updated['repair_authorization']=deepcopy(record);updated.setdefault('actors',{})['implementer']=record['implementer_actor']
        need(all(r['actor_id']!=record['implementer_actor'] for rows in subject.get('reviews',{}).values() for r in rows),'Repair actor must be distinct from reviewers.')
    elif action=='session-complete':
        require_action(subject_decision(subject,'completion',{}))
        need(not any(e['status'] in {'launching','uncertain'} for e in subject.get('executions',{}).values()),'Stop/reconcile active execution first.')
        current=[r for r in subject.get('reviews',{}).get('session',[]) if r.get('fresh') is not False and package_current(subject,subject.get('review_packages',{}).get(r['package_hash']))]
        need(current,'Current independent assessment required.')
        required=set(subject['review_contract']['request'].get('required_perspectives',[]))
        need(required.issubset({r.get('perspective') for r in current}),'Every required independent perspective must report.')
        actors=[r['actor_id'] for r in current if r.get('perspective') in required]
        need(len(set(actors))>=len(required),'Required perspectives need distinct actual actors.')
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
    return receipt


def _read(path):
    from .review_sessions import read_session
    state=read_session(path);need(state['subject'].get('status','active')=='active','Completed sessions are immutable; start a new session.')
    return state


def _commit(path,state,op,action,record,*,client=None,kind=None):
    from .review_sessions import transact_session
    if kind is not None:record={**record,'_client_request_hash':digest({'kind':kind,'client':client})}
    return transact_session(path,state['version'],op,{'action':action,'record':record})


def _live(subject):
    from .enforcement_live import source_observation,assert_protection_current
    observation=source_observation(subject)
    need(observation['source_identity']==subject['source_identity'],'Observe/capture current source before acceptance.')
    protection=assert_protection_current(subject)
    from .test_inputs import proof_inputs_current
    for proof in subject.get('verification_proofs',{}).values():
        if proof['phase']=='GREEN' and proof['source_identity']==subject['source_identity'] and proof.get('fresh') is not False:
            need(proof_inputs_current(subject,proof) and proof.get('protection_receipts')==protection,'Renew changed verification inputs/context.')
    return protection


def capture(path,phase,operation_id,timeout=300):
    from .review_sessions import read_session
    from .enforcement_live import source_observation,assert_protection_current
    from .test_inputs import capture_input_bindings
    from .native_models import run_bounded
    from .storage_objects import put_object
    path=Path(path);state=read_session(path);subject=state['subject']
    verification=subject['review_contract']['request'].get('verification',{})
    client_hash=digest({'phase':phase,'timeout':timeout,'contract_hash':subject['review_contract_hash']})
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
    protection=assert_protection_current(subject);observation=source_observation(subject)
    contract={'schema_version':2,'targets':sorted(set(verification['target_ids'])),'input_hashes':{k:v['sha256'] for k,v in inputs.items()},
        'input_bindings':inputs,'tool':verification['argv'],'report_format':verification.get('report_format','json'),
        'oracle_authority':verification['authority_refs'],'session_contract_hash':subject['review_contract_hash'],
        'clarification_binding':clarification_binding(subject,{}),'protection_context_hash':digest(protection)}
    _commit(path,state,operation_id+':reserve','execution-claim',{'id':operation_id,'owner_pid':os.getpid(),'client_request_hash':client_hash,
        'contract_hash':subject['review_contract_hash'],'clarification_binding':clarification_binding(subject,{}),'source_observation':observation})
    state=read_session(path);ended=False
    try:
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
            _commit(path,current,operation_id+':failed','execution-finish',{'id':operation_id,'status':'failed' if ended else 'uncertain'})
        raise


def prepare(path,operation_id):
    prior=_retry(path,operation_id,'package',{})
    if prior:return prior
    state=_read(path);subject=state['subject'];protection=_live(subject)
    package={'schema_version':1,'role':'session','session_id':subject['id'],'source_identity':subject['source_identity'],
        'context':context(subject),'protection_receipts':protection}
    package['package_hash']=digest(package)
    _commit(path,state,operation_id,'session-package',{'package':package},client={},kind='package');return package


def record_review(path,report,operation_id):
    prior=_retry(path,operation_id,'review',report)
    if prior:return prior
    state=_read(path);_live(state['subject'])
    from .storage_objects import read_object
    for oracle in report.get('test_oracles',[]):
        for key in ('red_proof_id','green_proof_id'):
            proof=state['subject']['verification_proofs'][oracle[key]];integrity=proof['integrity']
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
    state=_read(path);_live(state['subject'])
    _commit(path,state,operation_id,'session-complete',{},client={},kind='complete')
    from .review_sessions import read_session
    return read_session(path)['subject']['completion']
