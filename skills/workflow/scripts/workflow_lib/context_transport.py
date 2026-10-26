"""Ephemeral private scoped worker inputs, never approval or reusable authority."""
import json
from pathlib import Path
import re
from .storage_pins import reservation
from .document_units import canonical,digest
from .store import WorkflowError,_atomic_json

MAX_PREPARATION_BYTES=32*1024*1024


def _directory(root):
    root=Path(root).resolve();directory=root/'context-preparations'
    if directory.is_symlink():raise WorkflowError('CONTEXT_PREPARATION_INVALID','Preparation directory must not be a symlink.')
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    return directory


def _reference(root,ref):
    if (not isinstance(ref,dict) or set(ref)!={'schema_version','id','binding_hash'} or ref.get('schema_version')!=1
        or any(not isinstance(ref.get(k),str) or re.fullmatch('[0-9a-f]{64}',ref[k]) is None for k in ('id','binding_hash'))):
        raise WorkflowError('CONTEXT_PREPARATION_INVALID','Invalid scoped preparation reference.')
    return _directory(root)/(ref['id']+'.json')


@reservation('context-publication')
def store_preparation(root,prepared):
    from .context_preparation import _identity,PreparedContext
    if not isinstance(prepared,PreparedContext) or str(Path(root).resolve())!=prepared.root or prepared.binding_hash!=_identity(prepared.root,prepared.journal_version,prepared.scope,prepared.payload,prepared.source_bindings):
        raise WorkflowError('CONTEXT_PREPARATION_INVALID','Prepared authority or content does not match.')
    body={'schema_version':1,'root':prepared.root,'binding_hash':prepared.binding_hash,'payload':prepared.payload}
    if len(canonical(body))>MAX_PREPARATION_BYTES:raise WorkflowError('CONTEXT_PREPARATION_OVERFLOW','Scoped context input exceeds the safe artifact bound.')
    reference={'schema_version':1,'id':digest(body),'binding_hash':prepared.binding_hash};path=_reference(root,reference)
    if path.is_symlink():raise WorkflowError('CONTEXT_PREPARATION_INVALID','Preparation file is a symlink.')
    _atomic_json(path,body)
    return reference


@reservation('context-publication')
def load_preparation(root,reference,expected_binding):
    path=_reference(root,reference)
    try:
        if path.is_symlink():raise ValueError('symlink')
        with path.open('rb') as stream:raw=stream.read(MAX_PREPARATION_BYTES+1)
        if len(raw)>MAX_PREPARATION_BYTES:raise ValueError('oversize')
        body=json.loads(raw)
        if (digest(body)!=reference['id'] or body.get('root')!=str(Path(root).resolve())
            or body.get('binding_hash')!=expected_binding or reference['binding_hash']!=expected_binding):raise ValueError('binding mismatch')
        return body['payload']
    except (OSError,ValueError,KeyError,TypeError) as exc:raise WorkflowError('CONTEXT_PREPARATION_INVALID','Scoped worker input is missing, changed or outside its binding.') from exc


@reservation('context-publication')
def remove_preparation(root,reference):
    path=_reference(root,reference)
    # Unlink only this parent-owned name, never follow a replaced symlink.
    path.unlink(missing_ok=True)
