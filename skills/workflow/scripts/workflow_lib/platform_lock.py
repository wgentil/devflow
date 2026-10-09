"""Cross-process exclusive locks on persistent one-byte lock files."""
from contextlib import contextmanager
import os
import time


@contextmanager
def exclusive_file(handle, *, blocking: bool = True):
    """Hold an exclusive lock until the context exits.

    A nonblocking contention raises BlockingIOError on every platform.
    """
    if os.name == 'nt':
        import msvcrt
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'\0' if 'b' in handle.mode else '\0')
            handle.flush()
        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                contended = getattr(exc, 'winerror', None) in (33, 36) or exc.errno in (13, 36)
                if not contended:
                    raise
                if not blocking:
                    raise BlockingIOError('lock is held by another process') from exc
                time.sleep(0.05)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def sync_directory(path):
    """Persist a completed rename where the platform exposes directory fsync."""
    if os.name == 'nt':
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
