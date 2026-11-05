"""Versioned questions and recorded user answers; no business-rule inference."""
from copy import deepcopy
from .store import WorkflowError


def record_question(subject: dict, request: dict) -> dict:
    if (not isinstance(request.get('id'), str) or not request['id'].strip()
            or not isinstance(request.get('text'), str) or not request['text'].strip()
            or not request.get('source_identity') or request.get('spec_hash') != subject.get('plan', {}).get('spec_hash')):
        raise WorkflowError('INVALID_QUESTION', 'Question needs identity, text and current source/spec binding.')
    scope = request.get('scope')
    known = {row['id'] for row in subject.get('plan', {}).get('work_items', [])}
    if scope is not None and (not isinstance(scope, list) or not scope or any(i not in known for i in scope)):
        raise WorkflowError('INVALID_QUESTION_SCOPE', 'Use known items or unknown scope.')
    updated = deepcopy(subject)
    questions = updated.setdefault('clarifications', {})
    prior = questions.get(request['id'])
    row = deepcopy(request)
    row.update(version=prior['version']+1 if prior else 1, status='pending')
    if prior:
        row['history'] = prior.get('history', []) + [{k: v for k,v in prior.items() if k != 'history'}]
    questions[request['id']] = row
    updated['enforcement_revision'] = subject.get('enforcement_revision', 0)+1
    return updated


def record_answer(subject: dict, request: dict) -> dict:
    question = subject.get('clarifications', {}).get(request.get('id'))
    provenance = request.get('provenance', {})
    if (not question or question['version'] != request.get('question_version')
            or question.get('status') != 'pending' or not isinstance(request.get('answer'), str)
            or not request['answer'].strip() or not isinstance(request.get('actor_id'), str)
            or not request['actor_id'].strip() or provenance.get('kind') != 'user-message'
            or not provenance.get('ref') or type(request.get('material', False)) is not bool
            or not request.get('spec_hash')):
        raise WorkflowError('INVALID_USER_ANSWER', 'Record the actual user answer to the exact pending question version.')
    updated = deepcopy(subject)
    row = updated['clarifications'][request['id']]
    row.update(answer=deepcopy(request), status='answered')
    updated['enforcement_revision'] = subject.get('enforcement_revision', 0)+1
    return updated


def clarification_blockers(subject: dict, scope: dict) -> list[dict]:
    items = subject.get('plan', {}).get('work_items', [])
    graph = {row['id']: row.get('dependencies', []) for row in items}
    target = scope.get('item_id')
    ancestors = set()
    pending = [target] if target in graph else []
    while pending:
        node = pending.pop()
        if node in ancestors: continue
        ancestors.add(node); pending.extend(graph.get(node, []))
    blockers = []
    for row in subject.get('clarifications', {}).values():
        affected = row.get('scope')
        if target in graph and affected is not None and not ancestors.intersection(affected): continue
        answer = row.get('answer', {})
        valid = (row.get('status') == 'answered' and answer.get('question_version') == row.get('version')
                 and answer.get('spec_hash') == subject.get('plan', {}).get('spec_hash'))
        if answer.get('material'):
            valid = valid and subject.get('spec_approval', {}).get('content_hash') == answer.get('spec_hash')
        if not valid:
            blockers.append({'id': row['id'], 'version': row['version'], 'reason_code': 'CLARIFICATION_REQUIRED'})
    return blockers
