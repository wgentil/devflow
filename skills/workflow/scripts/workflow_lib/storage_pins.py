"""Durable root-coordinated reservations, reclaimed only by OS ownership proof."""
from contextlib import contextmanager
from functools import wraps
import json
import os
import re
from pathlib import Path
from uuid import uuid4
from .platform_lock import exclusive_file,sync_directory
from .storage_format import confined_path,detect_layout
from .store import _exclusive,WorkflowError

MAX_PIN_BYTES=65536
# Windows byte locks are mandatory. Keep the lease beyond all bounded metadata
# reads (including the 1MiB hash/copy buffer), without extending the data file.
PIN_LOCK_OFFSET=1 << 30

@contextmanager
def _lease(handle,*,blocking=True,legacy_probe=False):
    if os.name=='nt' and legacy_probe:
        # An earlier candidate locked byte zero; prove that ownership too.
        with exclusive_file(handle,blocking=blocking,offset=0,initialize=False):
            with exclusive_file(handle,blocking=blocking,offset=PIN_LOCK_OFFSET):yield
    else:
        with exclusive_file(handle,blocking=blocking,offset=PIN_LOCK_OFFSET):yield

class Pin:
    def __init__(self,root,kind):
        if not isinstance(kind,str) or not kind or len(kind)>2048:
            raise WorkflowError('INVALID_STORAGE_PIN','Reservation kind must be nonempty bounded metadata.')
        self.root=Path(root).resolve();self.handle=None;self.lease=None;self.path=None;self.owner_pid=os.getpid()
        if detect_layout(self.root)['layout'] not in {'v2','legacy'}:return
        with _exclusive(self.root):
            layout=detect_layout(self.root)
            identifier=uuid4().hex
            body={'pin_version':2,'id':identifier,'kind':kind,'pid':os.getpid(),
                'root_id':layout.get('root_id'),'layout_id':layout.get('layout_id')}
            raw=json.dumps(body,sort_keys=True).encode('utf-8')
            if len(raw)>MAX_PIN_BYTES:raise WorkflowError('INVALID_STORAGE_PIN','Reservation metadata exceeds its read budget.')
            self.path=confined_path(self.root,'pins/'+identifier+'.json',create_parents=True)
            self.handle=self.path.open('x+b');os.chmod(self.path,0o600)
            self.lease=_lease(self.handle);self.lease.__enter__()
            self.handle.seek(0);self.handle.write(raw);self.handle.flush();os.fsync(self.handle.fileno());sync_directory(self.path.parent)
    def close(self):
        if self.handle is None:return
        if os.getpid()!=self.owner_pid:
            self.handle.close();self.handle=None;self.lease=None
            return
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
        layout=detect_layout(root)
        # Prove ALL owners stopped before changing any descriptor.
        from contextlib import ExitStack
        with ExitStack() as stack:
            for path in files:
                confined_path(root,path.relative_to(root).as_posix())
                try:
                    handle=stack.enter_context(path.open('r+b'));stack.enter_context(_lease(handle,blocking=False,legacy_probe=True))
                except BlockingIOError as exc:raise WorkflowError('PIN_OWNER_ACTIVE','A reservation still has a live OS owner; stop/reconcile the worker first.') from exc
                try:
                    handle.seek(0);raw=handle.read(MAX_PIN_BYTES+1)
                    if len(raw)>MAX_PIN_BYTES:raise ValueError('oversized reservation')
                    body=json.loads(raw)
                except (ValueError,OSError) as exc:raise WorkflowError('INVALID_STORAGE_PIN','Malformed reservation; preserve it for explicit recovery.') from exc
                if (type(body.get('pin_version')) is not int or body['pin_version'] not in {1,2}
                        or body.get('id')!=path.stem or not re.fullmatch('[0-9a-f]{32}',path.stem)
                        or any(body.get(key)!=layout.get(key) for key in ('root_id','layout_id'))
                        or type(body.get('pid')) is not int or body['pid']<=0
                        or not isinstance(body.get('kind'),str) or not body['kind']):
                    raise WorkflowError('INVALID_STORAGE_PIN','Reservation identity differs from this root; preserve it for explicit recovery.')
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
