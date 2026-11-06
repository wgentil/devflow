"""Exclusive, durable tool execution identities; model attempts are not tool runs."""
from contextvars import ContextVar
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import os,uuid
from .store import WorkflowError,transact
from .storage_access import read_current,operation_lookup
from .document_units import digest
from .action_policy import require_action,subject_decision

CURRENT_TOOL=ContextVar('devflow_current_tool',default=None)


def reduce_tool(subject,action,record):
    updated=deepcopy(subject);scope=record['item_id'];active=subject.get('active_attempt')
    if action=='tool-claim':
        action_scope=record.get('action_scope',{'item_id':scope})
        require_action(subject_decision(subject,'proof',action_scope))
        if record.get('kind')=='hardening':
            gate=subject.get('hardening_config',{}).get(record.get('gate_id'))
            from .implementation_contracts import contract_binding
            valid=(gate and scope=='gate:'+record['gate_id'] and record.get('config_hash')==subject.get('hardening_config_hash')
                   and action_scope=={} and record.get('contract_binding')==contract_binding(subject,{'role':'branch'}))
        else:
            valid=active and active['token']==record.get('token') and active['item_id']==scope
        if not isinstance(record.get('id'),str) or not record['id'] or not valid or subject.get('active_executions',{}).get(scope):
            raise WorkflowError('TOOL_EXECUTION_ACTIVE','Known current attempt/configured gate and no active/uncertain tool execution required.')
        from .protection_receipts import validate_receipts
        validate_receipts(subject,record.get('protection_receipts'))
        observation=record.get('source_observation',{})
        if observation.get('source_identity')!=digest(observation.get('snapshots',{})) or type(record.get('owner_pid')) is not int:
            raise WorkflowError('INVALID_TOOL_EXECUTION','Bound coordinator and source required.')
        if record.get('authorization_id'):
            authorization=updated.get('authorizations',{}).get(record['authorization_id'],{})
            if authorization.get('execution_id'):raise WorkflowError('AUTHORIZATION_USED','Infrastructure authorization already reserved; inspect/reconcile rather than repeat apply.')
            authorization['execution_id']=record['id']
        updated.setdefault('active_executions',{})[scope]={**deepcopy(record),'status':'launching'}
    elif action=='tool-reconcile':
        claimed=updated.get('active_executions',{}).get(scope,{})
        from .enforcement_recovery import validate_tool_observation
        validate_tool_observation(claimed,record.get('observation',{}))
        updated.setdefault('worker_termination_observations',{})[record['id']]=deepcopy(record['observation'])
        del updated['active_executions'][scope]
    elif action=='tool-finish':
        claimed=updated.get('active_executions',{}).get(scope,{})
        if claimed.get('id')!=record.get('id'):raise WorkflowError('TOOL_EXECUTION_ACTIVE','Finish must bind this active execution.')
        result=record.get('result',{})
        if record.get('started') is True and record.get('ended') is True and result.get('phase')=='GREEN' and result.get('passed') is False and result.get('integrity'):
            updated.setdefault('verification_failures',{})[record['id']]={'id':record['id'],'item_id':scope,'token':claimed.get('token'),
                'source_identity':claimed['source_observation']['source_identity'],'result':deepcopy(result)}
        if record.get('uncertain'):
            updated['active_executions'][scope]['status']='uncertain'
        else:del updated['active_executions'][scope]
    return updated


def before_command():
    context=CURRENT_TOOL.get()
    if context:
        state=read_current(context['root'],run_id=context['run_id']);current=state['data']['runs'][context['run_id']]
        from .enforcement_live import assert_registered_repositories
        assert_registered_repositories(current,state['data'])
        proof_context(current)


def started():
    context=CURRENT_TOOL.get()
    if context:context.update(started=True,ended=False)


def ended():
    context=CURRENT_TOOL.get()
    if context:context['ended']=True


def cached(root,run_id,operation_id,client_hash):
    if not operation_id:return None
    prior=operation_lookup(Path(root),operation_id+':tool-finish')
    if not prior:return None
    record=prior['payload']['request']['record']
    if prior['kind']!='domain.enforcement.tool-finish' or record.get('client_hash')!=client_hash:
        raise WorkflowError('OPERATION_CONFLICT','Execution operation belongs to another request.')
    if record.get('uncertain'):raise WorkflowError('TOOL_EXECUTION_ACTIVE','Inspect/reconcile the uncertain tool; do not relaunch.')
    if record.get('proof_id'):
        proof=read_current(Path(root),run_id=run_id)['data']['runs'][run_id]['verification_proofs'][record['proof_id']]
        return {**proof,'replayed':True}
    return {'passed':False,'failure':record.get('failure','TOOL_FAILED'),'replayed':True}


@contextmanager
def execution(root,run_id,token,operation_id=None,client_hash=None,authorization_id=None,*,gate_id=None,expected_version=None):
    from .enforcement_live import source_observation,assert_protection_current
    from .clarifications import clarification_binding
    root=Path(root);state=read_current(root,run_id=run_id);run=state['data']['runs'][run_id]
    from .enforcement_live import assert_registered_repositories
    assert_registered_repositories(run,state['data'])
    active=run.get('active_attempt')
    if gate_id is None and (not active or active['token']!=token):raise WorkflowError('ATTEMPT_TOKEN_INVALID','Current tool attempt required.')
    identifier=operation_id or 'tool:'+uuid.uuid4().hex
    action_scope={} if gate_id else {'item_id':active['item_id']}
    gate_context={}
    if gate_id:
        from .implementation_contracts import contract_binding
        gate_context={'kind':'hardening','gate_id':gate_id,'config_hash':run.get('hardening_config_hash'),
                      'contract_binding':contract_binding(run,{'role':'branch'})}
    context={'id':identifier,'item_id':'gate:'+gate_id if gate_id else active['item_id'],
        'token':identifier if gate_id else token,'owner_pid':os.getpid(),'status':'launching','action_scope':action_scope,
        'source_observation':source_observation(run),'protection_receipts':assert_protection_current(run),
        'clarification_binding':clarification_binding(run,action_scope),'client_hash':client_hash,**gate_context,
        **({'authorization_id':authorization_id} if authorization_id else {})}
    claimed=transact(root,state['version'] if expected_version is None else expected_version,identifier+':tool-claim',{'kind':'domain.enforcement.tool-claim','payload':{'request':{'run_id':run_id,'record':context}}})
    if claimed['replayed']:raise WorkflowError('TOOL_EXECUTION_ACTIVE','An existing claim is historical evidence, not permission to relaunch; inspect/reconcile it.')
    holder={**context,'claim_version':claimed['state']['version'],'root':root,'run_id':run_id,'started':False,'ended':False,'result':{}}
    marker=CURRENT_TOOL.set(holder)
    try:yield holder
    finally:
        CURRENT_TOOL.reset(marker)
        current=read_current(root,run_id=run_id)
        result=holder['result']
        record={'id':identifier,'item_id':context['item_id'],'client_hash':client_hash,
            'uncertain':holder['started'] and not holder['ended'],'started':holder['started'],'ended':holder['ended'],
            **({'result':deepcopy(result)} if result else {})}
        if result.get('passed') and result.get('id'):record['proof_id']=result['id']
        elif not result.get('passed'):record['failure']=result.get('failure','TOOL_FAILED')
        transact(root,current['version'],identifier+':tool-finish',{'kind':'domain.enforcement.tool-finish','payload':{'request':{'run_id':run_id,'record':record}}})


def proof_context(run):
    context=CURRENT_TOOL.get()
    from .enforcement_live import source_observation,assert_protection_current
    from .clarifications import clarification_binding
    if (not context or context['source_observation']!=source_observation(run)
            or context['protection_receipts']!=assert_protection_current(run)
            or context['clarification_binding']!=clarification_binding(run,context.get('action_scope',{'item_id':context['item_id']}))):
        raise WorkflowError('VERIFICATION_STALE','Execution source, user decisions or protected context changed.')
    require_action(subject_decision(run,'proof',context.get('action_scope',{'item_id':context['item_id']})))
    if context.get('kind')=='hardening':
        from .implementation_contracts import contract_binding
        if context['config_hash']!=run.get('hardening_config_hash') or context['contract_binding']!=contract_binding(run,{'role':'branch'}):
            raise WorkflowError('VERIFICATION_STALE','Configured check or implementation contract changed before execution.')
    return {'execution_id':context['id'],'source_observation':context['source_observation'],
        'source_identity':context['source_observation']['source_identity'],'protection_receipts':context['protection_receipts'],
        'clarification_binding':context['clarification_binding']}


def validate_execution(subject,proof):
    claimed=subject.get('active_executions',{}).get(proof.get('item_id'),{})
    if (claimed.get('id')!=proof.get('execution_id') or claimed.get('token')!=proof.get('token')
            or claimed.get('source_observation')!=proof.get('source_observation')
            or claimed.get('protection_receipts')!=proof.get('protection_receipts')):
        raise WorkflowError('TOOL_EXECUTION_REQUIRED','Recorded matching execution/source/protection claim required.')
