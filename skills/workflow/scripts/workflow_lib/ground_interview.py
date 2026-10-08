"""Validate the visible first-use decision inventory without inferring answers."""
import json
from pathlib import Path

from .bootstrap import discover_project
from .governing_docs import load_project_manifest, _path
from .store import WorkflowError

TOPICS = (
    'product-users', 'constraints', 'architecture', 'languages',
    'coding-standards', 'lint-format', 'data', 'database', 'api-layer',
    'ui-framework', 'design-system', 'accessibility-localization',
    'security-privacy', 'integrations', 'testing', 'performance-reliability',
    'deployment-release', 'operations', 'team-conventions',
)
INTERVIEW_PATH = 'docs/devflow-ground-interview.json'


def _invalid(message):
    raise WorkflowError('INVALID_GROUND_INTERVIEW', message)


def inspect_ground_interview(project_dir: Path) -> dict:
    project = discover_project(Path(project_dir))
    manifest_path = project / 'docs/devflow-context.json'
    if manifest_path.exists():
        manifest = load_project_manifest(project)
        declaration = manifest.get('ground_interview')
        if declaration is None:
            return {'required': False, 'ready': True, 'path': None,
                    'missing_topics': [], 'unresolved_material': []}
        if not isinstance(declaration, dict) or declaration.get('path') != INTERVIEW_PATH:
            _invalid('ground_interview must name the visible standard interview path')
    path = _path(project, INTERVIEW_PATH)
    if not path.is_file():
        return {'required': True, 'ready': False, 'path': INTERVIEW_PATH,
                'missing_topics': list(TOPICS), 'unresolved_material': []}
    try:
        interview = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise WorkflowError('INVALID_GROUND_INTERVIEW', 'interview file must be valid UTF-8 JSON') from exc
    if (not isinstance(interview, dict) or type(interview.get('schema_version')) is not int or interview.get('schema_version') != 1
            or not isinstance(interview.get('topics'), dict)):
        _invalid('interview requires schema_version 1 and topics object')
    topics = interview['topics']
    unknown = set(topics) - set(TOPICS)
    if unknown:
        _invalid('unknown interview topics: ' + ', '.join(sorted(unknown)))
    missing = [name for name in TOPICS if name not in topics]
    unresolved = []
    for name, record in topics.items():
        if not isinstance(record, dict) or type(record.get('material')) is not bool:
            _invalid(f'{name} requires a material boolean and status')
        status = record.get('status')
        if status in {'answered', 'established'}:
            if not isinstance(record.get('decision'), str) or not record['decision'].strip():
                _invalid(f'{name} requires a decision')
            if status == 'established' and (not isinstance(record.get('sources'), list)
                    or not record['sources'] or any(not isinstance(s, str) or not s.strip() for s in record['sources'])):
                _invalid(f'{name} requires source references')
        elif status in {'deferred', 'not-applicable'}:
            if not isinstance(record.get('reason'), str) or not record['reason'].strip():
                _invalid(f'{name} requires a reason')
            if status == 'not-applicable' and record['material']:
                _invalid(f'{name} cannot be material and not applicable')
            if status == 'deferred' and record['material']:
                unresolved.append(name)
        else:
            _invalid(f'{name} has unsupported status')
    return {'required': True, 'ready': not missing and not unresolved,
            'path': INTERVIEW_PATH, 'missing_topics': missing,
            'unresolved_material': sorted(unresolved)}


def require_ground_interview(project_dir: Path) -> dict:
    report = inspect_ground_interview(project_dir)
    if not report['ready']:
        code = 'GROUND_INTERVIEW_REQUIRED' if report['missing_topics'] == list(TOPICS) and not (discover_project(Path(project_dir)) / INTERVIEW_PATH).is_file() else 'GROUND_INTERVIEW_INCOMPLETE'
        raise WorkflowError(code, 'complete material ground interview decisions before planning or implementation', report)
    return report
