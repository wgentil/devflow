"""Offline task-routing comparisons and journal-derived outcome statistics."""
from copy import deepcopy
import math
from .document_units import digest
from .context_metrics import explicit_runtime_usage
from .store import WorkflowError

BINDING = ('host','host_version','model_id','model_revision','effort','execution_path','policy_hash')


def _finite(value):
    return type(value) in (int,float) and math.isfinite(value) and value >= 0


def _case(case):
    # Existing reviewed case snapshots bind expected.routing inside their
    # original content hash. No new approval command or executable runner.
    if isinstance(case.get('expected'),dict) and isinstance(case['expected'].get('routing'),dict):
        body={key:value for key,value in case.items() if key not in {'case_hash','case_id','feedback_id','approved_by'}}
        valid=case.get('case_hash')==digest(body)
        projected={**case['expected']['routing'], **{key:case.get(key) for key in ('case_id','case_hash','approved_by','scoring_version')}}
        return projected,valid
    return case,case.get('case_hash')==digest({key:value for key,value in case.items() if key!='case_hash'})


def evaluate_routing(cases: list[dict], results: list[dict], policy: dict) -> dict:
    if not isinstance(cases,list) or not isinstance(results,list) or any(not isinstance(row,dict) for row in cases+results):
        raise WorkflowError('ROUTING_EVALUATION_INVALID','Case and result objects required.')
    issues=[]
    rows={row.get('case_id'):row for row in results}
    if len(rows)!=len(results) or len({row.get('case_id') for row in cases})!=len(cases):issues.append('CASE_SET_INVALID')
    scored=[];observed=0
    for original in cases:
        case,valid_hash=_case(original)
        row=rows.get(case.get('case_id'))
        binding=case.get('binding') or {}
        valid_case=(valid_hash and isinstance(case.get('approved_by'),str) and bool(case['approved_by'])
            and type(case.get('scoring_version')) is int and case['scoring_version']>0
            and all(isinstance(binding.get(key),str) and binding[key] for key in BINDING)
            and binding.get('policy_hash')==digest(policy)
            and all(isinstance(case.get(key),list) and all(isinstance(v,str) for v in case[key])
                    for key in ('required_ids','required_facts')))
        if not valid_case:issues.append('CASE_EVIDENCE_INVALID')
        if row is not None:observed+=1
        row=row or {}
        missing_ids=sorted(set(case.get('required_ids',[]))-set(row.get('supplied_ids',[])))
        missing_facts=sorted(set(case.get('required_facts',[]))-set(row.get('supplied_facts',[])))
        matched=(valid_case and row.get('case_hash')==case.get('case_hash')
                 and all((row.get('binding') or {}).get(key)==binding.get(key) for key in BINDING))
        passed=bool(matched and row.get('passed') is True and not missing_ids and not missing_facts)
        if not matched:issues.append('RESULT_SCOPE_MISMATCH')
        measurements={key:row[key] if _finite(row.get(key)) else None
                      for key in ('duration_ms','context_bytes','retries','escalations')}
        scored.append({'case_id':case.get('case_id'),'case_hash':case.get('case_hash'),'passed':passed,
            'missing_ids':missing_ids,'missing_facts':missing_facts,'binding':deepcopy(binding),
            'findings':deepcopy(row.get('findings')) if isinstance(row.get('findings'),list) else None,
            'reported_usage':explicit_runtime_usage(row.get('usage')) or None, **measurements})
    if set(rows)-{row.get('case_id') for row in cases}:issues.append('UNREVIEWED_RESULT')
    body={'routing_evaluation_schema_version':1,'policy_hash':digest(policy),'status':'unavailable',
        'coverage':observed/len(cases) if cases else None,'cases':scored,'issues':sorted(set(issues)),
        'promotion_eligible':False,'cost_usd':None,
        'measurement_scope':'Supplied reviewed evaluation results; host attribution requires matching journal receipts. Byte/effort reductions are not savings.'}
    if cases:body['status']='passed' if not issues and all(row['passed'] for row in scored) else 'failed'
    return {**body,'report_hash':digest(body)}


def routing_statistics(data: dict, scope: dict) -> dict:
    seen=set();rows=[];runtime=[];known_bytes=[];unknown_usage=0
    for run_id,run in data.get('runs',{}).items():
        if scope.get('run_id') and scope['run_id']!=run_id:continue
        for identifier,record in run.get('native_invocations',{}).items():
            routing=record.get('decision',{}).get('routing')
            if not routing:continue
            if scope.get('stage') and scope['stage']!=record.get('scope',{}).get('stage'):continue
            if scope.get('task_id') and scope['task_id']!=routing.get('task_facts',{}).get('task_id'):continue
            if scope.get('invocation_id') and scope['invocation_id']!=identifier:continue
            operation=record.get('operation_id') or (run_id,identifier)
            if operation in seen:continue
            seen.add(operation)
            result=record.get('result',{})
            usage=explicit_runtime_usage(result.get('usage'))
            if not usage:unknown_usage+=1
            runtime.append(usage)
            measured=routing.get('known_payload') or result.get('known_payload') or {}
            if type(measured.get('known_payload_bytes')) is int:known_bytes.append(measured['known_payload_bytes'])
            rows.append({'run_id':run_id,'invocation_id':identifier,'operation_id':record.get('operation_id'),
                'status':record.get('status'),'worker_status':result.get('worker_outcome',{}).get('status'),
                'execution_path':routing.get('execution_path'),'escalation_index':routing.get('escalation_index',0),
                'retry_of':routing.get('retry_of'),'retry_count':record.get('retry_count',0)})
    return {'schema_version':1,'invocations':len(rows),'outcomes':rows,
        'escalations':sum(row['escalation_index']>0 and not row['retry_of'] for row in rows),'retries':sum(row['retry_count']>0 and (row['escalation_index']==0 or bool(row['retry_of'])) for row in rows),
        'runtime_usage':{key:sum(value.get(key,0) for value in runtime) for key in ('input_tokens','output_tokens','cached_tokens')
                         if any(key in value for value in runtime)},
        'runtime_usage_coverage':{key:sum(key in value for value in runtime)/len(rows) if rows else None
                                  for key in ('input_tokens','output_tokens','cached_tokens')},
        'usage_coverage':(len(rows)-unknown_usage)/len(rows) if rows else None,
        'known_context_bytes':sum(known_bytes),'context_measurement_coverage':len(known_bytes)/len(rows) if rows else None,
        'cost_usd':None,'cost_reason':'Use explicit attributed usage and sourced pricing through stats price; no inferred routing cost.',
        'latency_scope':'Operation durations may overlap; no summed wall-clock or savings inference.'}
