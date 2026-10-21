"""Completed-code reverification eligibility and fresh attempt issuance."""
from copy import deepcopy
from .store import WorkflowError


def validate_reverification(run: dict, item_id: str) -> None:
    def require(ok, code, message):
        if not ok: raise WorkflowError(code,message)
    require(run.get('status') == 'active','RUN_NOT_ACTIVE','Only active undelivered runs can be reverified.')
    require(not run.get('active_attempt'),'ATTEMPT_ACTIVE','Finish or abandon the active attempt first.')
    require(not any(row.get('status') == 'running' for row in run.get('native_invocations',{}).values()),
            'NATIVE_INVOCATION_ACTIVE','Stop or reconcile running workers before reverification.')
    require(not any(row.get('status') == 'claimed' for row in run.get('repair_cycles',[])),
            'REPAIR_LEASE_ACTIVE','Finish or reconcile the active repair first.')
    item=next((row for row in run.get('plan',{}).get('work_items',[]) if row['id'] == item_id),None)
    require(item is not None,'WORK_ITEM_NOT_FOUND','Known work item required.')
    require(item.get('kind') == 'code','REVERIFICATION_UNSUPPORTED','Reverification currently supports code items only.')
    require(run.get('items',{}).get(item_id,{}).get('status') == 'complete','ITEM_INELIGIBLE','Use next/retry for an incomplete item.')
    require(bool(run['items'][item_id].get('attempts')),'NO_PREVIOUS_ATTEMPT','Recorded completed attempt required.')
    require(all(run.get('items',{}).get(dep,{}).get('status') == 'complete' for dep in item.get('dependencies',[])),
            'ITEM_INELIGIBLE','Complete dependencies before reverification.')


def begin_reverification(run: dict, item_id: str) -> dict:
    from .runs import issue_attempt
    validate_reverification(run,item_id)
    updated=deepcopy(run)
    updated['items'][item_id]['status']='pending'
    invalidate_item_reviews(updated,item_id)
    updated=issue_attempt(updated,item_id)
    updated['active_attempt']['mode']='reverify'
    updated['items'][item_id]['attempts'][-1]['mode']='reverify'
    return updated


def invalidate_item_reviews(run: dict, item_id: str) -> None:
    """Retain evidence history but require new affected review/acceptance."""
    for role, records in run.get('reviews',{}).items():
        for row in records:
            if role in {'branch','acceptance'} or role == 'item' and row.get('item_id') == item_id:
                row['fresh']=False
    for row in run.get('acceptances',[]): row['fresh']=False
