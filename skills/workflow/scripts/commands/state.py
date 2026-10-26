"""Explicit control maintenance; inspection is the default, never migration."""
import json
from pathlib import Path
from workflow_lib.store import WorkflowError

def register_commands(parser):
    group=parser.add_parser('state');commands=group.add_subparsers(dest='state_command',required=True)
    for name in ('compact','gc'):
        action=commands.add_parser(name);action.add_argument('--root',required=True)
        mode=action.add_mutually_exclusive_group();mode.add_argument('--dry-run',action='store_true');mode.add_argument('--apply',action='store_true')
        if name=='compact':mode.add_argument('--resume',action='store_true')
        action.add_argument('--plan-hash');action.add_argument('--operation-id');action.add_argument('--actor-id');action.add_argument('--details',action='store_true')
    pins=commands.add_parser('pins');pins.add_argument('--root',required=True);pins.add_argument('--reconcile',action='store_true')
    pins.add_argument('--operation-id');pins.add_argument('--actor-id');pins.add_argument('--details',action='store_true')
    verify=commands.add_parser('verify');verify.add_argument('--root',required=True);verify.add_argument('--full',action='store_true')
    for name in ('backup','policy'):
        action=commands.add_parser(name);action.add_argument('--root',required=True);action.add_argument('--operation-id');action.add_argument('--actor-id')
        action.add_argument('--output' if name=='backup' else '--file',required=True)

def _identity(parsed):
    if not parsed.operation_id_explicit or not parsed.actor_id:
        raise WorkflowError('MAINTENANCE_IDENTITY_REQUIRED','Explicit --operation-id and --actor-id are required for maintenance changes.')

def _summary(value,details=False):
    if details:return value
    hidden={'files','candidates','terminal_candidates','pins'}
    result={key:item for key,item in value.items() if key not in hidden}
    for key in hidden:
        if key in value:result[key+'_count']=len(value[key])
    if len(json.dumps(result).encode('utf-8'))>16384:
        for key in ('retained_unknown','blockers','deferred'):
            if key in result:
                result[key+'_count']=len(result[key]);result[key]=result[key][:10]
        result['details']='Request --details for all bound paths/reasons.'
    return result

def dispatch(parsed):
    from workflow_lib.storage_maintenance import (compaction_plan,apply_authorized_compaction,
        resume_compaction,verify_store,backup_control)
    from workflow_lib.storage_gc import gc_plan,apply_gc
    root=Path(parsed.root);action=parsed.state_command
    if action=='pins':
        from workflow_lib.storage_maintenance import _pins
        if not parsed.reconcile:return _summary({'pins':_pins(root),'authority':'OS ownership must be proven before reconciliation'},parsed.details)
        _identity(parsed)
        from workflow_lib.storage_audit import perform,paths,write_record
        from workflow_lib.storage_pins import reconcile
        def release(audit):
            audit['pin_inventory']=_pins(root);write_record(paths(root,parsed.operation_id)[1],audit)
            return reconcile(root)
        return perform(root,'pins-reconcile',{'scope':'all-stopped-owner-reservations'},parsed.operation_id,parsed.actor_id,release)
    if action=='verify':
        report=verify_store(root,full=parsed.full)
        if not report['valid']:raise WorkflowError(report.get('error_code','STORAGE_VERIFY_FAILED'),'Control verification failed.',{'verification':report})
        return report
    if action in {'compact','gc'}:
        if getattr(parsed,'resume',False):
            _identity(parsed)
            from workflow_lib.storage_audit import operation_reserved
            prior=operation_reserved(root,parsed.operation_id)
            from workflow_lib.storage_format import confined_path,INTENT_FILE
            from workflow_lib.storage_maintenance import _read_json,resume_initialization_audited
            intent_path=confined_path(root,INTENT_FILE)
            intent=_read_json(intent_path) if intent_path.exists() else {}
            if intent.get('kind')=='initialize' or prior and prior.get('kind')=='initialize-resume':
                identity=prior['request']['format'] if prior else intent['format']
                return resume_initialization_audited(root,identity,operation_id=parsed.operation_id,actor_id=parsed.actor_id)
            if not prior or prior.get('kind')!='compact':raise WorkflowError('MAINTENANCE_RECOVERY_REQUIRED','Resume using the original compact operation ID and actor.')
            return _summary(apply_authorized_compaction(root,prior['request']['plan_hash'],operation_id=parsed.operation_id,actor_id=parsed.actor_id),parsed.details)
        if not parsed.apply:
            if parsed.plan_hash:raise WorkflowError('INVALID_INPUT','A plan hash is used with --apply.')
            return _summary((compaction_plan if action=='compact' else gc_plan)(root),parsed.details)
        _identity(parsed)
        if not parsed.plan_hash:raise WorkflowError('MAINTENANCE_PLAN_REQUIRED','Inspect the dry-run and provide its exact --plan-hash.')
        apply=apply_authorized_compaction if action=='compact' else apply_gc
        return _summary(apply(root,parsed.plan_hash,operation_id=parsed.operation_id,actor_id=parsed.actor_id),parsed.details)
    _identity(parsed)
    if action=='backup':
        from workflow_lib.storage_audit import perform
        return perform(root,'backup',{'output':str(Path(parsed.output).resolve())},parsed.operation_id,parsed.actor_id,
            lambda audit:backup_control(root,Path(parsed.output)))
    from workflow_lib.storage_access import read_current,operation_lookup
    from workflow_lib.store import transact
    policy=json.loads(Path(parsed.file).read_text(encoding='utf-8'))
    event={'kind':'maintenance.policy.recorded','payload':{'maintenance_policy':policy,
        'maintenance_policy_authorization':{'actor_id':parsed.actor_id,'operation_id':parsed.operation_id}}}
    previous=operation_lookup(root,parsed.operation_id)
    if previous and (previous['kind']!=event['kind'] or previous['payload']!=event['payload']):raise WorkflowError('OPERATION_CONFLICT','Policy operation belongs to another request.')
    state=read_current(root,global_keys=())
    result=transact(root,state['version'],parsed.operation_id,event)
    if result['event']['kind']!=event['kind'] or result['event']['payload']!=event['payload']:
        raise WorkflowError('OPERATION_CONFLICT','A concurrent writer committed another policy request with this operation ID.')
    return {'policy':result['event']['payload']['maintenance_policy'],'event_sequence':result['event']['sequence'],'replayed':result['replayed']}
