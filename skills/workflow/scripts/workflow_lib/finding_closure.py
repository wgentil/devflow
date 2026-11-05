"""Correction candidates are not independent finding resolution."""
from copy import deepcopy
from .store import WorkflowError
from .action_policy import require_action, subject_decision


def _require(ok, message):
    if not ok: raise WorkflowError('FINDING_CLOSURE_BLOCKED', message)


def propose_correction(subject: dict, request: dict) -> dict:
    finding = next((f for f in subject.get('unresolved_findings', []) if f['id'] == request.get('finding_id')), None)
    _require(finding and request.get('source_identity') == subject.get('source_identity')
             and bool(request.get('source_identity')) and isinstance(request.get('proof_ids'), list)
             and request.get('rationale'), 'Candidate needs a known finding, current source, proof references and rationale.')
    updated = deepcopy(subject)
    updated.setdefault('corrections', {})[finding['id']] = deepcopy(request)
    return updated


def validate_closure(subject: dict, request: dict) -> dict:
    finding = next((f for f in subject.get('unresolved_findings', []) if f['id'] == request.get('finding_id')), None)
    _require(finding, 'Unknown finding.')
    require_action(subject_decision(subject, 'finding', {'item_id': finding['item_id']} if finding.get('item_id') else {}))
    _require(not finding.get('unresolved_disagreements'), 'Resolve the recorded reviewer disagreement through independent adjudication first.')
    source = subject.get('source_identity')
    candidate = subject.get('corrections', {}).get(finding['id'], {})
    _require(source and candidate.get('source_identity') == source, 'Current candidate required.')
    reviews = [r for rows in subject.get('reviews', {}).values() for r in rows
               if r.get('review_id') == request.get('review_id')]
    _require(len(reviews) == 1, 'Exactly one recorded independent review required.')
    review = reviews[0]
    implementers = set(subject.get('implementer_actors', [])) | {subject.get('actors', {}).get('implementer')}
    _require(review.get('actor_id') and review['actor_id'] not in implementers
             and review.get('invocation_ref') and review.get('fresh') is not False
             and review.get('verdict') in {'pass', 'request-changes', 'block'}, 'Fresh completed independent assessment required.')
    from .stored_records import require_package
    from .review_enforcement import review_bindings_current
    package = require_package(subject.get('review_packages', {}).get(review.get('package_hash')))
    _require(review_bindings_current(subject, package, live=False), 'Current review input and question bindings required.')
    _require(package.get('source_identity') == source, 'Review package must bind current corrected source.')
    required_perspectives = set(finding.get('required_perspectives', []))
    if finding.get('required_perspective'): required_perspectives.add(finding['required_perspective'])
    _require(not required_perspectives or required_perspectives.issubset({review.get('perspective')}),
             'The actual independent invocation must cover the required perspective; one invocation cannot impersonate multiple reviewers.')
    dispositions = [d for d in review.get('closure_dispositions', []) if d.get('finding_id') == finding['id']]
    _require(len(dispositions) == 1, 'Explicit independent finding disposition required.')
    disposition = dispositions[0]
    _require(disposition.get('disposition') == 'resolved' and disposition.get('source_identity') == source
             and set(disposition.get('obligations', [])) == set(finding.get('obligations', [finding['id']])),
             'Every consolidated obligation must be independently resolved on current source.')
    proofs = candidate.get('proof_ids', [])
    _require(set(proofs) == set(disposition.get('proof_ids', [])), 'Review must cover candidate proofs.')
    if not proofs:
        applicability = disposition.get('execution_inapplicable', {})
        _require(applicability.get('reason') and applicability.get('evidence_refs'), 'Execution inapplicability requires independent evidence.')
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
