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


def validate_test_pair(red: dict, green: dict, contract: dict, *, require_review: bool = True) -> dict:
    def require(ok, reason):
        if not ok: raise WorkflowError('TEST_INTEGRITY_BLOCKED', reason)
    require(contract.get('schema_version') == 2 and contract.get('targets') and contract.get('input_hashes')
            and contract.get('tool') and (contract.get('oracle_review') if require_review else contract.get('oracle_authority')), 'Complete independently reviewed verification contract required.')
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


def verification_integrity_contract(subject: dict, item: dict, input_hashes: dict, targets: list[str], argv: list[str], report_format: str, input_bindings: dict | None = None) -> dict:
    declared = item.get('verification_inputs')
    if not isinstance(declared, list) or not declared or set(declared) != set(input_hashes):
        raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Approved item must declare all verification inputs.')
    if set(item.get('verification_target_ids', [])) != set(targets):
        raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Targets differ from the approved item contract.')
    if not isinstance(input_bindings, dict) or set(input_bindings) != set(input_hashes) or any(
            binding.get('sha256') != input_hashes[name] for name,binding in input_bindings.items()):
        raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Actual input identity bindings required.')
    authority = item.get('requirement_ids')
    if not subject.get('plan', {}).get('spec_hash') or not isinstance(authority, list) or not authority:
        raise WorkflowError('TEST_INTEGRITY_BLOCKED', 'Approved specification and requirement authority required before runtime capture.')
    from .clarifications import clarification_binding
    from .document_units import digest
    return {'schema_version': 2, 'targets': sorted(set(targets)), 'input_hashes': input_hashes,
            'tool': list(argv), 'report_format': report_format, 'input_bindings': input_bindings,
            'oracle_authority': [{'spec_hash': subject['plan']['spec_hash'], 'requirement_id': rid} for rid in authority],
            'clarification_binding': clarification_binding(subject, {'item_id': item['id']}),
            'spec_hash': subject['plan']['spec_hash'], 'item_id': item['id'], 'item_contract_hash': digest(item)}
