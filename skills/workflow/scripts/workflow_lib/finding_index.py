"""Original finding obligations survive grouping, disposition and identity changes."""
from copy import deepcopy
from .document_units import digest
from .finding_closure import finding_hash
from .review_policy import bounded
from .store import WorkflowError

SEVERITY={'info':0,'minor':1,'important':2,'critical':3}
DISPOSED={'resolved','waived','rejected','deferred'}


def need(ok,message):
    if not ok:raise WorkflowError('FINDING_INDEX_BLOCKED',message)


def semantic_finding(finding):
    fields=('item_id','path','failure_scenario','description','title','text','impact','requested_correction',
            'question','authority_refs','expected_behavior','severity','mandatory','required_perspective',
            'required_perspectives','execution_required','non_waivable','waivable')
    result={key:deepcopy(finding[key]) for key in fields if key in finding}
    obligations=finding.get('obligations') or [finding['id']]
    result['obligations']=['finding' if value==finding['id'] else value for value in obligations]
    return result


def _canonical_id(original_hash):return 'finding-'+original_hash[:24]


def _refresh(subject,index):
    raw={f['id']:f for f in subject.get('unresolved_findings',[])}
    for identifier,node in index['canonical'].items():
        if node.get('superseded_by'):continue
        members=[raw[fid] for fid in node['member_ids']]
        active=[f for f in members if f.get('status','open') not in DISPOSED]
        severity=max((f.get('severity') if isinstance(f.get('severity'),str) and f['severity'] in SEVERITY else 'critical' for f in active or members),key=SEVERITY.get)
        node.update(severity=severity,item_ids=sorted({f['item_id'] for f in members if f.get('item_id')}),
            required_perspectives=sorted({p for f in members for p in
                list(f.get('required_perspectives',[]))+([f['required_perspective']] if f.get('required_perspective') else [])}),
            obligation_hashes=sorted({h for fid in node['member_ids'] for h in index['members'][fid]['obligation_hashes']}),
            outcomes={fid:raw[fid].get('status','open') for fid in node['member_ids']},
            status='open' if active else 'resolved' if all(f.get('status')=='resolved' for f in members) else 'disposed')
    families={}
    for fid,member in index['members'].items():
        for obligation in member['obligation_hashes']:families.setdefault(obligation,[]).append(raw[fid])
    verified=set(index.get('verified_history',[]))
    for obligation,members in families.items():
        if all(f.get('status')=='resolved' and f.get('resolution',{}).get('proof_ids')
               and (f['resolution'].get('review_ids') or f['resolution'].get('review_id')) for f in members):verified.add(obligation)
    index['verified_history']=sorted(verified)
    return index


def index_findings(subject:dict,reports:list[dict])->dict:
    need(isinstance(reports,list),'Use explicit recorded report facts.')
    updated=deepcopy(subject);index=deepcopy(subject.get('finding_index',{
        'schema_version':1,'canonical':{},'aliases':{},'members':{},'original_records':{},'history':[],'verified_history':[]}))
    need(index.get('schema_version')==1,'Unsupported finding index contract.')
    findings=subject.get('unresolved_findings',[])
    need(isinstance(findings,list) and all(isinstance(f,dict) and isinstance(f.get('id'),str) and f['id'] for f in findings)
         and len({f['id'] for f in findings})==len(findings),'Original findings need unique explicit identities.')
    ids={f['id'] for f in findings}
    need(set(index['aliases']).issubset(ids),'Original indexed members cannot disappear; retain their dispositions.')
    for report in reports:
        need(isinstance(report,dict),'Report references must be objects.')
        need(all(f.get('id') in ids for f in report.get('findings',[])),'Index only admitted original obligations, never unvalidated report imports.')
    for finding in findings:
        fid=finding['id'];original_hash=finding_hash(finding);semantic=semantic_finding(finding)
        need(isinstance(finding.get('obligations',[]),list),'Constituent obligations must be an explicit array.')
        if fid in index['members']:
            member=index['members'][fid]
            need(member['semantic_hash']==digest(semantic),'A finding ID cannot silently change its original failure or obligations.')
            member['current_finding_hash']=original_hash
            index['aliases'][fid]['current_finding_hash']=original_hash
        else:
            obligations=semantic['obligations']
            need(all(isinstance(o,str) and o for o in obligations),'Keep every named obligation.')
            member={'id':fid,'original_finding_hash':original_hash,'current_finding_hash':original_hash,
                'semantic_hash':digest(semantic),'original':deepcopy(finding),
                'obligation_hashes':[digest({'failure':semantic,'obligation':o}) for o in obligations]}
            index['members'][fid]=member;canonical=_canonical_id(original_hash)
            index['canonical'][canonical]={'id':canonical,'member_ids':[fid],'equivalence_refs':[]}
            index['aliases'][fid]={'canonical_id':canonical,'original_finding_hash':original_hash,'current_finding_hash':original_hash}
        index['original_records'].setdefault(original_hash,deepcopy(finding))
    updated['finding_index']=_refresh(subject,index)
    return updated


def _recorded_review(subject,review_id,*,diagnostic_allowed=True):
    matches=[r for rows in subject.get('reviews',{}).values() for r in rows if r.get('review_id')==review_id]
    need(len(matches)==1,'Exactly one existing independent reviewer output is required.')
    review=matches[0];implementers=set(subject.get('implementer_actors',[]))|{subject.get('actors',{}).get('implementer')}
    need(review.get('actor_id') and review['actor_id'] not in implementers and review.get('invocation_ref')
         and review.get('fresh') is not False,'Current independent invocation required.')
    from .stored_records import require_package
    package=require_package(subject.get('review_packages',{}).get(review.get('package_hash')))
    from .review_enforcement import review_bindings_current
    if subject.get('review_contract_hash'):
        from .session_evidence import package_current
        current=package_current(subject,package)
    else:current=package and review_bindings_current(subject,package,live=False)
    need(current and package.get('source_identity')==subject.get('source_identity'),'Reviewer output must inspect the current original obligations.')
    from .review_policy import review_version
    if review_version(subject) is not None:
        from .review_dispatch import validate_review_model
        from .adversarial_reviews import semantic_report_hash
        validate_review_model(subject,package,review)
        receipt=subject.get('model_receipts',{}).get(review.get('model_invocation_id'),{})
        need(receipt.get('review_report_hash')==semantic_report_hash(review),'Grouping/disposition must come from sealed actual reviewer output.')
        need(diagnostic_allowed or (receipt.get('diagnostic') is False and review.get('diagnostic') is not True),'Diagnostic invocations cannot resolve or reject original obligations.')
    return review,package


def consolidate_findings(subject:dict,record:dict)->dict:
    bounded(record)
    need(set(record).issubset({'review_id','equivalence_id','member_ids','canonical_id'}),'Grouping cannot import counters, statuses or approvals.')
    updated=index_findings(subject,[]);review,package=_recorded_review(subject,record.get('review_id'))
    rows=[e for e in review.get('finding_equivalences',[]) if e.get('id')==record.get('equivalence_id')]
    need(len(rows)==1,'Explicit same-failure/correction evidence in an existing actual review is required.')
    equivalence=rows[0];ids=record.get('member_ids')
    need(isinstance(ids,list) and len(ids)>=2 and len(ids)==len(set(ids)) and set(ids)==set(equivalence.get('member_ids',[])), 'Exact distinct reviewed members required.')
    index=updated['finding_index'];raw={f['id']:f for f in updated['unresolved_findings']}
    need(set(ids).issubset(raw),'Unknown original finding.')
    groups={index['aliases'][fid]['canonical_id'] for fid in ids}
    all_ids=sorted({fid for group in groups for fid in index['canonical'][group]['member_ids']})
    from .clarifications import clarification_blockers
    for fid in all_ids:
        finding=raw[fid]
        need(not finding.get('unresolved_disagreements'),'Resolve actual reviewer disagreement before declaring equivalence.')
        blocked={q['id'] for q in clarification_blockers(subject,{'item_id':finding['item_id']} if finding.get('item_id') else {})}
        need(not blocked and (not finding.get('question') or 'finding:'+fid in subject.get('clarifications',{})), 'Missing business rules require actual clarification, not assumed equivalence.')
    failure=equivalence.get('same_failure',{})
    need(equivalence.get('source_identity')==subject.get('source_identity') and all(failure.get(k) for k in ('trigger','observed','expected'))
         and equivalence.get('same_correction') and equivalence.get('reason') and equivalence.get('evidence_refs'), 'Cite the same observed failure, correction and actual supporting evidence.')
    need(equivalence.get('finding_hashes')=={fid:finding_hash(raw[fid]) for fid in ids},'Equivalence must bind exact current member obligations.')
    if review.get('role')=='item':need(all(raw[fid].get('item_id')==review.get('item_id') for fid in all_ids),'Item review cannot consolidate unseen foreign-item obligations.')
    canonical=record.get('canonical_id') or sorted(groups)[0]
    need(canonical in groups,'Canonical destination must already belong to a reviewed member.')
    index['history'].append({'operation':'consolidate','canonical_ids':sorted(groups),'member_ids':all_ids,
        'review_id':review['review_id'],'equivalence_id':equivalence['id']})
    refs={ref for group in groups for ref in index['canonical'][group].get('equivalence_refs',[])}
    refs.add(review['review_id']+':'+equivalence['id'])
    index['canonical'][canonical]={'id':canonical,'member_ids':all_ids,'equivalence_refs':sorted(refs)}
    for group in groups-{canonical}:index['canonical'][group]['superseded_by']=canonical
    for fid in all_ids:index['aliases'][fid]['canonical_id']=canonical
    updated['finding_index']=_refresh(updated,index)
    return updated


def finding_progress(subject:dict)->dict:
    indexed=index_findings(subject,[])['finding_index'];outcomes={}
    for f in subject.get('unresolved_findings',[]):outcomes.setdefault(f.get('status','open'),[]).append(f['id'])
    verified=indexed['verified_history']
    active={k:v for k,v in indexed['canonical'].items() if not v.get('superseded_by')}
    return {'verified_progress_hash':digest(verified),'verified_obligation_hashes':list(verified),
        'verified_obligation_count':len(verified),'outcomes':outcomes,
        'canonical_open_ids':sorted(k for k,v in active.items() if v['status']=='open'),
        'duplicate_alias_count':sum(max(0,len(v['member_ids'])-1) for v in active.values())}


def validate_canonical_closure(subject,record):
    bounded(record)
    need(set(record).issubset({'canonical_id','member_closures'}),'Canonical closure cannot import spending or disposition state.')
    indexed=index_findings(subject,[]);node=indexed['finding_index']['canonical'].get(record.get('canonical_id'),{})
    need(node and not node.get('superseded_by'),'Use the current canonical group.')
    members=record.get('member_closures')
    need(isinstance(members,list) and len(members)==len(node['member_ids']) and
         all(isinstance(m,dict) for m in members) and {m.get('finding_id') for m in members}==set(node['member_ids']),
         'Every original member needs its own current closure, including item/proof and perspective obligations.')
    from .finding_closure import validate_closure
    results={m['finding_id']:validate_closure(subject,m) for m in members}
    return {'status':'resolved','canonical_id':node['id'],'members':results,
        'review_ids':sorted({rid for result in results.values() for rid in result['review_ids']})}


def split_findings(subject,record):
    bounded(record)
    need(set(record).issubset({'review_id','partition_id','canonical_id'}),'Splitting cannot replace budgets or original states.')
    updated=index_findings(subject,[]);index=updated['finding_index']
    old=index['canonical'].get(record.get('canonical_id'),{})
    need(old and not old.get('superseded_by'),'Split an active canonical group.')
    review,_=_recorded_review(subject,record.get('review_id'))
    rows=[r for r in review.get('finding_partitions',[]) if r.get('id')==record.get('partition_id')]
    need(len(rows)==1,'An actual independent report must explain this partition.')
    partition=rows[0];groups=partition.get('groups')
    need(isinstance(groups,list) and len(groups)>1 and all(isinstance(g,list) and g for g in groups),'Use explicit nonempty groups.')
    flat=[fid for group in groups for fid in group]
    need(all(isinstance(fid,str) for fid in flat) and len(flat)==len(set(flat)) and set(flat)==set(old['member_ids']), 'Every original member must survive exactly once.')
    raw={f['id']:f for f in subject['unresolved_findings']}
    need(partition.get('canonical_id')==old['id'] and partition.get('source_identity')==subject.get('source_identity')
         and partition.get('finding_hashes')=={fid:finding_hash(raw[fid]) for fid in flat}
         and partition.get('reason') and partition.get('evidence_refs'),'Partition needs current member contracts and independent evidence.')
    index['history'].append({'operation':'split','before':deepcopy(old),'review_id':review['review_id'],'partition_id':partition['id']})
    destinations=[]
    for group in groups:
        canonical=_canonical_id(index['members'][sorted(group)[0]]['original_finding_hash']);destinations.append(canonical)
        index['canonical'][canonical]={'id':canonical,'member_ids':sorted(group),'equivalence_refs':[],
            'partition_ref':review['review_id']+':'+partition['id']}
        for fid in group:index['aliases'][fid]['canonical_id']=canonical
    if old['id'] not in destinations:index['canonical'][old['id']]['superseded_by']=destinations[0]
    updated['finding_index']=_refresh(updated,index)
    return updated


def record_disposition(subject,record):
    bounded(record)
    need(set(record).issubset({'review_id','disposition_id','finding_id'}),'Disposition cannot import approval, source edits or counters.')
    updated=index_findings(subject,[]);review,_=_recorded_review(subject,record.get('review_id'),diagnostic_allowed=False)
    finding=next((f for f in updated['unresolved_findings'] if f['id']==record.get('finding_id')),None)
    need(finding,'Known original finding required.')
    from .action_policy import require_action,subject_decision
    require_action(subject_decision(subject,'finding',{'item_id':finding['item_id']} if finding.get('item_id') else {}))
    rows=[r for r in review.get('finding_dispositions',[]) if r.get('id')==record.get('disposition_id') and r.get('finding_id')==finding['id']]
    need(len(rows)==1,'Use the exact independently recorded disposition.')
    disposition=rows[0];kind=disposition.get('disposition')
    need(kind in {'rejected','deferred'},'Resolved needs proof-backed closure; waived needs actual user authorization; duplicates retain member obligations.')
    need(disposition.get('finding_hash')==finding_hash(finding) and disposition.get('source_identity')==subject.get('source_identity')
         and disposition.get('reason') and disposition.get('evidence_refs'),'Disposition must bind current original obligations and actual evidence.')
    if review.get('role')=='item':need(finding.get('item_id')==review.get('item_id'),'Item review cannot dispose of a foreign item.')
    if kind=='deferred':need(finding.get('severity') in {'minor','info'} and finding.get('mandatory') is not True,'Only nonmandatory minor/info findings may be deferred without user waiver.')
    if kind=='rejected':
        from .implementation_contracts import authority_refs
        allowed=authority_refs(subject,{'item_id':finding['item_id']} if finding.get('item_id') else {})
        refs=disposition.get('authority_refs')
        need(isinstance(refs,list) and refs and set(refs).issubset(allowed),'Reject against actual approved rules/decisions, not invented business intent.')
    finding.setdefault('disposition_history',[]).append({'status':finding.get('status','open'),'disposition':deepcopy(finding.get('disposition_record'))})
    finding.update(status=kind,disposition_record={**deepcopy(disposition),'review_id':review['review_id']})
    return index_findings(updated,[])


def guard_live_finding(subject,action,record):
    """Producer-only observations; pure replay uses the reducers above."""
    from .review_policy import review_version
    if review_version(subject) is None or action not in {'close-finding','close-canonical','consolidate-findings','split-findings','finding-disposition'}:return
    from .enforcement_live import assert_source_current,assert_protection_current
    assert_source_current(subject);receipts=assert_protection_current(subject)
    if action=='close-canonical':
        closure=validate_canonical_closure(subject,record);members=list(closure['members'])
    elif action=='close-finding':
        from .finding_closure import validate_closure
        closure=validate_closure(subject,record);members=[record['finding_id']]
    else:closure={'review_ids':[record['review_id']]};members=[]
    for fid in members:
        for pid in subject.get('corrections',{}).get(fid,{}).get('proof_ids',[]):
            verifier=subject.get('verifier_proofs',{}).get(pid,{})
            evidence=subject.get('verification_proofs',{}).get(verifier.get('evidence_id'),{})
            need(evidence.get('kind')!='code' or evidence.get('protection_receipts')==receipts,
                'Renew code proof after a protected verification-context change.')
    from .host_completion import package_current as workflow_current
    from .session_evidence import package_current as session_current
    current=session_current if subject.get('review_contract_hash') else workflow_current
    for rid in closure['review_ids']:
        review,_=_recorded_review(subject,rid,diagnostic_allowed=action in {'consolidate-findings','split-findings'})
        need(current(subject,subject['review_packages'][review['package_hash']]),'Renew actual current review inputs before changing finding lineage or disposition.')
