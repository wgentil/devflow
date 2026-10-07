"""Opt-in workflow trace and reviewed case commands."""

import json
from pathlib import Path

from .journal import add_journal_options, commit
from workflow_lib.store import read_state, WorkflowError


def register_commands(parser):
    group = parser.add_parser('improve')
    commands = group.add_subparsers(dest='improve_command', required=True)
    for name in ('trace-enable', 'feedback', 'case-approve', 'inspect', 'run-cases', 'compare', 'retrospective'):
        action = commands.add_parser(name)
        add_journal_options(action)
        if name == 'trace-enable':
            action.add_argument('--run-id', required=True)
            action.add_argument('--actor-id', required=True)
        if name in {'feedback', 'case-approve', 'run-cases', 'compare', 'retrospective'}:
            action.add_argument('--input', required=True)
        if name == 'run-cases': action.add_argument('--cwd', required=True)


def dispatch(parsed):
    if parsed.improve_command == 'trace-enable':
        return commit(parsed, 'domain.improve.trace-enable', {'run_id': parsed.run_id,
                                                               'actor_id': parsed.actor_id})
    if not parsed.root:
        raise WorkflowError('CONTROL_ROOT_REQUIRED', 'improvement requires --root')
    data = read_state(Path(parsed.root))['data']
    if parsed.improve_command == 'inspect':
        return {'feedback': data.get('improvement_feedback', {}),
                'approved_cases': data.get('improvement_cases', {})}
    request = json.loads(Path(parsed.input).read_text())
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
    from workflow_lib.improvement_eval import retrospective
    return retrospective(request['traces'], list(data.get('improvement_feedback', {}).values()))
