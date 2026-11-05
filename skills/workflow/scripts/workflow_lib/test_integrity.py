"""Conservative structured outcome classification and linked proof validation."""
import json
from .store import WorkflowError


def parse_test_evidence(stdout: str, stderr: str, report_format: str) -> dict:
    from .evidence import _report
    outcomes = _report(stdout, stderr, report_format)
    # Generic failure reports establish outcome, not failure phase or relevance.
    classifications = {key: 'unknown' for key in outcomes}
    if report_format == 'json':
        report = json.loads(stdout)
        if report.get('schema') == 'devflow-test-report-v2':
            for row in report['tests']:
                phase = row.get('failure_phase')
                if row['outcome'] == 'failed' and phase == 'test-assertion':
                    classifications[row['id']] = 'assertion'
                elif phase in {'setup', 'import', 'discovery', 'teardown'}:
                    classifications[row['id']] = phase
    return {'outcomes': outcomes, 'classification': classifications,
            'limitation': 'Generic reports do not substantiate assertion phase or business-rule relevance.'}


def validate_test_pair(red: dict, green: dict, contract: dict) -> dict:
    def require(ok, reason):
        if not ok: raise WorkflowError('TEST_INTEGRITY_BLOCKED', reason)
    require(contract.get('schema_version') == 2 and contract.get('targets') and contract.get('input_hashes')
            and contract.get('tool') and contract.get('oracle_review'), 'Complete independently reviewed verification contract required.')
    require(red.get('phase') == 'RED' and green.get('phase') == 'GREEN'
            and red.get('passed') is True and green.get('passed') is True
            and red.get('contract') == contract == green.get('contract'), 'Matching linked proof contracts required.')
    require(red.get('source_identity') and green.get('source_identity')
            and green.get('baseline_source') == red['source_identity'], 'Linked baseline and correction source identities required.')
    require(type(red.get('exit_code')) is int and red['exit_code'] != 0
            and green.get('exit_code') == 0, 'Actual failed baseline and successful correction required.')
    require(all(row.get('stdout_ref') and row.get('stderr_ref') for row in (red, green)), 'Raw reports must be retained.')
    targets = contract['targets']
    require(all(t in red.get('outcomes', {}) for t in targets)
            and any(red['outcomes'][t] == 'failed' and red.get('classification', {}).get(t) == 'assertion' for t in targets)
            and all(red['outcomes'][t] in {'failed', 'passed'} for t in targets)
            and all(green.get('outcomes', {}).get(t) == 'passed' for t in targets), 'Relevant target assertion failure and complete passing targets required.')
    return {'passed': True, 'baseline_source': red['source_identity'], 'source_identity': green['source_identity']}


def verification_integrity_contract(subject: dict, item: dict, input_hashes: dict, targets: list[str], argv: list[str], report_format: str) -> dict:
    declared = item.get('verification_inputs')
    if not isinstance(declared, list) or not declared or set(declared) != set(input_hashes):
        raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Approved item must declare all verification inputs.')
    if set(item.get('verification_target_ids', [])) != set(targets):
        raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Targets differ from the approved item contract.')
    implementers = set(subject.get('implementer_actors', [])) | {subject.get('actors', {}).get('implementer')}
    eligible = []
    for rows in subject.get('reviews', {}).values():
        for review in rows:
            if (review.get('actor_id') and review['actor_id'] not in implementers
                    and review.get('invocation_ref') and review.get('verdict') == 'pass'):
                for oracle in review.get('test_oracles', []):
                    if (oracle.get('item_id') == item.get('id') and oracle.get('input_hashes') == input_hashes
                            and set(oracle.get('target_ids', [])) == set(targets)
                            and oracle.get('spec_hash') == subject.get('plan', {}).get('spec_hash')
                            and oracle.get('rationale') and oracle.get('authority_refs') and oracle.get('failure_relevance')):
                        eligible.append(review['review_id'])
    if not eligible:
        raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Independent oracle and failure-relevance review of these exact inputs required.')
    return {'schema_version': 2, 'targets': sorted(set(targets)), 'input_hashes': input_hashes,
            'tool': list(argv), 'report_format': report_format, 'oracle_review': sorted(eligible)[-1],
            'spec_hash': subject.get('plan', {}).get('spec_hash'), 'item_id': item['id']}
