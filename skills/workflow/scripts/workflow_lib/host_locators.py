"""Atomic, rebuildable project/session discovery cache; no ownership authority."""
import hashlib
import json
from pathlib import Path
from .store import WorkflowError, _atomic_json
from .hosts import HOSTS


def locator_path(project_dir: Path, host: str, session_id: str) -> Path:
    if host not in HOSTS or not isinstance(session_id,str) or not session_id:
        raise WorkflowError('INVALID_HOST', 'Supported host and actual session ID required.')
    return project_dir.resolve()/'.devflow/hosts'/host/(hashlib.sha256(session_id.encode()).hexdigest()+'.json')


def write_locator(project_dir: Path, host: str, session_id: str, control_root: Path, binding_id: str) -> None:
    path = locator_path(project_dir,host,session_id)
    path.parent.mkdir(parents=True,exist_ok=True)
    _atomic_json(path, {'control_root':str(control_root.resolve()),'binding_id':binding_id})


def read_locator(project_dir: Path, host: str, session_id: str) -> dict | None:
    path=locator_path(project_dir,host,session_id)
    if not path.exists(): return None
    try:
        if path.stat().st_size > 8192: raise ValueError('locator exceeds limit')
        value=json.loads(path.read_text())
        if set(value) != {'control_root','binding_id'} or not all(isinstance(x,str) and x for x in value.values()) or not Path(value['control_root']).is_absolute():
            raise ValueError('invalid locator fields')
        return value
    except (OSError,ValueError,TypeError) as exc:
        raise WorkflowError('LOCATOR_INVALID', 'Repair attachment locator from the journal; '+str(exc)) from exc
