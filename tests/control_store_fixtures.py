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


def historical_run(root, run_id, actor_id=None):
    """Seed a pre-policy run for frozen lifecycle tests, never a live downgrade."""
    from workflow_lib.store import read_state, transact
    from workflow_lib.runs import start_run, run_summary
    state=read_state(root);data=state['data']
    run=start_run(data,run_id,data['plan'])
    run.pop('review_policy');run.pop('enforcement')
    if actor_id:run['actors']={'implementer':actor_id}
    transact(root,state['version'],'historical-fixture:'+run_id,{'kind':'fixture','payload':{
        'runs':{**data.get('runs',{}),run_id:run}}})
    return run_summary(run)
