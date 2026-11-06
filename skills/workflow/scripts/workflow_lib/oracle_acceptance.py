"""Independent review of actual runtime proof, without an extra pre-test review round."""
from .store import WorkflowError
from .document_units import digest
from .clarifications import clarification_binding
from .test_integrity import validate_test_pair


def _require(ok, message):
    if not ok: raise WorkflowError('ORACLE_REVIEW_REQUIRED', message)


def validate_oracle_acceptance(subject: dict, package: dict, review: dict) -> dict:
    oracles = review.get('test_oracles', [])
    _require(isinstance(oracles, list), 'Test oracle assessments must be an array.')
    if review.get('role') not in {'item', 'branch'}:
        _require(not oracles, 'Oracle approval belongs to independent item or branch review.')
        return {}
    implementers = set(subject.get('implementer_actors', [])) | {subject.get('actors', {}).get('implementer')}
    _require(review.get('actor_id') and review['actor_id'] not in implementers
             and review.get('invocation_ref') and review.get('review_id'), 'Actual independent reviewer identity and invocation required.')
    accepted = {}
    for oracle in oracles:
        _require(isinstance(oracle, dict), 'Each oracle assessment must be an object.')
        item_id = oracle.get('item_id')
        item = next((i for i in subject.get('plan', {}).get('work_items', []) if i['id'] == item_id), None)
        _require(item and item.get('kind') == 'code', 'Oracle assessment needs a planned code item.')
        if review['role'] == 'item': _require(item_id == review.get('item_id'), 'Oracle assessment is outside the item review scope.')
        green = subject.get('verification_proofs', {}).get(oracle.get('green_proof_id'), {})
        red = subject.get('verification_proofs', {}).get(oracle.get('red_proof_id'), {})
        if not red and green.get('red_source'):
            red = green.get('red_baseline', {})
            lineage = green['red_source']
            _require(red.get('id') == oracle.get('red_proof_id') == lineage.get('proof_id')
                     and red.get('token') == lineage.get('token'),
                     'Sealed RED must match the original validated reuse lineage.')
        attempts = subject.get('items', {}).get(item_id, {}).get('attempts', [])
        _require(attempts and green.get('token') == attempts[-1].get('token')
                 and green.get('item_id') == item_id and red.get('item_id') == item_id
                 and green.get('passed') is True and green.get('fresh') is not False
                 and red.get('passed') is True and red.get('fresh') is not False,
                 'Current recorded RED/GREEN evidence for the item required.')
        _require(red.get('token') == green.get('token') or green.get('red_source', {}).get('proof_id') == red.get('id'),
                 'RED must belong to the attempt or its explicitly validated reuse lineage.')
        _require(green.get('source_identity') and green['source_identity'] == subject.get('source_identity')
                 == package.get('source_identity'), 'Review must cover the actual corrected source.')
        contract = green.get('integrity', {}).get('contract', {})
        _require(contract.get('spec_hash') == subject.get('plan', {}).get('spec_hash')
                 and contract.get('item_contract_hash') == digest(item)
                 and contract.get('oracle_authority') == [
                     {'spec_hash': subject['plan']['spec_hash'], 'requirement_id': rid}
                     for rid in item.get('requirement_ids', [])],
                 'Oracle authority must match the current approved item and specification.')
        validate_test_pair(red.get('integrity', {}), green.get('integrity', {}), contract, require_review=False)
        _require(oracle.get('input_hashes') == contract.get('input_hashes')
                 and set(oracle.get('target_ids', [])) == set(contract.get('targets', []))
                 and oracle.get('clarification_binding') == contract.get('clarification_binding')
                 == clarification_binding(subject, {'item_id': item_id}), 'Exact inputs, targets and user-answer versions required.')
        authorities = {'spec:' + row['spec_hash'] + '#' + row['requirement_id'] for row in contract.get('oracle_authority', [])}
        _require(authorities and authorities.issubset(set(oracle.get('authority_refs', [])))
                 and oracle.get('failure_relevance') and oracle.get('rationale'), 'Cite the independent authority and actual failure relevance.')
        _require(green['id'] not in accepted, 'Duplicate oracle assessment for one proof.')
        accepted[green['id']] = {'review_id': review['review_id'], 'source_identity': green['source_identity'],
            'red_proof_id': red['id'], 'clarification_binding': oracle['clarification_binding'],
            'semantic_status': 'reviewed'}
    if review.get('verdict') == 'pass':
        relevant = [i for i in subject.get('plan', {}).get('work_items', []) if i.get('kind') == 'code'
                    and (review['role'] != 'item' or i['id'] == review.get('item_id'))]
        for item in relevant:
            attempts = subject.get('items', {}).get(item['id'], {}).get('attempts', [])
            _require(attempts, 'Passing review requires executed code evidence.')
            current = [p for p in subject.get('verification_proofs', {}).values() if p.get('item_id') == item['id']
                       and p.get('token') == attempts[-1].get('token') and p.get('phase') == 'GREEN'
                       and p.get('passed') is True and p.get('fresh') is not False]
            _require(current and current[-1]['id'] in accepted, 'Passing review must assess the current code proof, oracle and failure discrimination.')
    from .review_policy import review_version
    if review_version(subject)==1 and review.get('verdict')=='pass' and review.get('perspective')=='test':
        from .test_challenges import validate_test_quality
        validate_test_quality(subject,package,review)
    return accepted
