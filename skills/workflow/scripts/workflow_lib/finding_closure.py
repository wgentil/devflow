"""Correction candidates are not independent finding resolution."""
from copy import deepcopy
from .store import WorkflowError
from .action_policy import require_action, subject_decision


def _require(ok, message):
    if not ok: raise WorkflowError('FINDING_CLOSURE_BLOCKED', message)


def validate_waiver(subject: dict, finding: dict) -> None:
    from .action_policy import enforcement_version
    if enforcement_version(subject) is None:
        return
    _require(finding.get('non_waivable') is not True and finding.get('waivable') is not False,
             'This finding cannot be waived.')
    require_action(subject_decision(subject, 'finding', {'item_id': finding['item_id']} if finding.get('item_id') else {}))


def finding_hash(finding: dict) -> str:
    from .document_units import digest
    return digest({k:v for k,v in finding.items() if k not in {'status','resolution'}})


def propose_correction(subject: dict, request: dict) -> dict:
    finding = next((f for f in subject.get('unresolved_findings', []) if f['id'] == request.get('finding_id')), None)
    _require(finding and request.get('source_identity') == subject.get('source_identity')
             and bool(request.get('source_identity')) and isinstance(request.get('proof_ids'), list)
             and request.get('rationale'), 'Candidate needs a known finding, current source, proof references and rationale.')
    updated = deepcopy(subject)
    _require(not request.get('finding_hash') or request['finding_hash']==finding_hash(finding),'Candidate finding contract changed.')
    updated.setdefault('corrections', {})[finding['id']] = {**deepcopy(request),'finding_hash':finding_hash(finding)}
    return updated


def _validate_one(subject: dict, request: dict, *, check_perspective=True) -> dict:
    finding = next((f for f in subject.get('unresolved_findings', []) if f['id'] == request.get('finding_id')), None)
    _require(finding, 'Unknown finding.')
    require_action(subject_decision(subject, 'finding', {'item_id': finding['item_id']} if finding.get('item_id') else {}))
    _require(not finding.get('unresolved_disagreements'), 'Resolve the recorded reviewer disagreement through independent adjudication first.')
    source = subject.get('source_identity')
    candidate = subject.get('corrections', {}).get(finding['id'], {})
    _require(source and candidate.get('source_identity') == source and candidate.get('finding_hash')==finding_hash(finding), 'Current candidate and finding contract required.')
    reviews = [r for rows in subject.get('reviews', {}).values() for r in rows
               if r.get('review_id') == request.get('review_id')]
    _require(len(reviews) == 1, 'Exactly one recorded independent review required.')
    review = reviews[0]
    _require(finding.get('provenance',{}).get('review_id') != review.get('review_id'),
             'A report cannot resolve its own newly originated finding; require a later current assessment.')
    implementers = set(subject.get('implementer_actors', [])) | {subject.get('actors', {}).get('implementer')}
    _require(review.get('actor_id') and review['actor_id'] not in implementers
             and review.get('invocation_ref') and review.get('fresh') is not False
             and review.get('verdict') in {'pass', 'request-changes', 'block', 'changes-requested', 'blocked', 'needs-clarification'}, 'Fresh completed independent assessment required.')
    from .stored_records import require_package
    from .review_enforcement import review_bindings_current
    package = require_package(subject.get('review_packages', {}).get(review.get('package_hash')))
    if subject.get('review_contract_hash'):
        from .session_evidence import package_current
        _require(package_current(subject,package),'Current standalone review package required.')
    else:_require(review_bindings_current(subject, package, live=False), 'Current review input and question bindings required.')
    _require(package.get('source_identity') == source, 'Review package must bind current corrected source.')
    from .review_policy import review_version
    if review_version(subject) is not None:
        from .finding_index import _recorded_review
        _recorded_review(subject,review['review_id'],diagnostic_allowed=False)
        _require(review.get('role')!='item' or finding.get('item_id')==review.get('item_id'),
                 'An item reviewer cannot resolve another item outside its actual package scope.')
    required_perspectives = set(finding.get('required_perspectives', []))
    if finding.get('required_perspective'): required_perspectives.add(finding['required_perspective'])
    _require(not check_perspective or not required_perspectives or (isinstance(review.get('perspective'),str) and required_perspectives.issubset({review['perspective']})),
             'The actual independent invocation must cover the required perspective; one invocation cannot impersonate multiple reviewers.')
    dispositions = [d for d in review.get('closure_dispositions', []) if d.get('finding_id') == finding['id']]
    _require(len(dispositions) == 1, 'Explicit independent finding disposition required.')
    disposition = dispositions[0]
    _require(disposition.get('disposition') == 'resolved' and disposition.get('source_identity') == source
             and disposition.get('finding_hash')==finding_hash(finding)
             and set(disposition.get('obligations', [])) == set(finding.get('obligations', [finding['id']])),
             'Every consolidated obligation must be independently resolved on current source.')
    proofs = candidate.get('proof_ids', [])
    _require(set(proofs) == set(disposition.get('proof_ids', [])), 'Review must cover candidate proofs.')
    if not proofs:
        applicability = disposition.get('execution_inapplicable', {})
        _require(applicability.get('reason') and 'package:'+review['package_hash'] in applicability.get('evidence_refs',[])
                 and finding.get('execution_required') is not True, 'Execution inapplicability requires applicable current package evidence.')
    if proofs:
        applicability = disposition.get('proof_applicability', {})
        obligations = set(finding.get('obligations', [finding['id']]))
        _require(isinstance(applicability, dict) and set(applicability) == set(proofs)
                 and all(isinstance(values, list) and values and set(values).issubset(obligations)
                         for values in applicability.values())
                 and set().union(*(set(values) for values in applicability.values())) == obligations,
                 'Independent proof applicability must cover every consolidated obligation.')
    for identifier in proofs:
        proof = subject.get('verifier_proofs', {}).get(identifier, {})
        _require(proof.get('passed') is True and proof.get('fresh') is not False
                 and proof.get('source_identity') == source, 'Current applicable verifier proof required.')
        if subject.get('review_contract_hash'):
            evidence=subject.get('verification_proofs',{}).get(proof.get('evidence_id'),{})
            _require(proof.get('contract_hash')==subject['review_contract_hash'] and evidence.get('session_id')==subject['id']
                     and evidence.get('contract_hash')==subject['review_contract_hash'] and evidence.get('phase')=='GREEN'
                     and proof.get('semantic_status')=='reviewed' and evidence.get('source_identity')==source,
                     'Current independently accepted standalone repair proof required.')
            continue
        item_id = proof.get('item_id')
        item = next((i for i in subject.get('plan', {}).get('work_items', []) if i['id'] == item_id), None)
        attempts = subject.get('items', {}).get(item_id, {}).get('attempts', [])
        evidence = subject.get('verification_proofs', {}).get(proof.get('evidence_id'), {})
        _require(item and attempts and proof.get('token') == attempts[-1].get('token')
                 and (not finding.get('item_id') or item_id == finding['item_id'])
                 and evidence.get('item_id') == item_id and evidence.get('token') == proof.get('token')
                 and evidence.get('fresh') is not False and evidence.get('passed') is True
                 and evidence.get('source_identity') == source,
                 'Proof must bind the applicable current item attempt and actual corrected execution.')
        eligible = ((item.get('kind') == 'code' and evidence.get('kind') == 'code'
                     and evidence.get('phase') == 'GREEN' and proof.get('semantic_status') == 'reviewed')
                    or (item.get('kind') == 'iac' and evidence.get('kind') == 'iac-apply')
                    or (item.get('kind') == 'agent-config' and evidence.get('kind') == 'agent-evaluation'
                        and evidence.get('phase') == 'post'))
        _require(eligible, 'Applicable corrected proof kind and independent code-oracle acceptance required.')
    return {'status': 'resolved', 'review_id': review['review_id'], 'source_identity': source,
            'proof_ids': list(proofs), 'disposition': deepcopy(disposition)}


def validate_closure(subject: dict, request: dict) -> dict:
    identifiers=request.get('review_ids') or [request.get('review_id')]
    _require(isinstance(identifiers,list) and identifiers and all(isinstance(i,str) and i for i in identifiers)
             and len(set(identifiers))==len(identifiers),'Distinct recorded review identities required.')
    results=[_validate_one(subject,{**request,'review_id':i},check_perspective=False) for i in identifiers]
    reviews=[r for rows in subject.get('reviews',{}).values() for r in rows if r.get('review_id') in identifiers]
    finding=next(f for f in subject['unresolved_findings'] if f['id']==request['finding_id'])
    required=set(finding.get('required_perspectives',[]))
    if finding.get('required_perspective'):required.add(finding['required_perspective'])
    _require(required.issubset({r.get('perspective') for r in reviews}), 'All required perspectives need actual dispositions.')
    if len(required)>1:
        _require(len({r['actor_id'] for r in reviews})==len(reviews)
                 and len({r['invocation_ref'] for r in reviews})==len(reviews), 'Perspectives require distinct actual reviewer invocations.')
    return {**results[0],'review_ids':identifiers,'finding_hash':finding_hash(finding),
            'dispositions':[r['disposition'] for r in results]}
