"""Durable root-coordinated reservations, reclaimed only by OS ownership proof."""
from contextlib import nullcontext
from functools import wraps
import json
import os
from pathlib import Path
from uuid import uuid4
from .platform_lock import exclusive_file,sync_directory
from .storage_format import confined_path,detect_layout
from .store import _exclusive,WorkflowError

class Pin:
    def __init__(self,root,kind):
        self.root=Path(root).resolve();self.handle=None;self.lease=None;self.path=None
        if detect_layout(self.root)['layout'] not in {'v2','legacy'}:return
        with _exclusive(self.root):
            layout=detect_layout(self.root)
            self.path=confined_path(self.root,'pins/'+uuid4().hex+'.json',create_parents=True)
            self.handle=self.path.open('x+b');os.chmod(self.path,0o600)
            self.lease=exclusive_file(self.handle);self.lease.__enter__()
            body={'pin_version':1,'id':self.path.stem,'kind':kind,'pid':os.getpid(),
                'root_id':layout.get('root_id'),'layout_id':layout.get('layout_id')}
            self.handle.write(json.dumps(body,sort_keys=True).encode('utf-8'));self.handle.flush();os.fsync(self.handle.fileno());sync_directory(self.path.parent)
    def close(self):
        if self.handle is None:return
        with _exclusive(self.root):
            self.lease.__exit__(None,None,None);self.handle.close();self.handle=None
            self.path.unlink(missing_ok=True);sync_directory(self.path.parent)
    def __enter__(self):return self
    def __exit__(self,*exc):self.close()
    def __del__(self):
        try:self.close()
        except Exception:pass # A retained descriptor remains a conservative blocker.

def reserve(root,kind):return Pin(root,kind)

def reconcile(root):
    """Explicit stopped-owner reconciliation; age and PID alone never suffice."""
    root=Path(root).resolve();released=0
    with _exclusive(root):
        directory=confined_path(root,'pins')
        files=list(directory.iterdir()) if directory.exists() else []
        # Prove ALL owners stopped before changing any descriptor.
        from contextlib import ExitStack
        with ExitStack() as stack:
            for path in files:
                confined_path(root,path.relative_to(root).as_posix())
                try:
                    handle=stack.enter_context(path.open('r+b'));stack.enter_context(exclusive_file(handle,blocking=False))
                except BlockingIOError as exc:raise WorkflowError('PIN_OWNER_ACTIVE','A reservation still has a live OS owner; stop/reconcile the worker first.') from exc
                try:body=json.loads(handle.read(65537))
                except (ValueError,OSError) as exc:raise WorkflowError('INVALID_STORAGE_PIN','Malformed reservation; preserve it for explicit recovery.') from exc
                if body.get('pin_version')!=1 or body.get('id')!=path.stem:raise WorkflowError('INVALID_STORAGE_PIN','Unsupported reservation identity.')
        for path in files:path.unlink();released+=1
        if directory.exists():sync_directory(directory)
    return {'released':released,'basis':'exclusive OS ownership; no age expiry'}

def reservation(kind):
    def decorate(function):
        @wraps(function)
        def wrapped(root,*args,**kwargs):
            with reserve(root,kind):return function(root,*args,**kwargs)
        return wrapped
    return decorate
