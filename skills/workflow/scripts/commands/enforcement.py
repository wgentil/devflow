"""Explicit enforcement adoption and read-only policy diagnostics."""
import json
from pathlib import Path
from .journal import add_journal_options, commit
from workflow_lib.action_policy import subject_decision
from workflow_lib.storage_access import read_current
from workflow_lib.store import WorkflowError


def register_commands(parser):
    group = parser.add_parser('enforcement')
    actions = group.add_subparsers(dest='enforcement_command', required=True)
    for name in ('decide', 'adopt', 'question', 'answer', 'propose-fix', 'close-finding', 'close-canonical', 'consolidate-findings', 'split-findings', 'finding-disposition', 'configure-effects', 'extend-effects', 'claim', 'effect-transition', 'observe-source', 'protect-inventory', 'reconcile-tool', 'propose-protected-change', 'approve-protected-change'):
        command = actions.add_parser(name)
        add_journal_options(command)
        command.add_argument('--input', required=True)
    for name in ('session-verify','session-prepare','session-review','session-complete','session-protect-inventory','session-reconcile'):
        command=actions.add_parser(name)
        command.add_argument('--session',required=True)
        command.add_argument('--operation-id',required=True)
        if name in {'session-verify','session-review','session-protect-inventory','session-reconcile'}:command.add_argument('--input',required=True)
    for name in ('session-init', 'session-event', 'session-status'):
        command = actions.add_parser(name)
        command.add_argument('--session', required=True)
        if name != 'session-status': command.add_argument('--input', required=True)
        if name == 'session-event':
            command.add_argument('--operation-id', required=True)
            command.add_argument('--expected-version', required=True, type=int)


def dispatch(parsed):
    if parsed.enforcement_command.startswith('session-'):
        from workflow_lib.review_sessions import initialize_session, read_session, transact_session
        path = Path(parsed.session)
        if parsed.enforcement_command in {'session-verify','session-prepare','session-review','session-complete','session-protect-inventory','session-reconcile'}:
            from workflow_lib.session_evidence import capture,prepare,record_review,complete
            name=parsed.enforcement_command
            if name=='session-prepare':return prepare(path,parsed.operation_id)
            if name=='session-complete':return complete(path,parsed.operation_id)
            request=json.loads(Path(parsed.input).read_text(encoding='utf-8'))
            if name=='session-verify':return capture(path,request['phase'],parsed.operation_id,request.get('timeout_seconds',300))
            if name=='session-review':return record_review(path,request,parsed.operation_id)
            if name=='session-reconcile':
                from workflow_lib.enforcement_recovery import reconcile_session
                return reconcile_session(path,request['execution_id'],request['worker_stop_confirmation'],parsed.operation_id)
            from workflow_lib.session_evidence import _retry,_commit
            prior=_retry(path,parsed.operation_id,'inventory',request)
            if prior:return prior
            state=read_session(path);subject=state['subject']
            from workflow_lib.protected_changes import snapshot_protected
            record={**request,'baseline':snapshot_protected(Path(subject['repositories'][request['repo_id']]['location']),request['inventory'])}
            return _commit(path,state,parsed.operation_id,'protect-inventory',record,client=request,kind='inventory')
        if parsed.enforcement_command == 'session-status': return read_session(path)
        request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
        if parsed.enforcement_command == 'session-init': return initialize_session(path, request)
        return transact_session(path, parsed.expected_version, parsed.operation_id, request)

    request = json.loads(Path(parsed.input).read_text(encoding='utf-8'))
    if parsed.enforcement_command=='reconcile-tool':
        from workflow_lib.enforcement_recovery import reconcile_tool
        return reconcile_tool(Path(parsed.root),request['run_id'],request['record']['execution_id'],request['record']['worker_stop_confirmation'],parsed.operation_id)
    if parsed.enforcement_command in {'close-finding','close-canonical','consolidate-findings','split-findings','finding-disposition'}:
        if not parsed.root:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'mutations require --root')
        if not getattr(parsed, 'operation_id_explicit', False):
            raise WorkflowError('OPERATION_ID_REQUIRED', 'mutations require --operation-id for safe retry')
        from workflow_lib.storage_access import operation_lookup
        if operation_lookup(Path(parsed.root), parsed.operation_id):
            return commit(parsed, 'domain.enforcement.'+parsed.enforcement_command, request)
        state = read_current(Path(parsed.root), run_id=request['run_id'])
        if parsed.expected_version is not None and parsed.expected_version != state['version']:
            raise WorkflowError('STATE_VERSION_CONFLICT', 'Re-read current closure inputs before retrying.')
        subject = state['data'].get('runs', {}).get(request['run_id'])
        if not subject: raise WorkflowError('RUN_UNAVAILABLE', 'Known run required.')
        from workflow_lib.finding_closure import validate_closure
        from workflow_lib.enforcement_live import assert_source_current, assert_protection_current
        from workflow_lib.host_completion import package_current
        from workflow_lib.finding_index import validate_canonical_closure
        action=parsed.enforcement_command
        closure=(validate_canonical_closure(subject,request['record']) if action=='close-canonical' else
            validate_closure(subject,request['record']) if action=='close-finding' else {'review_ids':[request['record']['review_id']]})
        assert_source_current(subject)
        protection_receipts = assert_protection_current(subject)
        member_ids=(list(closure['members']) if action=='close-canonical' else [request['record'].get('finding_id')])
        candidate = {'proof_ids':[pid for fid in member_ids for pid in subject.get('corrections',{}).get(fid,{}).get('proof_ids',[])]}
        for proof_id in candidate.get('proof_ids', []):
            verifier = subject.get('verifier_proofs', {}).get(proof_id, {})
            evidence = subject.get('verification_proofs', {}).get(verifier.get('evidence_id'), {})
            if evidence.get('kind') == 'code' and evidence.get('protection_receipts') != protection_receipts:
                raise WorkflowError('FINDING_CLOSURE_BLOCKED', 'Renew code proof after a protected verification-context change.')
        for review in (r for rows in subject.get('reviews',{}).values() for r in rows if r.get('review_id') in closure['review_ids']):
            package=subject.get('review_packages',{}).get(review['package_hash'])
            if not package or not package_current(subject,package):
                raise WorkflowError('FINDING_CLOSURE_BLOCKED','Current actual review inputs required before closing the finding.')
        parsed.expected_version = state['version']
    if parsed.enforcement_command == 'protect-inventory':
        from workflow_lib.protected_changes import snapshot_protected
        from workflow_lib.storage_access import operation_lookup
        prior = operation_lookup(Path(parsed.root), parsed.operation_id)
        if prior:
            previous = prior.get('payload', {}).get('request', {})
            previous_record = {k:v for k,v in previous.get('record', {}).items() if k != 'baseline'}
            current_record = {k:v for k,v in request.get('record', {}).items() if k != 'baseline'}
            if (prior.get('kind') != 'domain.enforcement.protect-inventory'
                    or previous.get('run_id') != request.get('run_id') or previous_record != current_record):
                raise WorkflowError('OPERATION_CONFLICT', 'Operation belongs to a different protection request.')
            return commit(parsed, prior['kind'], previous)
        state = read_current(Path(parsed.root), run_id=request['run_id'])
        subject = state['data']['runs'][request['run_id']]
        record = request['record']
        repo = subject['repositories'][record['repo_id']]
        request = {**request, 'record': {**record, 'baseline': snapshot_protected(Path(repo['location']), record['inventory'])}}
        parsed.expected_version = state['version']
    if parsed.enforcement_command == 'propose-protected-change':
        from workflow_lib.protected_changes import observe_protected_changes
        from workflow_lib.storage_access import operation_lookup
        prior = operation_lookup(Path(parsed.root), parsed.operation_id)
        if prior:
            previous = prior.get('payload', {}).get('request', {})
            if (prior.get('kind') != 'domain.enforcement.propose-protected-change'
                    or previous.get('run_id') != request.get('run_id')
                    or previous.get('record', {}).get('repo_id') != request.get('record', {}).get('repo_id')):
                raise WorkflowError('OPERATION_CONFLICT', 'Operation belongs to another protected-change proposal.')
            return commit(parsed, prior['kind'], previous)
        state = read_current(Path(parsed.root), run_id=request['run_id'])
        subject = state['data']['runs'][request['run_id']]
        repo_id = request['record']['repo_id']
        protection = subject.get('protected_inventories', {}).get(repo_id)
        if not protection: raise WorkflowError('PROTECTION_INVENTORY_REQUIRED', 'Declare governing inventory first.')
        observation = observe_protected_changes(Path(subject['repositories'][repo_id]['location']),
            protection['inventory'], protection['baseline'])
        request = {'run_id': request['run_id'], 'record': {'repo_id': repo_id, 'observation': observation}}
        parsed.expected_version = state['version']
    if parsed.enforcement_command == 'observe-source':
        from workflow_lib.enforcement_live import source_observation
        from workflow_lib.storage_access import operation_lookup
        prior = operation_lookup(Path(parsed.root), parsed.operation_id)
        if prior and prior.get('kind') == 'domain.enforcement.observe-source' and prior['payload']['request'].get('run_id') == request.get('run_id'):
            return commit(parsed, prior['kind'], prior['payload']['request'])
        state = read_current(Path(parsed.root), run_id=request['run_id'])
        subject = state['data'].get('runs', {}).get(request['run_id'])
        if not subject: raise WorkflowError('RUN_UNAVAILABLE', 'Known run required.')
        request = {'run_id': request['run_id'], 'record': source_observation(subject)}
        parsed.expected_version = state['version']
    if parsed.enforcement_command != 'decide':
        return commit(parsed, 'domain.enforcement.' + parsed.enforcement_command, request)
    if not parsed.root:
        raise WorkflowError('CONTROL_ROOT_REQUIRED', 'decision diagnostics require --root')
    state = read_current(Path(parsed.root), run_id=request['run_id'])
    run = state['data'].get('runs', {}).get(request['run_id'])
    if run is None:
        raise WorkflowError('RUN_UNAVAILABLE', 'known run required')
    return subject_decision(run, request['action'], request.get('scope', {}))
