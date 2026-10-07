"""Versioned, reviewable cases derived from opted-in traces."""

from .journal_domains import digest
from .store import WorkflowError

OWNERS = {'repository', 'skill', 'helper', 'validator', 'test', 'host-adapter', 'no-change'}


def propose_case(trace: dict, feedback: dict) -> dict:
    if not isinstance(feedback, dict) or feedback.get('owner') not in OWNERS:
        raise WorkflowError('INVALID_FEEDBACK', 'known improvement owner required')
    if not isinstance(feedback.get('observation'), str) or not feedback['observation'].strip():
        raise WorkflowError('INVALID_FEEDBACK', 'concrete observation required')
    command = feedback.get('command')
    if not isinstance(command, list) or not command or not all(isinstance(v, str) and v for v in command):
        raise WorkflowError('INVALID_CASE', 'executable argv case required')
    expected = feedback.get('expected')
    if not isinstance(expected, dict) or not expected:
        raise WorkflowError('INVALID_CASE', 'expected observable behavior required')
    if type(feedback.get('scoring_version')) is not int or feedback['scoring_version'] < 1:
        raise WorkflowError('INVALID_CASE', 'positive scoring version required')
    case = {'version': 1, 'source_run_id': trace['run_id'], 'trace_hash': digest(trace),
            'owner': feedback['owner'], 'expected': expected, 'command': command,
            'scoring_version': feedback['scoring_version'],
            'timeout_seconds': feedback.get('timeout_seconds', 60)}
    if 'stage' in feedback:
        from .model_validation import STAGES
        if feedback['stage'] not in STAGES:
            raise WorkflowError('INVALID_CASE', 'supported model evaluation stage required')
        case['stage'] = feedback['stage']
    if type(case['timeout_seconds']) is not int or not 1 <= case['timeout_seconds'] <= 900:
        raise WorkflowError('INVALID_CASE', 'case timeout must be 1 to 900 seconds')
    case_hash = digest(case)
    return {**case, 'case_id': 'case-' + case_hash[:16], 'case_hash': case_hash}
