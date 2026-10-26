"""Explicit workflow initialization; never writes to an installed bundle."""
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from .store import WorkflowError
from .storage_access import read_current
from .platform_lock import exclusive_file


def compatible_runtime(candidates=None) -> str:
    candidates = [sys.executable, shutil.which('python3'), shutil.which('python')] if candidates is None else candidates
    for candidate in dict.fromkeys(candidates):
        if not candidate: continue
        try:
            check = subprocess.run([candidate, '-c', 'import sys; sys.exit(sys.version_info < (3,11))'],
                                   capture_output=True, timeout=5)
            if check.returncode == 0: return candidate
        except (OSError, subprocess.TimeoutExpired): pass
    raise WorkflowError('RUNTIME_UNAVAILABLE', 'DevFlow requires an existing Python 3.11+ runtime; this package does not provision an interpreter.')


def discover_project(project_dir: Path) -> Path:
    location = project_dir.expanduser().resolve()
    result = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=location, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise WorkflowError('PROJECT_REQUIRED', 'Open a Git project and invoke workflow there; Git is not initialized automatically.')
    root = Path(result.stdout.strip()).resolve()
    if not location.is_relative_to(root):
        raise WorkflowError('PROJECT_MISMATCH', 'Working directory is outside the discovered repository.')
    return root


def exclude_runtime(project: Path) -> None:
    result = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'],
                            cwd=project, capture_output=True, text=True, check=True, encoding='utf-8')
    path = Path(result.stdout.strip())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+', encoding='utf-8') as file:
        with exclusive_file(file):
            file.seek(0); body = file.read()
            if '/.devflow/' not in body.splitlines():
                file.seek(0, 2)
                file.write(('\n' if body and not body.endswith('\n') else '') + '/.devflow/\n')
                file.flush()


def initialize_project(project_dir: Path, control_root: Path | None, operation_id: str, expected_version: int | None) -> dict:
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise WorkflowError('OPERATION_ID_REQUIRED', 'Initialization requires an explicit operation ID.')
    project = discover_project(project_dir)
    root = control_root.expanduser().resolve() if control_root else project / '.devflow/control'
    from .releases import PACKAGE_ROOT
    if root.is_relative_to(PACKAGE_ROOT):
        raise WorkflowError('INSTALLED_ROOT_READ_ONLY', 'Control state must be outside the installed package.')
    exclude_runtime(project)
    state = read_current(root,operations=(operation_id,))
    prior = [key for key, repo in state['data'].get('repositories', {}).items()
             if Path(repo['location']).resolve() == project]
    if not prior and root == project/'.devflow/control' and state['data'].get('repositories'):
        raise WorkflowError('PROJECT_RELOCATION_REQUIRED','Existing project records require explicit repository relocation; no duplicate identity was created.')
    if len(prior) > 1: raise WorkflowError('AMBIGUOUS_PROJECT', 'Several repository identities refer to this project.')
    identifier = prior[0] if prior else 'repo-' + hashlib.sha256(str(project).encode()).hexdigest()[:24]
    from argparse import Namespace
    from commands.journal import commit
    request = {'repo_id': identifier, 'location': str(project)}
    receipt = commit(Namespace(root=str(root), operation_id=operation_id, operation_id_explicit=True,
                     expected_version=expected_version), 'domain.host.init', request) if not prior or operation_id in state['operations'] else {'state_version':state['version'], 'unchanged':True}
    runs = [key for key, run in read_current(root,active_runs=True)['data'].get('runs', {}).items()
            if run.get('status') not in {'delivered','discarded'} and identifier in run.get('repositories', {})]
    from .project_setup import inspect_project_setup
    setup = inspect_project_setup(project)
    return {**receipt, 'document_setup':setup, 'project_dir':str(project), 'control_root':str(root), 'repo_id':identifier,
            'resumable_runs':runs, 'selection_required':len(runs)>1}
