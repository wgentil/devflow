"""Additive regression inputs, locked across baseline/correction and current intent."""
from copy import deepcopy
from .document_units import digest
from .clarifications import clarification_binding
from .review_policy import bounded,require_review_policy
from .store import WorkflowError


def need(ok,message):
    if not ok:raise WorkflowError('TEST_EXTENSION_BLOCKED',message)


def session_item(subject):
    verification=subject['review_contract']['request'].get('verification',{})
    return {'id':'session','kind':'code','repo_id':verification.get('repo_id'),
        'verification_inputs':verification.get('input_paths',[]),'verification_target_ids':verification.get('target_ids',[])}


def _binding(subject,item):
    if subject.get('review_contract_hash'):
        return {'item_id':'session','token':subject['review_contract_hash'],'item_contract_hash':digest(item),
            'clarification_binding':clarification_binding(subject,{}),'authority_hash':subject['review_contract_hash']}
    attempts=subject.get('items',{}).get(item['id'],{}).get('attempts',[])
    need(attempts,'An actual current item attempt is required.')
    return {'item_id':item['id'],'token':attempts[-1]['token'],'item_contract_hash':digest(item),
        'clarification_binding':clarification_binding(subject,{'item_id':item['id']}),
        'authority_hash':subject.get('review_contract_hash') or subject.get('plan',{}).get('spec_hash')}


def current_extension(subject,item):
    row=subject.get('test_extensions',{}).get(item['id'])
    if row is None:return None
    expected=_binding(subject,item)
    need(row.get('schema_version')==1 and all(row.get(k)==v for k,v in expected.items()) and
         row.get('extension_hash')==digest({k:v for k,v in row.items() if k!='extension_hash'}),
         'Renew the additive test contract for the actual current attempt, authority and question answers.')
    return row


def record_extension(subject,record):
    bounded(record);require_review_policy(subject)
    need(subject.get('status')=='active','Active subject required.')
    need(not any(row.get('status') not in {'completed','failed','reconciled'} for row in list(subject.get('effects',{}).values())+list(subject.get('active_executions',{}).values())+list(subject.get('executions',{}).values())), 'Reconcile active workers before changing the locked regression contract.')
    need(set(record)=={'item_id','token','item_contract_hash','clarification_binding','source_identity','input_bindings','target_ids','reason'},
        'Declare additive inputs/targets only; original plan/authority cannot be replaced.')
    item=(session_item(subject) if record['item_id']=='session' and subject.get('review_contract_hash') else next((i for i in subject.get('plan',{}).get('work_items',[]) if i['id']==record['item_id']),None))
    need(item and item.get('kind')=='code','Use an actual approved code item.')
    binding=_binding(subject,item)
    need(all(record.get(k)==v for k,v in binding.items() if k!='authority_hash') and record['source_identity']==subject.get('source_identity'),
         'Current item attempt, authority/answers and observed source required.')
    inputs=record['input_bindings'];targets=record['target_ids']
    from pathlib import Path
    need(isinstance(inputs,dict) and inputs and all(isinstance(name,str) and name and not Path(name).is_absolute()
         and '..' not in Path(name).parts and isinstance(value,dict) and value.get('sha256') for name,value in inputs.items()),'Actual repository-relative supplemental input bindings required.')
    need(not set(inputs)&set(item.get('verification_inputs',[])), 'Additional files cannot replace original locked inputs.')
    need(isinstance(targets,list) and all(isinstance(t,str) and t for t in targets) and len(targets)==len(set(targets))
         and not set(targets)&set(item.get('verification_target_ids',[])) and record.get('reason'),'Declare distinct added targets and their regression purpose.')
    previous=subject.get('test_extensions',{}).get(item['id'])
    if previous and previous.get('authority_hash')==binding['authority_hash']:
        need(set(previous['input_bindings']).issubset(inputs) and set(previous['target_ids']).issubset(targets)
             and all(inputs[name]==value for name,value in previous['input_bindings'].items()),
             'Previously locked additional tests/targets cannot be dropped or weakened; use an actual approved authority amendment when required.')
    row={**deepcopy(record),**binding,'schema_version':1};row['extension_hash']=digest(row)
    updated=deepcopy(subject)
    if previous and previous!=row:updated.setdefault('test_extension_history',[]).append(deepcopy(previous))
    updated.setdefault('test_extensions',{})[item['id']]=row
    return updated


def session_verification(subject):
    verification=deepcopy(subject['review_contract']['request'].get('verification',{}))
    extension=current_extension(subject,session_item(subject))
    if extension:
        verification['input_paths']=sorted(set(verification.get('input_paths',[]))|set(extension['input_bindings']))
        verification['target_ids']=sorted(set(verification.get('target_ids',[]))|set(extension['target_ids']))
    return verification


def guard_extension(subject,record):
    from pathlib import Path
    from .enforcement_live import assert_source_current,assert_protection_current
    from .test_inputs import capture_input_bindings
    assert_source_current(subject);assert_protection_current(subject)
    item=session_item(subject) if subject.get('review_contract_hash') else next((i for i in subject['plan']['work_items'] if i['id']==record.get('item_id')),None)
    need(item,'An actual selected verification scope is required.')
    repo=Path(subject['repositories'][item['repo_id']]['location'])
    need(capture_input_bindings(repo,list(record.get('input_bindings',{})))==record.get('input_bindings'),
         'Supplemental inputs must match the actual current repository files.')


def admit_extension(location,request,operation_id):
    from pathlib import Path
    from .review_driver import Subject
    from .test_inputs import capture_input_bindings
    adapter=Subject(location,request);_,subject=adapter.read();adapter.live(subject)
    need(not set(request)-{'session','run_id','item_id','input_paths','target_ids','reason'},'Only explicit additive test scope is accepted.')
    item=session_item(subject) if adapter.session else next((i for i in subject['plan']['work_items'] if i['id']==request.get('item_id')),None)
    need(item,'Select the actual workflow item or standalone verification contract.')
    repo=Path(subject['repositories'][item['repo_id']]['location'])
    binding=_binding(subject,item)
    record={k:v for k,v in binding.items() if k!='authority_hash'}
    record.update(source_identity=subject['source_identity'],input_bindings=capture_input_bindings(repo,request.get('input_paths',[])),
        target_ids=request.get('target_ids'),reason=request.get('reason'))
    record_extension(subject,record)
    return adapter.event('test-extension',record,operation_id)
