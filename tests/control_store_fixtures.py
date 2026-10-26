"""Owned storage roots; explicit legacy layout never depends on production test flags."""
from contextlib import contextmanager
from pathlib import Path
import tempfile


@contextmanager
def owned_control():
    with tempfile.TemporaryDirectory(prefix='devflow-storage-') as temporary:
        yield Path(temporary).resolve() / 'control é東京'


def legacy_root(root):
    (Path(root) / 'events').mkdir(parents=True, exist_ok=True)
    return Path(root)
