"""Short derived intent, causal rationale and deterministic review prerequisites."""
from copy import deepcopy
from .clarifications import record_question, clarification_blockers, current_questions
from .document_units import digest
from .review_policy import bounded, review_bindings, require_review_policy
from .store import WorkflowError


def need(condition, message):
    if not condition:
        raise WorkflowError('IMPLEMENTATION_CONTRACT_BLOCKED', message)


def scope_key(scope):
    return 'item:' + scope['item_id'] if scope.get('item_id') else scope.get('role', 'branch')


def _scope(scope):
    return {k: v for k, v in scope.items() if k != 'diagnostic'}


def contract_binding(subject, scope):
    contracts = subject.get('implementation_contracts', {})
    if scope.get('item_id'):
        selected = {'item:' + scope['item_id']: contracts.get('item:' + scope['item_id'])}
        items = {i['id']: i for i in subject.get('plan', {}).get('work_items', [])}
        pending = list(items.get(scope['item_id'], {}).get('dependencies', []));seen=set()
        while pending:
            item = pending.pop()
            if item in seen:continue
            seen.add(item);selected['item:' + item] = contracts.get('item:' + item)
            if item not in items or not isinstance(items[item].get('dependencies'), list):
                return digest(contracts)
            pending.extend(items[item]['dependencies'])
    else:
        selected = contracts
    return digest(selected)


def bindings(subject, scope):
    return {k: v for k, v in review_bindings(subject, _scope(scope)).items() if k != 'contract_hash'}


def authority_refs(subject, scope):
    if subject.get('review_contract_hash'):
        request = subject['review_contract']['request']
        allowed = set(request.get('authority_refs', []))
        allowed.update('intent:' + subject['review_contract_hash'] + '#' + row['id']
                       for row in request.get('intent', []) if isinstance(row, dict) and row.get('id'))
    else:
        plan = subject.get('plan', {})
        selected = [i for i in plan.get('work_items', []) if not scope.get('item_id') or i['id'] == scope['item_id']]
        allowed = {'spec:' + plan['spec_hash'] + '#' + rid for i in selected for rid in i.get('requirement_ids', [])}
    for question in current_questions(subject, {'item_id': scope['item_id']} if scope.get('item_id') else {}):
        answer = question.get('answer', {})
        if (question.get('status') == 'answered' and answer.get('material') is False
                and answer.get('provenance', {}).get('kind') == 'user-message' and answer['provenance'].get('ref')):
            allowed.add('question:' + question['id'] + ':' + str(question['version']))
    return allowed


def _refs(value):
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def _question(subject, request, intent_hash):
    scope = request['scope'];key = digest({'scope': scope, 'intent': intent_hash, 'authority': bindings(subject, scope)})[:24]
    identifier = 'contract-' + key
    if identifier in subject.get('clarifications', {}):
        return deepcopy(subject)
    from .clarifications import authority_binding
    authority_key, authority_hash = authority_binding(subject)
    return record_question(subject, {'id': identifier, 'text': request.get('question') or
        'Which approved rule or actual user decision defines this intended behavior?',
        'scope': [scope['item_id']] if scope.get('item_id') else None,
        'source_identity': subject['source_identity'], authority_key: authority_hash})


def record_implementation_contract(subject, record):
    bounded(record);require_review_policy(subject)
    allowed = {'scope', 'source_identity', 'behaviors', 'invariants', 'non_goals', 'interfaces', 'neighboring',
               'neighboring_disposition', 'checks', 'question', 'intent_decision', 'previous_contract_hash'}
    need(isinstance(record, dict) and not set(record) - allowed, 'Contract fields cannot import approval/history or commands.')
    scope = record.get('scope')
    need(subject.get('status') == 'active' and isinstance(scope, dict) and scope.get('role') in {'item','branch','session'},
         'Active scope and explicit item/branch/session role required.')
    need(record.get('source_identity') and record['source_identity'] == subject.get('source_identity'), 'Observe current source before deriving a contract.')
    known = {i['id'] for i in subject.get('plan', {}).get('work_items', [])}
    need(not scope.get('item_id') or scope['item_id'] in known, 'Contract item must belong to the approved plan.')
    behaviors = record.get('behaviors')
    need(isinstance(behaviors, list) and behaviors and all(isinstance(b, dict) and b.get('id') and b.get('text') for b in behaviors),
         'Describe explicit observable behaviors.')
    for behavior in behaviors:
        need(not set(behavior)-{'id','text','authority_refs','target_ids','incorrect_behaviors'},'Behavior metadata must use known fields; do not hide unapproved intent in extra fields.')
        for key in ('target_ids','incorrect_behaviors'):
            need(key not in behavior or isinstance(behavior[key],list) and all(isinstance(v,str) and v for v in behavior[key]),'Test selections must be explicit string arrays.')
    for field in ('invariants','non_goals','interfaces'):
        need(isinstance(record.get(field), list) and all(isinstance(v, str) and v.strip() for v in record[field]),
             'Record invariants, boundaries/non-goals and interfaces, using explicit lists.')
    for check in record.get('checks', []):
        need(isinstance(check, str) and check in subject.get('hardening_config', {}), 'Reference configured check IDs; do not import commands.')
    intent = {k: deepcopy(record[k]) for k in ('behaviors','invariants','non_goals','interfaces')}
    intent['behaviors']=[{k:v for k,v in b.items() if k not in {'target_ids','incorrect_behaviors'}} for b in intent['behaviors']]
    intent_hash = digest(intent)
    authority = authority_refs(subject, scope)
    if not all(_refs(b.get('authority_refs')) and set(b['authority_refs']).issubset(authority) for b in behaviors):
        return _question(subject, record, intent_hash)
    prior = subject.get('implementation_contracts', {}).get(scope_key(scope))
    previous_intent={k:deepcopy(prior[k]) for k in ('behaviors','invariants','non_goals','interfaces')} if prior else None
    if previous_intent:previous_intent['behaviors']=[{k:v for k,v in b.items() if k not in {'target_ids','incorrect_behaviors'}} for b in previous_intent['behaviors']]
    if prior and digest(previous_intent) != intent_hash:
        decision = record.get('intent_decision', {})
        question = subject.get('clarifications', {}).get(decision.get('question_id'), {})
        decision_ref = 'question:' + str(question.get('id')) + ':' + str(question.get('version'))
        old_authority = prior['bindings'].get('authority_hash')
        current_authority = bindings(subject, scope).get('authority_hash')
        if old_authority == current_authority and not (question.get('version') == decision.get('question_version') and decision_ref in authority):
            return _question(subject, record, intent_hash)
    if prior and record.get('previous_contract_hash') not in {None, prior['contract_hash']}:
        raise WorkflowError('CONTRACT_VERSION_CONFLICT', 'Renew from the exact current contract.')
    contract = {k: deepcopy(v) for k,v in record.items() if k not in {'question','previous_contract_hash'}}
    contract.update(schema_version=1, bindings=bindings(subject, scope), intent_hash=intent_hash)
    contract['contract_hash'] = digest(contract)
    updated = deepcopy(subject)
    if prior and prior['contract_hash'] != contract['contract_hash']:
        updated.setdefault('implementation_contract_history', []).append(deepcopy(prior))
    updated.setdefault('implementation_contracts', {})[scope_key(scope)] = contract
    return updated


def contract_current(subject, contract):
    return (isinstance(contract, dict) and contract.get('bindings') == bindings(subject, contract.get('scope', {}))
            and contract.get('contract_hash') == digest({k:v for k,v in contract.items() if k != 'contract_hash'}))


def selected_contracts(subject, scope):
    contracts = subject.get('implementation_contracts', {})
    key = scope_key(scope)
    if scope.get('item_id') or key in contracts:
        return [contracts.get(key)]
    items = subject.get('plan', {}).get('work_items', [])
    return [contracts.get('item:' + i['id']) for i in items] if items else [contracts.get(key)]


def implementation_prerequisites(subject, scope):
    scope = _scope(scope)
    question_scope = {'item_id': scope['item_id']} if scope.get('item_id') else {}
    blocked_ids = {q['id'] for q in clarification_blockers(subject, question_scope)}
    questions = [q for q in current_questions(subject, question_scope) if q['id'] in blocked_ids]
    reasons = ['BUSINESS_CLARIFICATION_REQUIRED'] if questions else []
    contracts = selected_contracts(subject, scope)
    if any(not contract_current(subject, c) for c in contracts):
        reasons.append('IMPLEMENTATION_CONTRACT_MISSING_OR_STALE')
    return {'status': 'block' if reasons else 'allow', 'reason_codes': reasons,
            'questions': deepcopy(questions), 'scope': scope, 'contract_binding': contract_binding(subject, scope)}


def _neighboring(contract):
    rows = contract.get('neighboring', [])
    if rows and all(isinstance(r, dict) and r.get('behavior') and r.get('reason')
                    and _refs(r.get('evidence_refs')) and _refs(r.get('target_ids')) for r in rows):
        return True
    disposition = contract.get('neighboring_disposition', {})
    return (disposition.get('applicability') == 'not-applicable' and disposition.get('reason')
            and _refs(disposition.get('evidence_refs')))


def review_prerequisites(subject, scope):
    result = implementation_prerequisites(subject, scope)
    result.update(missing_checks=[], not_configured=[])
    reasons = list(result['reason_codes'])
    contracts = selected_contracts(subject, _scope(scope))
    if any(c and not _neighboring(c) for c in contracts):
        reasons.append('NEIGHBORING_BEHAVIOR_UNASSESSED')
    items = [i for i in subject.get('plan', {}).get('work_items', []) if not scope.get('item_id') or i['id'] == scope['item_id']]
    if subject.get('review_contract_hash'):
        needs_test = bool(subject['review_contract']['request'].get('verification'))
        targets = [None] if needs_test else []
    else:
        targets = [i['id'] for i in items if i.get('kind') == 'code']
    for item_id in targets:
        attempts = subject.get('items', {}).get(item_id, {}).get('attempts', []) if item_id else []
        if not any(p.get('passed') is True and p.get('fresh') is not False and p.get('phase') == 'GREEN'
                   and p.get('source_identity') == subject.get('source_identity')
                   and (item_id is None or p.get('item_id') == item_id and attempts and p.get('token') == attempts[-1]['token'])
                   for p in subject.get('verification_proofs', {}).values()):
            result['missing_checks'].append('focused-test:' + str(item_id or 'session'))
    configured_kinds = set()
    for identifier, config in subject.get('hardening_config', {}).items():
        if config.get('pre_review') is not True:continue
        if scope.get('item_id') and config.get('item_ids') and scope['item_id'] not in config['item_ids']:continue
        configured_kinds.add(config.get('kind'))
        proof = subject.get('hardening_proofs', {}).get(identifier, {})
        if (proof.get('passed') is not True or proof.get('config_hash') != subject.get('hardening_config_hash')
                or proof.get('source_identity') != subject.get('source_identity')):
            result['missing_checks'].append(identifier)
    result['not_configured'] = [k for k in ('syntax','type','lint') if k not in configured_kinds]
    if result['missing_checks']:reasons.append('PRE_REVIEW_CHECKS_REQUIRED')
    result.update(status='block' if reasons else 'allow', reason_codes=reasons)
    if scope.get('diagnostic') is True:
        result.update(status='allow', diagnostic_only=True)
    return result


def record_fix_rationale(subject, record):
    bounded(record);require_review_policy(subject)
    need(subject.get('status') == 'active' and record.get('source_identity') == subject.get('source_identity'), 'Current active source required for fix rationale.')
    contract = subject.get('implementation_contracts', {}).get(scope_key(record.get('scope', {})))
    need(contract_current(subject, contract) and record.get('contract_hash') == contract['contract_hash'], 'Bind the current implementation contract.')
    gate_id=record.get('gate_id')
    finding = next((f for f in subject.get('unresolved_findings', []) if f.get('id') == record.get('finding_id')), None)
    gate_hash=gate_failure_binding(subject,gate_id,record.get('scope',{})) if gate_id else None
    need((gate_hash is not None and not record.get('finding_id') or finding is not None and not gate_id)
         and record.get('observed_failure') and _refs(record.get('evidence_refs'))
         and record.get('correction') and record.get('why'), 'Observed actual finding/check failure, evidence, correction and causal reason required.')
    target='gate:'+gate_id if gate_id else finding['id']
    valid_evidence = ({'gate:'+gate_id} if gate_id else {'finding:' + finding['id']}) | {'verification:' + k for k in subject.get('verification_proofs', {})}
    need(set(record['evidence_refs']).issubset(valid_evidence), 'Rationale evidence must resolve to recorded findings, configured checks or execution.')
    cause = record.get('cause', {})
    need(cause.get('kind') in {'hypothesis','confirmed'} and isinstance(cause.get('text'), str) and cause['text'].strip(), 'Label the supported cause or hypothesis.')
    from .finding_closure import finding_hash
    rationale = {**deepcopy(record), 'schema_version':1, **({'gate_failure_hash':gate_hash} if gate_id else {'finding_hash':finding_hash(finding)})}
    rationale['rationale_hash'] = digest(rationale)
    updated = deepcopy(subject)
    prior = updated.setdefault('fix_rationales', {}).get(target)
    if prior:updated.setdefault('fix_rationale_history', []).append(deepcopy(prior))
    updated['fix_rationales'][target] = rationale
    return updated


def rationale_current(subject, finding_id):
    rationale = subject.get('fix_rationales', {}).get(finding_id, {})
    contract = subject.get('implementation_contracts', {}).get(scope_key(rationale.get('scope', {})))
    finding = next((f for f in subject.get('unresolved_findings', []) if f.get('id') == finding_id), None)
    from .finding_closure import finding_hash
    gate_id=rationale.get('gate_id')
    target_current=(gate_id and finding_id=='gate:'+gate_id and rationale.get('gate_failure_hash')==gate_failure_binding(subject,gate_id,rationale.get('scope',{})) and rationale.get('gate_failure_hash') is not None) or (not gate_id and finding and rationale.get('finding_hash')==finding_hash(finding))
    return bool(rationale and target_current and rationale.get('source_identity') == subject.get('source_identity')
                and contract_current(subject, contract) and rationale.get('contract_hash') == contract['contract_hash']
                and rationale.get('rationale_hash') == digest({k:v for k,v in rationale.items() if k != 'rationale_hash'}))


def gate_item_ids(subject,gate_id):
    config=subject.get('hardening_config',{}).get(gate_id,{})
    ids=config.get('item_ids');known={i['id']:i for i in subject.get('plan',{}).get('work_items',[])}
    if (not isinstance(ids,list) or not ids or any(not isinstance(i,str) for i in ids)
            or len(ids)!=len(set(ids)) or any(i not in known or known[i].get('repo_id')!=config.get('repo_id') for i in ids)):return []
    return ids


def gate_failure_binding(subject,gate_id,scope):
    config=subject.get('hardening_config',{}).get(gate_id,{})
    proof=subject.get('hardening_proofs',{}).get(gate_id,{})
    item=next((i for i in subject.get('plan',{}).get('work_items',[]) if i['id']==scope.get('item_id')),None)
    if (gate_id not in subject.get('required_hardening_gates',[]) or config.get('pre_review') is not True
            or not item or item.get('repo_id')!=config.get('repo_id') or item['id'] not in gate_item_ids(subject,gate_id)
            or proof.get('passed') is not False or not proof.get('execution_id') or type(proof.get('exit_code')) is not int
            or proof.get('failure') not in {'GATE_FAILED','FINDINGS_PRESENT'}
            or proof.get('source_identity')!=subject.get('source_identity') or proof.get('config_hash')!=subject.get('hardening_config_hash')):return None
    return digest({'gate_id':gate_id,'config':config,'proof':proof})
