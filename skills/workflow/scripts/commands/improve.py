"""Opt-in workflow trace and reviewed case commands."""

import json
from pathlib import Path
from workflow_lib.storage_access import read_command, read_current, operation_lookup, read_history, read_entity

from .journal import add_journal_options, commit
from workflow_lib.store import WorkflowError


def register_commands(parser):
    group = parser.add_parser('improve')
    commands = group.add_subparsers(dest='improve_command', required=True)
    for name in ('trace-enable', 'feedback', 'case-approve', 'inspect', 'run-cases', 'compare', 'retrospective', 'model-evaluate'):
        action = commands.add_parser(name)
        add_journal_options(action)
        if name == 'trace-enable':
            action.add_argument('--run-id', required=True)
            action.add_argument('--actor-id', required=True)
        if name in {'feedback', 'case-approve', 'run-cases', 'compare', 'retrospective', 'model-evaluate'}:
            action.add_argument('--input', required=True)
        if name == 'run-cases': action.add_argument('--cwd', required=True)


def dispatch(parsed):
    if parsed.improve_command == 'trace-enable':
        return commit(parsed, 'domain.improve.trace-enable', {'run_id': parsed.run_id,
                                                               'actor_id': parsed.actor_id})
    if not parsed.root:
        raise WorkflowError('CONTROL_ROOT_REQUIRED', 'improvement requires --root')
    if parsed.improve_command in {'feedback','case-approve'}:
        request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
        return commit(parsed,'domain.improve.'+parsed.improve_command,request)
    data = read_command(Path(parsed.root), parsed, family='improve')['data']
    if parsed.improve_command == 'inspect':
        return {'feedback': data.get('improvement_feedback', {}),
                'approved_cases': data.get('improvement_cases', {})}
    request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
    if parsed.improve_command in {'feedback', 'case-approve'}:
        return commit(parsed, 'domain.improve.' + parsed.improve_command, request)
    if parsed.improve_command == 'run-cases':
        from workflow_lib.improvement_eval import run_candidate_cases
        return run_candidate_cases(request, list(data.get('improvement_cases', {}).values()),
                                   Path(parsed.cwd))
    if parsed.improve_command == 'compare':
        from workflow_lib.improvement_eval import compare_candidate
        return compare_candidate(request['baseline'], request['candidate'],
                                 list(data.get('improvement_cases', {}).values()))
    if parsed.improve_command == 'model-evaluate':
        from workflow_lib.model_validation import evaluate_model, promotion_decision, STAGES
        from workflow_lib.native_runtime import policy
        selected = set(request.get('case_ids', []))
        approved = data.get('improvement_cases', {})
        if selected - set(approved):
            raise WorkflowError('CASE_NOT_APPROVED', 'model evaluation requires approved case IDs')
        cases = [approved[identifier] for identifier in sorted(selected)
                 if approved[identifier].get('stage') in STAGES]
        report = evaluate_model(request['host'], request['model_id'], request['host_version'],
                                cases, request.get('results', []))
        decision = promotion_decision(report, {'version': policy()['version'],
            'thresholds': policy().get('validation_thresholds', {})})
        value = {'report': report, 'decision': decision, 'released': False}
        if request.get('routing_evaluation') is not None:
            from workflow_lib.routing_evaluation import evaluate_routing
            evaluation = request['routing_evaluation']
            identifiers = evaluation.get('case_ids', [])
            if not isinstance(identifiers,list) or any(identifier not in approved for identifier in identifiers):
                raise WorkflowError('CASE_NOT_APPROVED','Routing evaluation requires reviewed case IDs.')
            value['routing_report'] = evaluate_routing([approved[identifier] for identifier in identifiers],
                                                      evaluation.get('results', []), policy())
        return value
    from workflow_lib.improvement_eval import retrospective
    return retrospective(request['traces'], list(data.get('improvement_feedback', {}).values()))
