"""Scoped locale simulation; explicit encodings and binary data stay untouched."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


@contextmanager
def legacy_path_defaults(codec='cp1252', *, newline=None):
    read, write = Path.read_text, Path.write_text
    def read_text(path, encoding=None, errors=None, **kwargs):
        return read(path, encoding=encoding or codec, errors=errors, **kwargs)
    def write_text(path, data, encoding=None, errors=None, **kwargs):
        if newline is not None:
            kwargs.setdefault('newline', newline)
        return write(path, data, encoding=encoding or codec, errors=errors, **kwargs)
    with patch.object(Path, 'read_text', read_text), patch.object(Path, 'write_text', write_text):
        yield


@contextmanager
def legacy_subprocess_defaults(codec='cp1252'):
    import subprocess
    original = subprocess.run
    def run(*args, **kwargs):
        if (kwargs.get('text') or kwargs.get('universal_newlines')) and kwargs.get('encoding') is None:
            kwargs['encoding'] = codec
        return original(*args, **kwargs)
    with patch.object(subprocess, 'run', run):
        yield
