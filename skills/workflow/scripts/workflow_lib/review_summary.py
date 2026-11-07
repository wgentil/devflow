"""Selected-scope metadata measurements and conservative original-receipt reuse."""
from copy import deepcopy
import math
from .store import WorkflowError


def need(ok,message):
    if not ok:raise WorkflowError('REVIEW_SUMMARY_BLOCKED',message)


def number(value):return type(value) in (int,float) and math.isfinite(value) and value>=0


def review_reuse(subject:dict,package:dict,receipt:dict)->dict:
    """No dispatch and no cross-package inheritance; live callers still check source."""
    try:
        from .review_policy import require_review_policy
        from .finding_index import _recorded_review
        from .adversarial_reviews import adversarial_bindings
        from .stored_records import require_package
        require_review_policy(subject)
        original,bound=_recorded_review(subject,receipt.get('review_id'),diagnostic_allowed=False)
        need(original==receipt and require_package(package)==bound,'Only the exact original recorded assessment/package can be reused.')
        scope={'role':bound.get('role'),**({'item_id':bound['item_id']} if bound.get('item_id') else {})}
        need(bound.get('adversarial_bindings')==adversarial_bindings(subject,scope),'Source, dependencies, contract, policy, risk, questions or proof bindings changed.')
        need(bound.get('role')!='pr','PR acceptance needs its separate fresh exact-head/status checks.')
        return {'reusable':True,'executed':False,'reason_code':'UNCHANGED_ORIGINAL_REVIEW',
            'receipt':deepcopy(original),'original_invocation_ref':original['invocation_ref'],
            'checked_bindings':deepcopy(bound['adversarial_bindings']),'package_hash':bound['package_hash']}
    except (WorkflowError,KeyError,TypeError,ValueError) as error:
        return {'reusable':False,'executed':False,'reason_code':'RENEW_REVIEW','detail':str(error)}


def record_escaped_defect(subject,record):
    from .review_policy import bounded
    bounded(record)
    need(set(record)=={'id','review_id','report_ref','confirmed','provenance'},'Record only the explicit later report and original review linkage.')
    provenance=record.get('provenance',{})
    need(all(isinstance(record.get(k),str) and record[k].strip() for k in ('id','review_id','report_ref'))
         and record.get('confirmed') is True and provenance.get('kind')=='user-message'
         and provenance.get('ref') and provenance.get('actor_id'),'Actual user-confirmed report provenance is required; absence never proves zero escapes.')
    need(any(r.get('review_id')==record['review_id'] for rows in subject.get('reviews',{}).values() for r in rows),'Link an actual retained original review.')
    previous=subject.get('escaped_defect_reports',{}).get(record['id'])
    need(previous is None or previous==record,'Report identity belongs to different evidence.')
    updated=deepcopy(subject);updated.setdefault('escaped_defect_reports',{})[record['id']]=deepcopy(record)
    return updated


def record_reuse(subject,record):
    need(set(record)=={'id','review_id'} and isinstance(record.get('id'),str) and record['id'],'Explicit original review and reuse identity required.')
    rows=[r for reviews in subject.get('reviews',{}).values() for r in reviews if r.get('review_id')==record.get('review_id')]
    need(len(rows)==1,'Exactly one original review required.')
    package=subject.get('review_packages',{}).get(rows[0].get('package_hash'))
    result=review_reuse(subject,package,rows[0]);need(result['reusable'],'Original review requires renewal.')
    entry={**deepcopy(record),**result}
    previous=subject.get('review_reuse_records',{}).get(record['id'])
    need(previous is None or previous==entry,'Reuse identity belongs to another original assessment.')
    updated=deepcopy(subject);updated.setdefault('review_reuse_records',{})[record['id']]=entry
    return updated


def summarize_review(subject:dict)->dict:
    """Aggregate retained metadata only, never source/artifact bodies or providers."""
    findings=subject.get('unresolved_findings',[]);aliases=subject.get('finding_index',{}).get('aliases',{})
    groups={}
    for finding in findings:
        key=aliases.get(finding['id'],{}).get('canonical_id',finding['id'])
        groups.setdefault(key,[]).append(finding)
    actionable=[rows for rows in groups.values() if any((f.get('requested_correction') or f.get('question')) and
        (f.get('evidence_refs') or f.get('provenance')) for f in rows)]
    dispositions={k:sum(f.get('status','open')==k for f in findings) for k in ('open','resolved','waived','rejected','deferred')}
    by_perspective={};by_severity={}
    for rows in actionable:
        for p in {f.get('required_perspective') or f.get('perspective') for f in rows}- {None}:
            by_perspective[p]=by_perspective.get(p,0)+1
        for p in {p for f in rows for p in f.get('required_perspectives',[])}:
            if not any((f.get('required_perspective') or f.get('perspective'))==p for f in rows):by_perspective[p]=by_perspective.get(p,0)+1
        order={'info':0,'minor':1,'important':2,'critical':3}
        severity=max((f.get('severity','critical') for f in rows),key=lambda value:order.get(value,3))
        by_severity[severity]=by_severity.get(severity,0)+1
    reviews=[r for rows in subject.get('reviews',{}).values() for r in rows]
    referenced={r.get('model_invocation_id') for r in reviews if r.get('model_invocation_id')}
    receipts=subject.get('model_receipts',{})
    review_receipts={key:row for key,row in receipts.items() if key in referenced or str(row.get('scope',{}).get('role','')).endswith('-reviewer')}
    reviewer_models = []
    for key, row in sorted(review_receipts.items()):
        eligibility = row.get('eligibility')
        basis = eligibility.get('basis') if isinstance(eligibility, dict) else None
        reviewer_models.append({'invocation_id': key, 'resolved': deepcopy(row.get('resolved')),
            'observed': deepcopy(row.get('observed')), 'eligibility_basis': basis or (
                'released-validated' if row.get('capability_validated') is True else 'unknown'),
            'suitability': 'unvalidated' if row.get('review_authorization_hash') else (
                'validated' if row.get('capability_validated') is True else 'unknown'),
            'review_authorization_hash': row.get('review_authorization_hash'),
            'model_revision': row.get('model_revision'),
            'authorization_revoked': row.get('review_authorization_hash') in subject.get('review_model_revocations', {})})
    intervals=[];unknown_times=0
    for row in review_receipts.values():
        start,end=row.get('started_ms'),row.get('finished_ms')
        if number(start) and number(end) and end>=start:intervals.append((start,end))
        else:unknown_times+=1
    unknown_times+=len(referenced-set(receipts))
    if not review_receipts and not referenced:unknown_times=1
    known_time=sum(end-start for start,end in intervals)
    effects=list(subject.get('effects',{}).values())
    def costs(key):
        values=[row[key] for row in effects if number(row.get(key))]
        missing=len(effects)-len(values) if effects else 1
        return (sum(values) if not missing else None,sum(values),missing)
    observed,known_observed,unknown_observed=costs('observed_cost')
    estimated,known_estimated,unknown_estimated=costs('estimated_cost')
    tokens={};unknown_usage=0
    for row in receipts.values():
        usage=row.get('usage')
        from .context_metrics import explicit_runtime_usage
        measured=explicit_runtime_usage(usage)
        if not measured:unknown_usage+=1
        for key,value in measured.items():tokens[key]=tokens.get(key,0)+value
    if not receipts:unknown_usage=1
    orchestration=subject.get('review_orchestration',{});cycles=orchestration.get('cycles',[])+subject.get('repair_cycles',[])
    from .clarifications import clarification_blockers
    pending=len(clarification_blockers(subject,{}))
    escapes=subject.get('escaped_defect_reports',{})
    completed=lambda row:row.get('dispatch') is True and (row.get('transport_completed') is True or row.get('status')=='allow') and bool(row.get('invocation_ref'))
    confirmed_reviews={r['review_id'] for r in reviews if completed(receipts.get(r.get('model_invocation_id'),{})) and receipts[r['model_invocation_id']].get('diagnostic') is False}
    confirmed=sum(any(f.get('status')=='resolved' or f.get('provenance',{}).get('review_id') in confirmed_reviews for f in rows) for rows in actionable)
    unknown_invocations=sum(row.get('dispatch') is not False and not completed(row) for row in receipts.values()) if receipts else 1
    return {'scope_id':subject.get('id'),'reviewer_models':reviewer_models,'unique_actionable_findings':len(actionable),'recorded_findings':len(findings),
        'duplicate_aliases':len(findings)-len(groups),'finding_dispositions':dispositions,
        'findings_by_perspective':dict(sorted(by_perspective.items())),'findings_by_severity':dict(sorted(by_severity.items())),
        'confirmed_escaped_defects':len({row['report_ref'] for row in escapes.values() if row.get('confirmed') is True}) if escapes else None,
        'review_wall_ms':max(e for _,e in intervals)-min(s for s,_ in intervals) if intervals and not unknown_times else None,
        'summed_invocation_ms':known_time if not unknown_times else None,
        'observed_cost':observed,'estimated_reserved_cost':estimated,'observed_tokens':tokens or None,
        'unknown_measurements':{'review_intervals':unknown_times,'observed_cost':unknown_observed,'estimated_reserved_cost':unknown_estimated,
            'model_usage':unknown_usage,'model_invocations':unknown_invocations,'escaped_defect_reports':0 if escapes else 1},
        'known_subtotals':{'summed_invocation_ms':known_time,'observed_cost':known_observed,'estimated_reserved_cost':known_estimated},
        'repair_cycles':len(cycles),'no_progress_cycles':sum(c.get('status')=='recorded' and c.get('made_progress') is False for c in cycles),
        'no_progress_stops':sum(c.get('reason_code')=='NO_PROGRESS' for c in subject.get('repair_cycles',[]))+len(orchestration.get('stop_records',{}))+(int(orchestration.get('blocker',{}).get('reason_code')=='NO_PROGRESS') if not orchestration.get('stop_records') else 0),
        'blocking_questions':pending,'review_reuses':len(subject.get('review_reuse_records',{})),
        'model_attempt_receipts':len(receipts),'model_invocations':sum(completed(r) for r in receipts.values()),
        'review_invocations':sum(completed(r) for r in review_receipts.values()),'confirmed_actionable_findings':confirmed,
        'unresolved_actionable_findings':sum(any(f.get('status','open') not in {'resolved','waived','rejected','deferred'} for f in rows) for rows in actionable)}
