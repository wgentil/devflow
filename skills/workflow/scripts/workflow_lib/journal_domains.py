"""Deterministic, validated journal reducers for auxiliary workflow records.

Reducers use committed state only. No filesystem reads, subprocesses, clocks or
connector calls happen during materialization, so journal recovery is reproducible.
"""
from copy import deepcopy
from datetime import datetime
import hashlib
import json

from .gate_reports import normalize_contract
from .store import WorkflowError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise WorkflowError('INVALID_EVENT', message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def current_snapshot(data, fingerprint):
    require(fingerprint == data.get('snapshot_hash'), 'snapshot revision is stale')
    snapshot = data.get('snapshots', {}).get(fingerprint)
    require(isinstance(snapshot, dict), 'snapshot is unavailable')
    from .issues import validate_snapshot
    require(validate_snapshot(snapshot)['valid'], 'complete snapshot required')
    for issue in snapshot['issues']:
        stored = data.get('issues', {}).get(issue['id'])
        require(stored and stored['fingerprint'] == digest(issue), 'issue changed since snapshot')
    return snapshot


def reduce_event(data, kind, payload, version):
    require(isinstance(payload, dict) and set(payload) == {'request'}, 'domain event requires a request')
    request = payload['request']
    require(isinstance(request, dict), 'request must be an object')
    require('state' not in request, 'caller-supplied state is forbidden')
    try:
        json.dumps(request, allow_nan=False)
        return _reduce(data, kind, request, version)
    except WorkflowError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise WorkflowError('INVALID_EVENT', str(exc)) from exc


def _reduce(data, kind, req, version):
    if kind == 'domain.improve.trace-enable':
        run = data.get('runs', {}).get(req.get('run_id'))
        require(run is not None and text(req.get('actor_id')), 'known run and opt-in actor required')
        require(not run.get('improvement_trace_enabled'), 'trace is already enabled')
        run['improvement_trace_enabled'] = True
        run['improvement_trace_actor'] = req['actor_id']
        return {'run_id': req['run_id'], 'trace_enabled': True}
    if kind == 'domain.improve.feedback':
        from .improvement_traces import project_run_trace
        from .improvement_cases import propose_case
        require(text(req.get('actor_id')), 'feedback reviewer actor required')
        trace = project_run_trace(data, req.get('run_id'), True)
        require(req.get('trace_hash') == digest(trace), 'feedback trace has changed')
        candidate = propose_case(trace, req.get('feedback'))
        feedback_id = digest({'trace_hash': req['trace_hash'], 'actor_id': req['actor_id'],
                              'feedback': req['feedback']})
        record = {'feedback_id': feedback_id, 'run_id': req['run_id'],
                  'trace_hash': req['trace_hash'], 'actor_id': req['actor_id'],
                  'feedback': deepcopy(req['feedback']), 'candidate': candidate}
        prior = data.setdefault('improvement_feedback', {}).get(feedback_id)
        require(prior is None or prior == record, 'feedback identity conflict')
        data['improvement_feedback'][feedback_id] = record
        return {'feedback_id': feedback_id, 'candidate': candidate}
    if kind == 'domain.improve.case-approve':
        record = data.get('improvement_feedback', {}).get(req.get('feedback_id'))
        require(record is not None and req.get('approved') is True and text(req.get('actor_id')),
                'recorded feedback and human approval required')
        candidate = record['candidate']
        require(req.get('case_hash') == candidate['case_hash'], 'case hash changed')
        require(req['actor_id'] != record['actor_id'], 'case approval needs a distinct reviewer')
        approved = {**deepcopy(candidate), 'feedback_id': record['feedback_id'],
                    'approved_by': req['actor_id']}
        cases = data.setdefault('improvement_cases', {})
        require(candidate['case_id'] not in cases, 'case already approved')
        cases[candidate['case_id']] = approved
        return {'case_id': candidate['case_id'], 'case_hash': candidate['case_hash']}
    if kind.startswith('domain.repair.'):
        from .repair import failure_delta, repair_decision
        run = data.get('runs', {}).get(req.get('run_id'))
        require(run is not None and run.get('status') == 'active', 'active repair run required')
        action = kind.removeprefix('domain.repair.')
        cycles = run.setdefault('repair_cycles', [])
        if action == 'configure':
            policy = req.get('policy')
            require(isinstance(policy, dict) and set(policy) == {'enabled', 'max_attempts',
                    'max_elapsed_ms', 'max_estimated_cost', 'no_progress_window'}, 'complete repair policy required')
            import math
            require(type(policy['enabled']) is bool and type(policy['max_attempts']) is int
                    and policy['max_attempts'] > 0 and type(policy['max_elapsed_ms']) is int
                    and policy['max_elapsed_ms'] > 0 and type(policy['no_progress_window']) is int
                    and policy['no_progress_window'] >= 2 and type(policy['max_estimated_cost']) in (int, float)
                    and math.isfinite(policy['max_estimated_cost'])
                    and policy['max_estimated_cost'] >= 0, 'invalid repair limits')
            require(not cycles, 'repair policy is frozen after first claim')
            run['repair_policy'] = deepcopy(policy)
            return {'run_id': req['run_id'], 'policy': deepcopy(policy)}
        if action == 'claim':
            require(text(req.get('cycle_id')) and isinstance(req.get('delta_hash'), str), 'repair cycle identity required')
            require(type(req.get('claimed_at_ms')) is int and req['claimed_at_ms'] >= 0, 'claim time required')
            cost = req.get('estimated_cost')
            require(type(cost) in (int, float) and cost >= 0, 'known nonnegative estimated cost required')
            require(not any(row['cycle_id'] == req['cycle_id'] for row in cycles), 'repair cycle ID already used')
            decision = repair_decision(run, req['claimed_at_ms'])
            require(decision['status'] == 'ready' and decision['delta_hash'] == req['delta_hash'],
                    'repair decision changed or is blocked')
            spent = decision['remaining']['estimated_cost']
            require(spent + cost <= run['repair_policy']['max_estimated_cost'], 'repair cost limit reached')
            run.setdefault('repair_started_ms', req['claimed_at_ms'])
            record = {'cycle_id': req['cycle_id'], 'status': 'claimed', 'input_delta_hash': req['delta_hash'],
                      'claimed_at_ms': req['claimed_at_ms'], 'estimated_cost': cost,
                      'scope': deepcopy(decision['scope'])}
            cycles.append(record)
            return deepcopy(record)
        if action == 'record':
            cycle = next((row for row in cycles if row['cycle_id'] == req.get('cycle_id')), None)
            require(cycle is not None and cycle['status'] == 'claimed', 'claimed repair cycle required')
            require(type(req.get('completed_at_ms')) is int
                    and req['completed_at_ms'] >= cycle['claimed_at_ms'], 'valid completion time required')
            delta = failure_delta(run)
            require(req.get('output_delta_hash') == delta['digest'], 'repair output delta changed')
            remaining = req.get('remaining_failures')
            require(remaining == delta, 'remaining failures do not match evidence')
            cycle.update(status='recorded', output_delta_hash=delta['digest'],
                         completed_at_ms=req['completed_at_ms'], remaining_failures=deepcopy(remaining),
                         worker_ref=req.get('worker_ref'), proof_refs=deepcopy(req.get('proof_refs', [])))
            return deepcopy(cycle)
        if action == 'stop':
            require(text(req.get('reason_code')), 'stop reason required')
            active = [row for row in cycles if row['status'] == 'claimed']
            if active:
                confirmation = req.get('worker_stop_confirmation')
                require(isinstance(confirmation, dict) and confirmation.get('approved') is True
                        and text(confirmation.get('actor_id')), 'human worker-stop confirmation required')
                require(not any(row.get('status') == 'running' for row in run.get('native_invocations', {}).values()),
                        'native worker must be stopped and reconciled first')
                for row in active:
                    row['status'] = 'stopped'
                    row['stop_reason_code'] = req['reason_code']
            run['repair_stop'] = {'reason_code': req['reason_code'], 'remaining_failures': failure_delta(run)}
            return deepcopy(run['repair_stop'])
        raise WorkflowError('INVALID_EVENT', f'unsupported repair event: {action}')
    if kind.startswith('domain.host.') and kind != 'domain.host.init':
        from .hosts import apply_host_event
        return apply_host_event(data, kind.removeprefix('domain.host.'), req)
    if kind == 'domain.host.init':
        require(text(req.get('repo_id')) and text(req.get('location')), 'repository identity required')
        repositories = data.setdefault('repositories', {})
        prior = repositories.get(req['repo_id'])
        require(prior is None or prior.get('location') == req['location'], 'repository identity conflict')
        repositories[req['repo_id']] = {'location': req['location']}
        return {'repo_id': req['repo_id']}
    if kind == 'domain.issues.capture':
        from .issues import capture_issue
        updated = capture_issue(data, req['issue'])
        data['issues'] = updated['issues']
        data['snapshot_valid'] = False
        return {'issue_id': req['issue']['id'], 'fingerprint': digest(req['issue'])}
    if kind == 'domain.issues.snapshot':
        from .issues import capture_issue, validate_snapshot
        snapshot = req['snapshot']
        require(isinstance(snapshot, dict) and isinstance(snapshot.get('issues'), list), 'snapshot issues required')
        ids = [i.get('id') for i in snapshot['issues'] if isinstance(i, dict)]
        require(len(ids) == len(snapshot['issues']) and all(text(i) for i in ids) and len(set(ids)) == len(ids), 'unique snapshot issue IDs required')
        check = validate_snapshot(snapshot)
        if snapshot.get('complete') is True:
            require(check['valid'], 'complete snapshot has inconsistent pagination')
            require(text(snapshot.get('repo_id')), 'snapshot source repository required')
        for issue in snapshot['issues']:
            data['issues'] = capture_issue(data, issue)['issues']
        fingerprint = digest(snapshot)
        data.setdefault('snapshots', {})[fingerprint] = deepcopy(snapshot)
        data['snapshot_hash'] = fingerprint
        data['snapshot_valid'] = False
        return {'snapshot_hash': fingerprint, 'complete': check['valid']}
    if kind == 'domain.issues.group':
        from .issues import revise_groups
        current_snapshot(data, req['snapshot_hash'])
        groups = req['groups']
        require(isinstance(groups, list) and groups and all(isinstance(g, dict) and text(g.get('id')) and isinstance(g.get('issue_ids'), list) for g in groups), 'valid groups required')
        require(len({g['id'] for g in groups}) == len(groups), 'duplicate group IDs')
        updated = revise_groups(data, req['snapshot_hash'], groups)
        for key in ('groups', 'group_revisions', 'snapshot_valid'):
            data[key] = updated[key]
        return {'snapshot_hash': req['snapshot_hash'], 'revision': len(data['group_revisions'])}
    if kind == 'domain.issues.start':
        from .issues import start_issue_run
        current_snapshot(data, req['snapshot_hash'])
        link = start_issue_run(data, req['group_id'], req['intent'])
        group = next(g for g in data['groups'] if g['id'] == req['group_id'])
        scope = group.get('requirement_ids', {})
        require(req['intent'] != 'build' or (isinstance(scope, dict) and set(scope) == set(group['issue_ids'])
                and all(isinstance(ids, list) and ids and all(text(i) for i in ids) for ids in scope.values())),
                'issue run requires per-issue requirement_ids mapping')
        link['snapshot_hash'] = req['snapshot_hash']
        link['issue_ids'] = deepcopy(group['issue_ids'])
        link['requirement_ids'] = deepcopy(scope)
        link['group_revision'] = len(data.get('group_revisions', []))
        link['run_id'] = digest(link)[:24]
        links = data.setdefault('issue_runs', {})
        require(link['run_id'] not in links, 'linked issue run already exists')
        if req['intent'] == 'build':
            from .runs import start_run
            run = start_run(data, link['run_id'], data.get('plan', {}))
            run['issue_group_id'] = req['group_id']
            planned = {r for i in run['plan']['work_items'] for r in i['requirement_ids']}
            require(all(set(ids).issubset(planned) for ids in scope.values()), 'issue scope is outside the run plan')
            run['issue_scope'] = deepcopy(link)
            data.setdefault('runs', {})[run['id']] = run
        links[link['run_id']] = link
        return link
    if kind == 'domain.issues.classify':
        from .outbox import classify_issue
        require(req['issue_id'] in data.get('issues', {}), 'unknown issue')
        proposal = req['proposal']
        require(proposal.get('kind') in {'escaped-defect', 'change-request', 'spec-gap'}, 'unsupported classification')
        run = data.get('runs', {}).get(proposal.get('run_id'), {})
        accepted = {r['id'] for a in run.get('acceptances', []) if a.get('complete') is True for r in a.get('requirements', []) if r.get('verdict') == 'MET'}
        require(isinstance(proposal.get('requirement_ids'), list) and proposal['requirement_ids'] and set(proposal['requirement_ids']).issubset(accepted), 'classification requires accepted requirement evidence')
        record = classify_issue(data, req['issue_id'], proposal, req.get('confirmed_hash'))
        if req.get('confirmed_hash') is not None:
            require(record['confirmed'] and text(req.get('actor_id')), 'exact classification confirmation and actor required')
            confirmed_at = datetime.fromisoformat(req['confirmed_at'].replace('Z', '+00:00'))
            require(confirmed_at.tzinfo is not None, 'confirmation date requires timezone')
            record['confirmed_at'] = req['confirmed_at']
        record['actor_id'] = req.get('actor_id')
        data.setdefault('classifications', []).append(record)
        return record
    if kind == 'domain.issues.authorize-write':
        current_snapshot(data, req['snapshot_hash'])
        run = data.get('runs', {}).get(req['run_id'], {})
        require(run.get('status') == 'delivered' and run.get('delivery', {}).get('manifest_hash') == req['manifest_hash'], 'exact terminal delivery manifest required')
        scope = run.get('issue_scope', {})
        require(req['issue_id'] in scope.get('issue_ids', []), 'issue is not linked to the immutable delivered run scope')
        original = data.get('snapshots', {}).get(scope.get('snapshot_hash'), {})
        issue = next((i for i in original.get('issues', []) if i.get('id') == req['issue_id']), None)
        require(issue is not None and data['issues'][req['issue_id']]['fingerprint'] == digest(issue), 'issue changed since implementation scope')
        accepted = {r['id'] for a in run.get('acceptances', []) if a.get('complete') is True and a.get('fresh', True) for r in a.get('requirements', []) if r.get('verdict') == 'MET'}
        require(isinstance(req.get('requirement_ids'), list) and req['requirement_ids'] and set(req['requirement_ids']).issubset(accepted), 'accepted issue requirements required')
        require(set(req['requirement_ids']) == set(scope.get('requirement_ids', {}).get(req['issue_id'], [])), 'authorization must cover the exact per-issue requirement scope')
        require(text(req.get('actor_id')) and text(req.get('operation_id')), 'explicit authorizing actor and operation ID required')
        require(req.get('action') in {'create-comment', 'update-comment', 'close-issue'}, 'unsupported external action')
        payload = req['payload']
        require(isinstance(payload, dict) and payload.get('issue_id') == req['issue_id'], 'payload target mismatch')
        marker = f"devflow:{req['run_id']}:{req['issue_id']}"
        require(payload.get('ownership_marker') == marker, 'owned generated-content marker required')
        if req['action'] == 'update-comment':
            require(text(payload.get('remote_comment_id')), 'owned remote comment ID required')
            require(any(r.get('status') == 'sent' and r.get('action') == 'create-comment'
                        and r.get('receipt') == payload['remote_comment_id']
                        and r.get('payload', {}).get('ownership_marker') == marker
                        for r in data.get('outbox', {}).values()), 'comment is not recorded as workflow-owned')
        require(not {'description', 'title'}.intersection(payload), 'external writes cannot replace human issue content')
        record = {**deepcopy(req), 'approved': True, 'payload_hash': digest(payload)}
        authorization_id = digest(record)
        data.setdefault('write_authorizations', {})[authorization_id] = record
        return {'authorization_id': authorization_id, 'manifest_hash': req['manifest_hash']}
    if kind == 'domain.issues.enqueue':
        from .outbox import enqueue_write
        authorization = data.get('write_authorizations', {}).get(req['authorization_id'])
        require(authorization is not None, 'recorded write authorization required')
        current_snapshot(data, authorization['snapshot_hash'])
        operation = {'id': authorization['operation_id'], 'authorization_id': req['authorization_id'],
                     'payload': authorization['payload']}
        updated = enqueue_write(data, authorization['manifest_hash'], operation)
        record = updated['outbox'][operation['id']]
        record['authorization_id'] = req['authorization_id']
        record['action'] = authorization['action']
        data['outbox'] = updated['outbox']
        return {'outbox_id': operation['id'], 'status': record['status']}
    if kind in {'domain.outbox.started', 'domain.outbox.receipt', 'domain.outbox.uncertain'}:
        record = data.get('outbox', {}).get(req['id'])
        require(record is not None, 'unknown outbox operation')
        if kind == 'domain.outbox.started':
            require(record['status'] == 'pending' and text(req.get('token')), 'outbox operation already reserved')
            authorization = data.get('write_authorizations', {}).get(record.get('authorization_id'))
            require(authorization is not None and authorization['payload_hash'] == record['payload_hash'], 'write authorization is missing or stale')
            current_snapshot(data, authorization['snapshot_hash'])
            record.update(status='dispatching', dispatch_token=req['token'])
        else:
            require(record.get('dispatch_token') == req.get('token'), 'dispatch token mismatch')
            require(record['status'] in {'dispatching', 'failed', 'sent'}, 'operation was never dispatched')
            if kind == 'domain.outbox.receipt':
                require(text(req.get('receipt')), 'remote receipt required')
                require(record.get('receipt') in {None, req['receipt']}, 'remote receipt conflict')
                record.update(status='sent', receipt=req['receipt'])
                record.pop('failure', None)
            else:
                require(record['status'] != 'sent', 'sent operation cannot regress')
                record.update(status='failed', failure='remote result uncertain; reconciliation required')
        return {'outbox_id': req['id'], 'status': record['status'], 'receipt': record.get('receipt')}
    if kind == 'domain.migrate.store':
        from .migrations import validate_increments
        require('delivered' not in req['increments'], 'delivery prerequisites come from journal records')
        validation = validate_increments(req['increments'], req['parity'])
        require(validation['valid'], '; '.join(validation['errors']))
        fingerprint = digest(req)
        prior = data.get('migration')
        require(prior is None or prior['hash'] == fingerprint, 'migration plan is immutable once recorded')
        data['migration'] = {'hash': fingerprint, 'increments': deepcopy(req['increments']),
                             'criteria': deepcopy(req['parity']), 'parity': []} if prior is None else prior
        return {'migration_hash': fingerprint}
    if kind == 'domain.migrate.record-parity':
        from .migrations import record_parity
        migration = data.get('migration')
        require(migration is not None, 'migration plan required')
        row = next((r for r in migration['increments']['increments'] if r['id'] == req['increment_id']), None)
        require(row is not None, 'unknown increment')
        verified = req.get('verified', [])
        require(isinstance(verified, list) and all(text(c) for c in verified), 'verified criteria must be IDs')
        refs = req.get('evidence', {})
        require(isinstance(refs, dict) and set(refs) == set(verified), 'exact criterion evidence mappings required')
        for criterion in verified:
            parity_proof(data, row['id'], criterion, refs[criterion])
        updated = record_parity({'required_criteria': {row['id']: row['criteria']},
                                 'parity': [{k:v for k,v in p.items() if k != 'evidence'} for p in migration['parity']]}, row['id'], verified, req.get('ruling'))
        record = next(p for p in updated['parity'] if p['increment_id'] == row['id'])
        prior = next((p for p in migration['parity'] if p['increment_id'] == row['id']), None)
        require(prior is None or prior.get('evidence', {}) == refs, 'parity evidence is immutable')
        record['evidence'] = deepcopy(refs)
        migration['parity'] = updated['parity']
        return {'increment_id': row['id'], 'migration_hash': migration['hash']}
    if kind == 'domain.migrate.bind':
        migration = data.get('migration', {})
        row = next((r for r in migration.get('increments', {}).get('increments', []) if r['id'] == req['increment_id']), None)
        require(row is not None, 'unknown increment')
        run = data.get('runs', {}).get(req['run_id'], {})
        require(run.get('status') == 'active', 'active run required for migration binding')
        require(run.get('migration_increment_id') in {None, row['id']}, 'run is already bound to another increment')
        run['migration_increment_id'] = row['id']
        return {'run_id': req['run_id'], 'increment_id': row['id']}
    if kind == 'domain.migrate.delivered':
        migration = data.get('migration', {})
        row = next((r for r in migration.get('increments', {}).get('increments', []) if r['id'] == req['increment_id']), None)
        require(row is not None, 'unknown increment')
        delivered = migration.setdefault('deliveries', {})
        require(all(d in delivered for d in row.get('depends_on', [])), 'predecessor delivery required')
        require(any(p['increment_id'] == row['id'] for p in migration.get('parity', [])), 'parity acceptance required')
        run = data.get('runs', {}).get(req['run_id'], {})
        require(run.get('status') == 'delivered' and isinstance(run.get('delivery'), dict), 'terminal run delivery evidence required')
        require(run.get('migration_increment_id') == row['id'], 'delivery run is not bound to this increment')
        migration_delivery_guard(data, req['run_id'])
        require(row['id'] not in delivered, 'increment already delivered')
        delivered[row['id']] = {'run_id': req['run_id'], 'manifest_hash': run['delivery']['manifest_hash']}
        return delivered[row['id']]
    if kind == 'domain.ingest.record':
        index = req['index']
        repo_id = req['repo_id']
        require(repo_id in data.get('repositories', {}), 'source repository is not registered')
        require(isinstance(index.get('sources'), list) and text(index.get('fingerprint')), 'source index required')
        paths = set()
        from pathlib import PurePosixPath
        for source in index['sources']:
            path = PurePosixPath(source['path'])
            require(not path.is_absolute() and '..' not in path.parts and source['path'] not in paths, 'invalid or duplicate source path')
            require(isinstance(source.get('text'), str) and hashlib.sha256(source['text'].encode()).hexdigest() == source['hash'], 'source content hash mismatch')
            paths.add(source['path'])
        require(isinstance(req.get('cache'), dict), 'ingestion cache required')
        record = {**deepcopy(index), 'repo_id': repo_id, 'repository_fingerprint': req['repository_fingerprint'], 'profile': req['profile'], 'scope': req['scope']}
        identifier = digest({'repo_id': repo_id, 'content_fingerprint': index['fingerprint']})
        record['content_fingerprint'] = index['fingerprint']
        record['fingerprint'] = identifier
        data.setdefault('source_indexes', {})[identifier] = record
        data.setdefault('ingestion_cache', {}).update(deepcopy(req['cache']))
        # Views that depend on this repository must use the current index.
        data.setdefault('current_source_indexes', {})[repo_id] = identifier
        return {'index_id': identifier, 'source_count': len(index['sources']), 'cache_hit': index['cache_hit']}
    if kind == 'domain.harden.configure':
        run = data.get('runs', {}).get(req['run_id'])
        require(run is not None and run.get('status') == 'active', 'active run required')
        gates = req['gates']
        require(text(req.get('actor_id')) and isinstance(gates, dict) and gates, 'actor and nonempty gate configuration required')
        for identifier, config in gates.items():
            require(text(identifier) and isinstance(config, dict) and config.get('repo_id') in data.get('repositories', {}), 'gate repository missing')
            require(isinstance(config.get('command'), list) and config['command'] and all(isinstance(a, str) for a in config['command']), 'gate argv required')
            require(any(i.get('repo_id') == config['repo_id'] for i in run.get('plan', {}).get('work_items', [])), 'gate repository is outside run')
            if 'contract' in config:
                normalize_contract(config)
        run['hardening_config'] = deepcopy(gates)
        run['hardening_config_hash'] = digest(gates)
        run['required_hardening_gates'] = sorted(gates)
        run['hardening_proofs'] = {}
        for config in gates.values():
            run.setdefault('repositories', {})[config['repo_id']] = deepcopy(data['repositories'][config['repo_id']])
        return {'config_hash': run['hardening_config_hash'], 'gate_ids': sorted(gates)}
    if kind == 'domain.harden.started':
        run = data.get('runs', {}).get(req['run_id'], {})
        require(req['config_hash'] == run.get('hardening_config_hash') and req['gate_id'] in run.get('hardening_config', {}), 'gate configuration is stale')
        require(text(req.get('token')), 'execution token required')
        config = run['hardening_config'][req['gate_id']]
        if 'contract' in config:
            require(req.get('contract_hash') == digest(normalize_contract(config)), 'gate contract is stale')
        else:
            require(req.get('contract_hash') in {None, digest({'kind': 'exit-status'})}, 'legacy gate contract mismatch')
        run.setdefault('hardening_attempts', {})[req['token']] = deepcopy(req)
        return {'token': req['token'], 'status': 'running'}
    if kind == 'domain.harden.record':
        run = data.get('runs', {}).get(req['run_id'], {})
        attempt = run.get('hardening_attempts', {}).get(req['token'])
        require(attempt and attempt['gate_id'] == req['gate_id'], 'gate attempt missing')
        require(req['config_hash'] == run.get('hardening_config_hash'), 'gate configuration changed during verification')
        proof = req['proof']
        require(type(proof.get('passed')) is bool, 'gate outcome required')
        config = run['hardening_config'][req['gate_id']]
        require(proof.get('argv') == config['command'], 'gate command mismatch')
        expected_contract_hash = digest(normalize_contract(config))
        if 'contract' in config or attempt.get('contract_hash') is not None:
            require(proof.get('contract_hash') == attempt.get('contract_hash') == expected_contract_hash,
                    'gate report contract mismatch')
        else:
            require(proof.get('contract_hash') is None, 'legacy gate report contract mismatch')
        proof = {**deepcopy(proof), 'config_hash': req['config_hash'], 'repo_id': config['repo_id'],
                 'repository_fingerprint': attempt['repository_fingerprint']}
        attempt['status'] = 'passed' if proof['passed'] else 'failed'
        run.setdefault('hardening_proofs', {})[req['gate_id']] = proof
        return {'proof': proof}
    if kind == 'domain.stats.usage-import':
        from .usage import import_usage
        imported = import_usage(req['records'], req.get('adapter_version', 'v1'), req.get('bindings', {}))
        usage = data.setdefault('usage', {'events': [], 'gaps': [], 'unbound': []})
        existing = {(r['source_id'], r['event_id']): r for r in usage['events']}
        for row in imported['events']:
            key = (row['source_id'], row['event_id'])
            require(key not in existing or existing[key] == row, 'usage event identity conflict')
            binding = row.get('binding')
            if binding is not None:
                require(isinstance(binding, dict) and binding.get('run_id') in data.get('runs', {}), 'usage binding references unknown run')
            existing[key] = row
        usage['events'] = [existing[k] for k in sorted(existing)]
        usage['gaps'] = sorted(set(usage['gaps'] + imported['gaps']))
        usage['unbound'] = [f"{r['source_id']}:{r['event_id']}" for r in usage['events'] if r.get('binding') is None]
        usage['complete'] = not usage['gaps']
        return {'event_count': len(existing), 'gaps': usage['gaps'], 'unbound_count': len(usage['unbound'])}
    if kind == 'domain.stats.prices':
        from .pricing import store_prices
        require(isinstance(req.get('source'), dict) and text(req['source'].get('timestamp')), 'price source timestamp required')
        record = store_prices(data, req['version'], req['source'], req['rates'])
        prior = data.setdefault('prices', {}).get(req['version'])
        require(prior is None or prior == record, 'price version is immutable')
        data['prices'][req['version']] = record
        return {'price_id': record['id'], 'price_version': record['version']}
    if kind == 'domain.stats.metrics':
        from .metrics import calculate_metrics, freeze_report
        as_of = req['as_of']
        parsed = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
        require(parsed.tzinfo is not None, 'report date requires an explicit timezone')
        effective = {}
        for c in data.get('classifications', []):
            if c.get('confirmed') is True and c.get('confirmed_at'):
                at = datetime.fromisoformat(c['confirmed_at'].replace('Z', '+00:00'))
                if at <= parsed and (c['issue_id'] not in effective or at >= datetime.fromisoformat(effective[c['issue_id']]['confirmed_at'].replace('Z', '+00:00'))):
                    effective[c['issue_id']] = c
        runs = []
        selected = req.get('run_ids')
        if selected is not None:
            require(isinstance(selected, list) and all(r in data.get('runs', {}) for r in selected), 'unknown report run selection')
        for run_id, run in data.get('runs', {}).items():
            if selected is not None and run_id not in selected:
                continue
            acceptance = next((a for a in reversed(run.get('acceptances', [])) if a.get('complete') is True and a.get('fresh', True)), None)
            delivery = run.get('delivery', {})
            date = delivery.get('actual_result', {}).get('delivered_at') or delivery.get('recorded_at')
            if run.get('status') != 'delivered' or not acceptance or not date:
                continue
            require(datetime.fromisoformat(date.replace('Z', '+00:00')).tzinfo is not None, 'delivery timestamp lacks timezone')
            if datetime.fromisoformat(date.replace('Z', '+00:00')) > parsed:
                continue
            runs.append({'id': run_id, 'status': 'delivered', 'acceptance': True,
                         'delivery_at': date, 'accepted_requirements': [r['id'] for r in acceptance['requirements'] if r['verdict'] == 'MET'],
                         'classifications': [c for c in effective.values()
                            if c['proposal'].get('run_id') == run_id and c.get('confirmed') is True
                            and c.get('confirmed_at') and datetime.fromisoformat(c['confirmed_at'].replace('Z', '+00:00')) <= parsed]})
        report = calculate_metrics(runs, {}, as_of)
        report['excluded_run_ids'] = sorted(set(data.get('runs', {})) - set(report['run_ids']))
        report['source_version'] = version
        report['source_hash'] = digest({k: data.get(k) for k in ('runs', 'classifications', 'usage', 'prices')})
        report['price_version'] = req.get('price_version')
        report['project'] = req.get('project')
        report['version'] = req.get('version')
        report['cost'] = None
        report['cost_reason'] = 'supported usage expectations and prices required'
        report['usage_coverage'] = None
        # Price each run independently: a covered run cannot hide missing usage in another.
        from .usage import usage_coverage
        from .pricing import price_usage
        price = data.get('prices', {}).get(req.get('price_version'))
        costs = {}
        expectations = data.get('usage_expectations', [])
        events = data.get('usage', {}).get('events', [])
        for run in runs:
            identifier = run['id']
            expected = [e for e in expectations if e.get('run_id') == identifier]
            usage = {'events': [e for e in events if isinstance(e.get('binding'), dict) and e['binding'].get('run_id') == identifier],
                     'gaps': data.get('usage', {}).get('gaps', [])}
            coverage = usage_coverage(expected, usage)
            conflicts = [e for e in usage['events'] if any(x['source_id'] == e['source_id'] and x['event_id'] == e['event_id'] and x['run_id'] != identifier for x in expectations)]
            result = (price_usage(usage, price, coverage) if price and expected and not conflicts
                      else {'cost': None, 'reason': 'matching runtime expectations and prices required'})
            costs[identifier] = {**result, 'coverage': coverage, 'accepted_requirements': len(run['accepted_requirements'])}
        report['run_costs'] = costs
        report['cost_excluded_run_ids'] = sorted(r for r, c in costs.items() if c['cost'] is None)
        report['cost_run_ids'] = sorted(r for r, c in costs.items() if c['cost'] is not None)
        report['cost_denominator'] = sum(c['accepted_requirements'] for c in costs.values() if c['cost'] is not None)
        report['priced_cost'] = sum(c['cost'] for c in costs.values() if c['cost'] is not None) if report['cost_run_ids'] else None
        report['usage_coverage'] = min((c['coverage']['coverage'] if c['coverage']['coverage'] is not None else 0 for c in costs.values()), default=None)
        if costs and not report['cost_excluded_run_ids']:
            report['cost'], report['cost_reason'] = report['priced_cost'], None
        elif costs:
            report['cost_reason'] = 'one or more runs lack eligible usage or prices'
        updated = freeze_report(data, report)
        data['reports'] = updated['reports']
        return {'report': data['reports'][-1]}
    if kind == 'domain.stats.expectations':
        rows = req['events']
        require(isinstance(rows, list) and all(isinstance(r, dict) and text(r.get('source_id')) and text(r.get('event_id')) for r in rows), 'runtime identity expectations required')
        require(all(r.get('run_id') in data.get('runs', {}) for r in rows), 'runtime expectations require registered run identity')
        old = {(r['source_id'], r['event_id']): r for r in data.get('usage_expectations', [])}
        for row in rows:
            key = (row['source_id'], row['event_id'])
            require(key not in old or old[key] == row, 'runtime expectation conflict')
            old[key] = deepcopy(row)
        data['usage_expectations'] = [old[k] for k in sorted(old)]
        return {'expected_event_count': len(old)}
    if kind == 'domain.stats.legacy-import':
        record = req['record']
        require(record.get('legacy') is True and text(record.get('source_hash')) and text(record.get('source_run_id')), 'invalid legacy import')
        data.setdefault('legacy_imports', {})[record['source_hash']] = deepcopy(record)
        return {'source_hash': record['source_hash'], 'legacy': True}
    raise WorkflowError('INVALID_EVENT', f'unsupported domain event: {kind}')


def migration_delivery_guard(data, run_id):
    run = data.get('runs', {}).get(run_id, {})
    identifier = run.get('migration_increment_id')
    if identifier is None:
        return
    migration = data.get('migration', {})
    row = next((r for r in migration.get('increments', {}).get('increments', []) if r['id'] == identifier), None)
    require(row is not None, 'bound migration increment is unavailable')
    require(identifier not in migration.get('deliveries', {}), 'increment already delivered')
    require(all(dep in migration.get('deliveries', {}) for dep in row.get('depends_on', [])), 'predecessor delivery required')
    parity = next((p for p in migration.get('parity', []) if p['increment_id'] == identifier), None)
    require(parity is not None, 'migration parity evidence required')
    for criterion in parity.get('verified', []):
        ref = parity.get('evidence', {}).get(criterion, {})
        require(ref.get('run_id') == run_id, 'parity proof belongs to another run')
        parity_proof(data, identifier, criterion, ref)


def parity_proof(data, increment_id, criterion, ref):
    run = data.get('runs', {}).get(ref.get('run_id'), {})
    require(run.get('migration_increment_id') == increment_id, 'parity run is not bound to this increment')
    proof_id = ref.get('proof_id')
    proof = run.get('verification_proofs', {}).get(proof_id, {})
    verifier = next((v for k,v in run.get('verifier_proofs', {}).items() if v.get('evidence_id', k) == proof_id), {})
    item_id = proof.get('item_id')
    item = next((i for i in run.get('plan', {}).get('work_items', []) if i['id'] == item_id), {})
    attempts = run.get('items', {}).get(item_id, {}).get('attempts', [])
    final = ((item.get('kind') == 'code' and proof.get('phase') == 'GREEN') or
             (item.get('kind') == 'iac' and proof.get('kind') == 'iac-apply') or
             (item.get('kind') == 'agent-config' and proof.get('kind') == 'agent-evaluation' and proof.get('phase') == 'post'))
    require(proof.get('passed') is True and proof.get('fresh', True) and verifier.get('passed') is True
            and final and attempts and proof.get('token') == attempts[-1].get('token')
            and verifier.get('token') == proof.get('token') and verifier.get('item_id') == item_id,
            'criterion requires current final registered verification')
    definition = next((c for c in data['migration']['criteria'] if c['id'] == criterion), {})
    required = definition.get('requirement_ids')
    require(isinstance(required, list) and required and ref.get('requirement_ids') == required
            and set(required).issubset(item.get('requirement_ids', [])), 'criterion requirement scope mismatch')
