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
             and review.get('verdict') == 'pass', 'Fresh independent passing review required.')
    package = subject.get('review_packages', {}).get(review.get('package_hash'), {})
    _require(package.get('source_identity') == source, 'Review package must bind current corrected source.')
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
    for identifier in proofs:
        proof = subject.get('verifier_proofs', {}).get(identifier, {})
        _require(proof.get('passed') is True and proof.get('fresh') is not False
                 and proof.get('source_identity') == source, 'Current applicable verifier proof required.')
    return {'status': 'resolved', 'review_id': review['review_id'], 'source_identity': source,
            'proof_ids': list(proofs), 'disposition': deepcopy(disposition)}
