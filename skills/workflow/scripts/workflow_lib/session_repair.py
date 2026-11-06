"""Reviewable exact editable-source handoff; never writes reviewed user files."""
from copy import deepcopy
from pathlib import Path
from contextvars import ContextVar
from .document_units import digest
from .store import WorkflowError
from .review_sessions import read_session

SCOPE_PRODUCER=ContextVar('devflow_session_scope_producer',default=None)


def need(ok,message):
    if not ok:raise WorkflowError('SESSION_REPAIR_BLOCKED',message)


def _proposal_hash(value):return digest({k:v for k,v in value.items() if k not in {'proposal_hash','authorization','_client_request_hash'}})


def prepare_repair(path,request):
    from .standalone_reviews import select_source
    from .protected_changes import snapshot_protected
    subject=read_session(path)['subject'];scope=subject.get('standalone_scope',{})
    need(scope and not subject.get('editable_source') and not subject.get('repair_authorization'),'A report-only selected-scope session is required; existing repair authority cannot be reset.')
    need(set(request)=={'implementer_actor','protection_paths'} and isinstance(request.get('implementer_actor'),str) and request['implementer_actor'],
         'Choose the actual writer and protected governing/test input paths.')
    original=Path(scope['repository']);selection,_=select_source(original,{'mode':'working-tree'})
    protections=request['protection_paths'];verification=subject['review_contract']['request'].get('verification',{})
    required=set(subject.get('governing_evidence',{}))|set(verification.get('input_paths',[]))
    need(isinstance(protections,list) and all(isinstance(p,str) and p in selection['files'] for p in protections)
         and required.issubset(protections),'Retain every selected governing document and original declared verification input.')
    from .standalone_reviews import _files_observation
    observation=_files_observation(selection)
    contract={'scope':{'repositories':[str(original)],'source_identity':observation['source_identity']},
        'request':deepcopy(subject['review_contract']['request'])}
    inventory={'paths':sorted(set(protections)),'governing_digest':digest(contract['scope'])}
    proposal={'schema_version':1,'session_id':subject['id'],'previous_contract_hash':subject['review_contract_hash'],
        'selection':selection,'observation':observation,'review_contract':contract,'review_contract_hash':digest(contract),
        'implementer_actor':request['implementer_actor'],'inventory':inventory,'baseline':snapshot_protected(original,inventory)}
    proposal['proposal_hash']=_proposal_hash(proposal)
    return proposal


def guard(path,subject,action,record):
    if action!='session-editable-scope':return
    need(SCOPE_PRODUCER.get()==str(Path(path).resolve()),'Only the actual observed-scope producer can authorize an editable handoff.')


def reduce_repair(subject,record):
    from .session_evidence import reduce_session
    need(record.get('schema_version')==1 and record.get('session_id')==subject['id'] and
         record.get('previous_contract_hash')==subject.get('review_contract_hash') and not subject.get('repair_authorization'),
         'Bind the original active review-only contract without replacing repair authority.')
    need(record.get('proposal_hash')==_proposal_hash(record),'Exact scope proposal required.')
    authorization=record.get('authorization',{})
    need(authorization.get('approved') is True and authorization.get('proposal_hash')==record['proposal_hash'] and
         authorization.get('actor_id') and authorization.get('reason') and authorization.get('provenance',{}).get('kind')=='user-message'
         and authorization['provenance'].get('ref'),'Actual user approval must bind the complete editable scope/protection proposal.')
    need(subject.get('status')=='active' and not any(r.get('status') not in {'completed','failed','reconciled'} for r in
        list(subject.get('effects',{}).values())+list(subject.get('executions',{}).values())), 'Reconcile all effects before changing scope.')
    selection=record['selection'];contract=record['review_contract'];observation=record['observation']
    need(selection.get('mode')=='working-tree' and selection.get('repository')==subject['standalone_scope']['repository']
         and selection.get('selection_hash')==digest({k:v for k,v in selection.items() if k!='selection_hash'})
         and observation.get('source_identity')==digest(observation.get('snapshots',{})), 'Actual selected working-tree identities required.')
    need(contract=={'scope':{'repositories':[selection['repository']],'source_identity':observation['source_identity']},'request':subject['review_contract']['request']}
         and record['review_contract_hash']==digest(contract),'Scope renewal preserves actual user intent; business amendments use their own gate.')
    required=set(subject.get('governing_evidence',{}))|set(contract['request'].get('verification',{}).get('input_paths',[]))
    need(required.issubset(record['inventory']['paths']) and record['baseline'].get('inventory')==record['inventory']
         and record['inventory']['governing_digest']==digest(contract['scope']), 'Keep actual governing/test protections in the approved proposal.')
    updated=deepcopy(subject)
    updated.setdefault('standalone_scope_history',[]).append({'selection':deepcopy(subject['standalone_scope']),
        'repositories':deepcopy(subject['repositories']),'contract':deepcopy(subject['review_contract']),
        'proposal_hash':record['proposal_hash'],'authorization':deepcopy(authorization)})
    updated.update(review_contract=deepcopy(contract),review_contract_hash=record['review_contract_hash'],
        governing_digest=digest(contract['scope']),standalone_scope=deepcopy(selection),editable_source=True,
        repositories={'repo-1':{'location':selection['repository']}},source_identity=observation['source_identity'],source_observation=deepcopy(observation),
        protected_inventories={'repo-1':{'inventory':deepcopy(record['inventory']),'baseline':deepcopy(record['baseline'])}})
    for collection in ('verification_proofs','verifier_proofs','hardening_proofs'):
        for row in updated.get(collection,{}).values():row.update(fresh=False,passed=False)
    for rows in updated.get('reviews',{}).values():
        for row in rows:row['fresh']=False
    return reduce_session(updated,'authorize-session-repair',{'contract_hash':record['review_contract_hash'],
        'implementer_actor':record['implementer_actor'],'authorization':authorization})


def authorize_repair(path,proposal,operation_id):
    from .session_evidence import _retry,_commit
    prior=_retry(path,operation_id,'editable-scope',proposal)
    if prior:return prior
    fresh=prepare_repair(path,{'implementer_actor':proposal.get('implementer_actor'),'protection_paths':proposal.get('inventory',{}).get('paths')})
    need({k:v for k,v in proposal.items() if k!='authorization'}==fresh,'Selected source/protections changed; prepare a fresh reviewable proposal.')
    state=read_session(path);token=SCOPE_PRODUCER.set(str(Path(path).resolve()))
    try:return _commit(path,state,operation_id,'session-editable-scope',proposal,client=proposal,kind='editable-scope')
    finally:SCOPE_PRODUCER.reset(token)
