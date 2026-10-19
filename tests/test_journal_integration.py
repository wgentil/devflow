"""Exercise authoritative auxiliary workflows through fresh CLI processes."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'skills/workflow/scripts/run.py'
sys.path.insert(0, str(ENTRY.parent))
from workflow_lib.store import read_state, transact, WorkflowError

class JournalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'control'
        self.input = Path(self.temp.name) / 'input.json'
    def tearDown(self): self.temp.cleanup()
    def cli(self, group, operation, data, op, **options):
        self.input.write_text(json.dumps(data))
        args = [sys.executable, str(ENTRY), group, operation, '--root', str(self.root),
                '--input', str(self.input), '--operation-id', op]
        if options: args += ['--options', json.dumps(options)]
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)
    def test_issue_snapshot_group_and_replay_survive_snapshot_loss(self):
        self.cli('issues', 'capture', {'issue': {'id':'i1','description':'human'}}, 'capture')
        snapshot={'complete':True,'repo_id':'r','pages':[1],'expected_pages':1,
                  'issues':[{'id':'i1','description':'human'}]}
        result=self.cli('issues','snapshot',{'snapshot':snapshot},'snapshot')
        self.cli('issues','group',{'snapshot_hash':result['snapshot_hash'],
                 'groups':[{'id':'g','issue_ids':['i1']}]},'group')
        version=read_state(self.root)['version']
        (self.root/'state.json').write_text('corrupt cache')
        replay=self.cli('issues','group',{'snapshot_hash':result['snapshot_hash'],
                 'groups':[{'id':'g','issue_ids':['i1']}]},'group')
        self.assertTrue(replay['replayed'])
        state=read_state(self.root)
        self.assertEqual(state['version'],version)
        self.assertEqual(state['data']['issues']['i1']['original']['description'],'human')
        self.assertEqual(state['data']['groups'][0]['id'],'g')
    def test_partial_snapshot_and_injected_state_cannot_group(self):
        self.cli('issues','snapshot',{'snapshot':{'complete':False,'issues':[{'id':'i'}]}},'partial')
        before=read_state(self.root)
        with self.assertRaises(WorkflowError):
            transact(self.root,before['version'],'bad',{'kind':'domain.issues.group',
                     'payload':{'request':{'snapshot_hash':'bad','groups':[]}}})
        self.assertEqual(read_state(self.root)['version'],before['version'])
    def test_usage_backfill_and_prices_are_append_only(self):
        row={'source_id':'session','event_id':'e','provider':'p','model':'m',
             'input_tokens':10,'cached_tokens':2,'output_tokens':3}
        self.cli('stats','usage-import',[row],'u1',adapter_version='v1')
        self.cli('stats','usage-import',[row],'u2',adapter_version='v1')
        self.assertEqual(len(read_state(self.root)['data']['usage']['events']),1)
        prices={'version':'v1','source':{'timestamp':'2026-10-06T00:00:00Z'},
                'rates':{'p/m':{'input':1,'cached':.5,'output':2}}}
        self.cli('stats','prices',prices,'p1')
        original=read_state(self.root)['data']['prices']['v1']
        with self.assertRaises(WorkflowError):
            transact(self.root,read_state(self.root)['version'],'p2',{'kind':'domain.stats.prices',
                     'payload':{'request':{**prices,'rates':{'p/m':{'input':9,'cached':9,'output':9}}}}})
        self.assertEqual(read_state(self.root)['data']['prices']['v1'],original)
    def test_report_freezes_journal_inputs_instead_of_caller_outcomes(self):
        result=self.cli('stats','metrics',{'runs':[{'id':'forged','status':'delivered','acceptance':True}]},
                        'report',as_of='2026-10-06T00:00:00Z')
        self.assertEqual(result['report']['run_ids'],[])
        before=read_state(self.root)['data']['reports'][0]
        self.cli('stats','metrics',{},'later',as_of='2026-11-06T00:00:00Z')
        self.assertEqual(read_state(self.root)['data']['reports'][0],before)
    def test_migration_plan_and_parity_survive_replay(self):
        self.cli('migrate','store',{'increments':{'increments':[{'id':'one','depends_on':[],
                 'criteria':['c1']}]},'parity':[{'id':'c1'}]},'migration')
        with self.assertRaises(WorkflowError):
            transact(self.root,1,'unknown',{'kind':'domain.migrate.record-parity',
                'payload':{'request':{'increment_id':'missing','verified':[]}}})
        result=self.cli('migrate','record-parity',{'increment_id':'one','verified':[],
            'ruling':{'approved':True,'actor_id':'human','why':'removed intentionally',
                      'cost_if_wrong':'restore it','criteria':['c1']}},'parity')
        self.assertEqual(read_state(self.root)['data']['migration']['parity'][0]['increment_id'],'one')
    def test_unknown_domain_events_fail_without_mutation(self):
        with self.assertRaises(WorkflowError):
            transact(self.root,0,'unknown',{'kind':'domain.unknown','payload':{'request':{}}})
        self.assertEqual(read_state(self.root)['version'],0)

    def test_policy_is_explicit_and_bounded(self):
        self._repair_fixture()
        bad = {'enabled': True, 'max_attempts': 0, 'max_elapsed_ms': 1000,
               'max_estimated_cost': 10, 'no_progress_window': 2}
        with self.assertRaises(WorkflowError):
            self._repair_event('configure', {'run_id': 'r', 'policy': bad}, 'bad')
        self.assertEqual(read_state(self.root)['data']['runs']['r'].get('repair_policy'), None)
        good = {**bad, 'max_attempts': 2}
        self._repair_event('configure', {'run_id': 'r', 'policy': good}, 'policy')
        self.assertEqual(read_state(self.root)['data']['runs']['r']['repair_policy'], good)

    def test_duplicate_claim_replays_once(self):
        from workflow_lib.repair import failure_delta
        self._repair_fixture()
        policy = {'enabled': True, 'max_attempts': 2, 'max_elapsed_ms': 1000,
                  'max_estimated_cost': 10, 'no_progress_window': 2}
        self._repair_event('configure', {'run_id': 'r', 'policy': policy}, 'policy')
        digest = failure_delta(read_state(self.root)['data']['runs']['r'])['digest']
        req = {'run_id': 'r', 'cycle_id': 'cycle-1', 'delta_hash': digest,
               'claimed_at_ms': 100, 'estimated_cost': 1}
        first = self._repair_event('claim', req, 'claim')
        replay = self._repair_event('claim', req, 'claim')
        self.assertFalse(first['replayed'])
        self.assertTrue(replay['replayed'])
        self.assertEqual(len(read_state(self.root)['data']['runs']['r']['repair_cycles']), 1)
        self._repair_event('record', {'run_id': 'r', 'cycle_id': 'cycle-1',
                           'output_delta_hash': digest, 'completed_at_ms': 200,
                           'remaining_failures': __import__('workflow_lib.repair', fromlist=['failure_delta']).failure_delta(
                               read_state(self.root)['data']['runs']['r'])}, 'record')
        self.assertEqual(read_state(self.root)['data']['runs']['r']['repair_cycles'][0]['status'], 'recorded')

    def test_repair_stop_surfaces_remaining_failures(self):
        from workflow_lib.repair import repair_decision
        self._repair_fixture()
        result = self._repair_event('stop', {'run_id': 'r', 'reason_code': 'HUMAN_DECISION'}, 'stop')
        self.assertEqual(result['state']['data']['domain_receipts']['stop']['remaining_failures']['gate_ids'],
                         ['security'])
        self.assertEqual(repair_decision(read_state(self.root)['data']['runs']['r'], 100)['reason_code'],
                         'HUMAN_DECISION')

    def _repair_fixture(self):
        run = {'id': 'r', 'status': 'active', 'actors': {'implementer': 'worker'},
               'plan': {'work_items': []}, 'items': {},
               'required_hardening_gates': ['security'], 'hardening_config_hash': 'cfg',
               'hardening_proofs': {'security': {'passed': False, 'config_hash': 'cfg'}},
               'unresolved_findings': []}
        transact(self.root, 0, 'fixture', {'kind': 'fixture', 'payload': {'runs': {'r': run}}})

    def _repair_event(self, action, request, operation_id):
        state = read_state(self.root)
        return transact(self.root, state['version'], operation_id,
                        {'kind': 'domain.repair.' + action, 'payload': {'request': request}})


class MigrationPilotIntegrationTests(unittest.TestCase):
    cli = JournalIntegrationTests.cli
    def setUp(self):
        JournalIntegrationTests.setUp(self)
        self.repo = Path(self.temp.name) / 'app'
        self.repo.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'config', 'user.email', 'test@example.invalid'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'config', 'user.name', 'Test'], check=True)
        (self.repo / 'fixture.txt').write_text('same')
        subprocess.run(['git', '-C', str(self.repo), 'add', 'fixture.txt'], check=True)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-qm', 'fixture'], check=True)
        run = {'id': 'r', 'status': 'active', 'plan': {'work_items': [{
            'id': 'W1', 'kind': 'code', 'repo_id': 'app', 'requirement_ids': ['R1']}]},
            'items': {'W1': {'status': 'complete', 'attempts': [{'token': 't', 'status': 'verified'}]}},
            'repositories': {'app': {'location': str(self.repo)}}}
        transact(self.root, 0, 'fixture', {'kind': 'fixture', 'payload': {
            'repositories': {'app': {'location': str(self.repo)}}, 'runs': {'r': run}}})
        self.cli('migrate', 'store', {'increments': {'increments': [{
            'id': 'greetings', 'depends_on': [], 'criteria': ['P1']}]},
            'parity': [{'id': 'P1', 'requirement_ids': ['R1']}]}, 'migration')
        self.cli('migrate', 'bind', {'run_id': 'r', 'increment_id': 'greetings'}, 'bind')

    def tearDown(self): JournalIntegrationTests.tearDown(self)

    def pilot(self):
        import hashlib
        digest = hashlib.sha256(b'same').hexdigest()
        command = [sys.executable, '-c',
                   "from pathlib import Path; Path('out.txt').write_text(Path('fixture.txt').read_text(encoding='utf-8'))"]
        return {'run_id': 'r', 'increment_id': 'greetings', 'criterion_id': 'P1',
                'item_id': 'W1', 'repo_id': 'app', 'pilot': {
                'fixtures': [{'path': 'fixture.txt', 'sha256': digest}],
                'legacy_argv': command, 'replacement_argv': command,
                'legacy_output_path': 'out.txt', 'replacement_output_path': 'out.txt',
                'comparator': {'kind': 'exact-bytes', 'version': 1}}}

    def test_pilot_proof_survives_replay_without_execution(self):
        request = self.pilot()
        first = self.cli('migrate', 'verify-pilot', request, 'pilot')
        self.assertTrue(first['proof']['passed'])
        replay = self.cli('migrate', 'verify-pilot', request, 'pilot')
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['proof']['proof_id'], first['proof']['proof_id'])

    def test_stale_repo_blocks_typed_parity(self):
        request = self.pilot()
        result = self.cli('migrate', 'verify-pilot', request, 'pilot')
        ref = {'run_id': 'r', 'proof_id': result['proof']['proof_id'],
               'requirement_ids': ['R1']}
        self.cli('migrate', 'record-parity', {'increment_id': 'greetings',
                 'verified': ['P1'], 'evidence': {'P1': ref}}, 'parity')
        (self.repo / 'fixture.txt').write_text('changed')
        from workflow_lib.journal_domains import migration_delivery_guard
        from workflow_lib.evidence import repository_fingerprint
        fingerprint = repository_fingerprint(self.repo)
        with self.assertRaises(WorkflowError):
            migration_delivery_guard(read_state(self.root)['data'], 'r', {'app': {
                'repository_head': fingerprint['head'],
                'worktree_digest': fingerprint['worktree_digest']}})

    def test_stale_attempt_or_comparator_mismatch_blocks_parity(self):
        request = self.pilot()
        request['pilot']['replacement_argv'] = [sys.executable, '-c',
            "from pathlib import Path; Path('out.txt').write_text('different')"]
        failed = self.cli('migrate', 'verify-pilot', request, 'failed-pilot')
        self.assertFalse(failed['proof']['passed'])
        ref = {'run_id': 'r', 'proof_id': failed['proof']['proof_id'], 'requirement_ids': ['R1']}
        with self.assertRaises(WorkflowError):
            state = read_state(self.root)
            transact(self.root, state['version'], 'bad-parity', {'kind': 'domain.migrate.record-parity',
                'payload': {'request': {'increment_id': 'greetings', 'verified': ['P1'],
                                        'evidence': {'P1': ref}}}})
        passed = self.cli('migrate', 'verify-pilot', self.pilot(), 'passed-pilot')
        state = read_state(self.root)
        run = state['data']['runs']['r']
        run['items']['W1']['attempts'].append({'token': 'new', 'status': 'active'})
        transact(self.root, state['version'], 'new-attempt', {'kind': 'fixture',
                 'payload': {'runs': {'r': run}}})
        ref['proof_id'] = passed['proof']['proof_id']
        with self.assertRaises(WorkflowError):
            state = read_state(self.root)
            transact(self.root, state['version'], 'stale-parity', {'kind': 'domain.migrate.record-parity',
                'payload': {'request': {'increment_id': 'greetings', 'verified': ['P1'],
                                        'evidence': {'P1': ref}}}})


class DurableOutboxTests(unittest.TestCase):
    setUp=JournalIntegrationTests.setUp
    tearDown=JournalIntegrationTests.tearDown
    cli=JournalIntegrationTests.cli
    def seed_delivery(self):
        from workflow_lib.journal_domains import digest
        issue={'id':'i1','description':'human'}
        snap={'complete':True,'repo_id':'r','pages':[1],'expected_pages':1,'issues':[issue]}
        h=digest(snap)
        transact(self.root,0,'fixture',{'kind':'fixture','payload':{
            'issues':{'i1':{'id':'i1','original':issue,'fingerprint':digest(issue)}},
            'snapshots':{h:snap},'snapshot_hash':h,'snapshot_valid':True,
            'groups':[{'id':'g','issue_ids':['i1']}],
            'runs':{'run':{'id':'run','status':'delivered','issue_group_id':'g','issue_scope':{'snapshot_hash':h,'issue_ids':['i1'],'requirement_ids':{'i1':['R1']}},
                     'acceptances':[{'complete':True,'fresh':True,'requirements':[{'id':'R1','verdict':'MET'}]}],
                     'delivery':{'manifest_hash':'m','recorded_at':'2026-10-01T00:00:00Z'}}}}})
        return h
    def test_crash_after_external_receipt_reconciles_without_resending(self):
        from workflow_lib.outbox import retry_writes
        h=self.seed_delivery()
        result=self.cli('issues','authorize-write',{'run_id':'run','issue_id':'i1',
            'snapshot_hash':h,'manifest_hash':'m','operation_id':'comment',
            'action':'create-comment','actor_id':'human','requirement_ids':['R1'],
            'payload':{'issue_id':'i1','body':'done','ownership_marker':'devflow:run:i1'}},'approve')
        self.cli('issues','enqueue',{'authorization_id':result['authorization_id']},'enqueue')
        class Connector:
            calls=0
            receipt=None
            def reconcile(self,op): return self.receipt
            def send(self,op):
                self.calls+=1
                self.receipt={'receipt':'remote-123'}
                raise KeyboardInterrupt('crash after remote write')
        connector=Connector()
        with self.assertRaises(KeyboardInterrupt): retry_writes(self.root,connector)
        self.assertEqual(read_state(self.root)['data']['outbox']['comment']['status'],'dispatching')
        retry_writes(self.root,connector)
        retry_writes(self.root,connector)
        self.assertEqual(connector.calls,1)
        self.assertEqual(read_state(self.root)['data']['outbox']['comment']['receipt'],'remote-123')
    def test_operation_conflict_and_stale_version_commit_nothing(self):
        self.cli('issues','capture',{'issue':{'id':'i','description':'original'}},'capture')
        before=read_state(self.root)['version']
        args=[sys.executable,str(ENTRY),'issues','capture','--root',str(self.root),
              '--input',str(self.input),'--operation-id','capture']
        self.input.write_text(json.dumps({'issue':{'id':'i','description':'changed'}}))
        conflict=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(json.loads(conflict.stdout)['error'],'OPERATION_CONFLICT')
        stale=subprocess.run(args[:-1]+['new','--expected-version','0'],capture_output=True,text=True)
        self.assertEqual(json.loads(stale.stdout)['error'],'STALE_STATE')
        self.assertEqual(read_state(self.root)['version'],before)

class ExecutionIntegrationTests(unittest.TestCase):
    setUp=JournalIntegrationTests.setUp
    tearDown=JournalIntegrationTests.tearDown
    cli=JournalIntegrationTests.cli
    def seed_repo(self):
        self.repo=Path(self.temp.name)/'repo'; self.repo.mkdir()
        (self.repo/'app.py').write_text('x=1\n')
        subprocess.run(['git','init','-q'],cwd=self.repo,check=True)
        subprocess.run(['git','add','.'],cwd=self.repo,check=True)
        subprocess.run(['git','-c','user.name=fixture','-c','user.email=fixture@test','commit','-qm','base'],cwd=self.repo,check=True)
        transact(self.root,0,'fixture',{'kind':'fixture','payload':{'repositories':{'r':{'location':str(self.repo)}},
            'runs':{'run':{'id':'run','status':'active','plan':{'work_items':[{'id':'w','repo_id':'r'}]}}}}})
    def test_hardening_proofs_are_journaled_and_replay_does_not_execute(self):
        self.seed_repo()
        counter=Path(self.temp.name)/'count'
        command=[sys.executable,'-c',f"from pathlib import Path; p=Path({str(counter)!r}); p.write_text(str(int(p.read_text(encoding='utf-8'))+1) if p.exists() else '1')"]
        self.cli('harden','configure',{'run_id':'run','actor_id':'human','gates':{'security':{'repo_id':'r','command':command}}},'config')
        result=self.cli('harden','gate',{'run_id':'run','gate_id':'security'},'gate')
        self.assertTrue(result['proof']['passed'])
        self.cli('harden','gate',{'run_id':'run','gate_id':'security'},'gate')
        self.assertEqual(counter.read_text(encoding='utf-8'),'1')
        state=read_state(self.root)
        self.assertTrue(state['data']['runs']['run']['hardening_proofs']['security']['passed'])
    def test_structured_gate_replay_does_not_execute(self):
        self.seed_repo()
        counter=Path(self.temp.name)/'count'
        command=[sys.executable,'-c',f"from pathlib import Path; p=Path({str(counter)!r}); p.write_text(str(int(p.read_text(encoding='utf-8'))+1) if p.exists() else '1'); print('{{\"findings\":[]}}')"]
        self.cli('harden','configure',{'run_id':'run','actor_id':'human','gates':{'security':{
            'repo_id':'r','command':command,'contract':{'kind':'json-report','version':1}}}},'config')
        first=self.cli('harden','gate',{'run_id':'run','gate_id':'security'},'gate')
        second=self.cli('harden','gate',{'run_id':'run','gate_id':'security'},'gate')
        self.assertTrue(first['proof']['passed'])
        self.assertTrue(second['replayed'])
        self.assertEqual(counter.read_text(encoding='utf-8'),'1')
        attempt=next(iter(read_state(self.root)['data']['runs']['run']['hardening_attempts'].values()))
        self.assertEqual(first['proof']['contract_hash'],attempt['contract_hash'])
    def test_legacy_gate_config_remains_valid(self):
        self.seed_repo()
        command=[sys.executable,'-c','print("unstructured output")']
        self.cli('harden','configure',{'run_id':'run','actor_id':'human','gates':{'security':{'repo_id':'r','command':command}}},'config')
        result=self.cli('harden','gate',{'run_id':'run','gate_id':'security'},'gate')
        self.assertTrue(result['proof']['passed'])
        self.assertEqual(read_state(self.root)['data']['runs']['run']['hardening_config']['security']['contract'],{'kind':'exit-status'})
    def test_changed_contract_or_repository_invalidates_proof(self):
        from workflow_lib.gates import hardening_ready
        self.seed_repo()
        command=[sys.executable,'-c','print("{\\\"findings\\\":[]}")']
        gate={'repo_id':'r','command':command,'contract':{'kind':'json-report','version':1}}
        self.cli('harden','configure',{'run_id':'run','actor_id':'human','gates':{'security':gate}},'config')
        self.cli('harden','gate',{'run_id':'run','gate_id':'security'},'gate')
        self.assertTrue(hardening_ready(read_state(self.root)['data']['runs']['run']))
        (self.repo/'app.py').write_text('x=2\n')
        self.assertFalse(hardening_ready(read_state(self.root)['data']['runs']['run']))
        (self.repo/'app.py').write_text('x=1\n')
        self.cli('harden','configure',{'run_id':'run','actor_id':'human','gates':{'security':{
            'repo_id':'r','command':command,'contract':{'kind':'exit-status'}}}},'config2')
        self.assertFalse(hardening_ready(read_state(self.root)['data']['runs']['run']))
    def test_missing_report_blocks_delivery(self):
        from workflow_lib.gates import hardening_ready
        self.seed_repo()
        command=[sys.executable,'-c','pass']
        self.cli('harden','configure',{'run_id':'run','actor_id':'human','gates':{'security':{
            'repo_id':'r','command':command,'contract':{'kind':'json-report','version':1}}}},'config')
        result=self.cli('harden','gate',{'run_id':'run','gate_id':'security'},'gate')
        self.assertFalse(result['proof']['passed'])
        self.assertEqual(result['proof']['failure'],'REPORT_MISSING')
        self.assertFalse(hardening_ready(read_state(self.root)['data']['runs']['run']))
    def test_ingestion_persists_index_cache_and_provenance_for_equal_files(self):
        self.seed_repo()
        (self.repo/'copy.py').write_text('x=1\n')
        profile=Path(self.temp.name)/'profile.json'; profile.write_text(json.dumps({'extensions':['.py']}))
        args=[sys.executable,str(ENTRY),'ingest','--root',str(self.root),'--repo-id','r',
              '--scope','.','--profile-json',str(profile),'--operation-id','ingest']
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        data=read_state(self.root)['data']
        index=next(iter(data['source_indexes'].values()))
        self.assertEqual({s['path'] for s in index['sources']},{'app.py','copy.py'})
        self.assertTrue(data['ingestion_cache'])
        version=read_state(self.root)['version']
        subprocess.run(args,capture_output=True,text=True,check=True)
        self.assertEqual(read_state(self.root)['version'],version)
        (self.repo / 'app.py').write_text('source changed after indexed receipt')
        compact = subprocess.run([*args, '--output-mode', 'refs'], capture_output=True, text=True)
        self.assertEqual(compact.returncode, 0, compact.stdout + compact.stderr)
        projected = json.loads(compact.stdout)['index']
        self.assertNotIn('text', projected['sources'][0])
        inspected = subprocess.run([sys.executable, str(ENTRY), 'context-artifact', 'inspect', '--root', str(self.root),
                                    '--id', projected['artifact_id']], capture_output=True, text=True)
        self.assertEqual(inspected.returncode, 0, inspected.stdout + inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout), index)
        self.assertEqual(read_state(self.root)['version'], version)
    def test_metrics_use_delivery_acceptance_and_bound_usage_only(self):
        from workflow_lib.journal_domains import digest
        transact(self.root,0,'fixture',{'kind':'fixture','payload':{'runs':{
            'run':{'id':'run','status':'delivered','delivery':{'recorded_at':'2026-10-01T00:00:00Z'},
                'acceptances':[{'complete':True,'requirements':[{'id':'R1','verdict':'MET'}]}]},
            'pending':{'status':'active'}}}})
        row={'source_id':'s','event_id':'e','provider':'p','model':'m','input_tokens':100,'cached_tokens':10,'output_tokens':5}
        self.cli('stats','usage-import',[row],'usage',adapter_version='v1',bindings={'s:e':{'run_id':'run'}})
        self.cli('stats','expectations',{'events':[{'source_id':'s','event_id':'e','run_id':'run'}]},'expected')
        self.cli('stats','prices',{'version':'v1','source':{'timestamp':'2026-10-06T00:00:00Z'},'rates':{'p/m':{'input':1,'cached':.5,'output':2}}},'prices')
        report=self.cli('stats','metrics',{},'report',as_of='2026-11-01T00:00:00Z',price_version='v1')['report']
        self.assertEqual(report['run_ids'],['run']); self.assertEqual(report['accepted_requirements'],1)
        self.assertEqual(report['usage_coverage'],1); self.assertAlmostEqual(report['cost'],.000105)
        self.assertIn('pending',report['excluded_run_ids'])

class ReportingIntegrationTests(unittest.TestCase):
    def test_frozen_report_rollup_excludes_unpriced_denominators(self):
        from workflow_lib.reporting import rollup
        result=rollup([{'id':'a','cost':10,'accepted_requirements':2,'as_of':'2026-11-01T00:30:00+01:00'},
                       {'id':'b','cost':None,'accepted_requirements':100,'as_of':'2026-10-31T23:30:00Z'}],{'month':'2026-10'})
        self.assertEqual(result['eligible_run_ids'],['a'])
        self.assertEqual(result['excluded_run_ids'],['b'])
        self.assertEqual(result['ratio'],5)
    def test_nonfinite_usage_prices_fail_without_commit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with self.assertRaises(WorkflowError):
                transact(root,0,'nan',{'kind':'domain.stats.prices','payload':{'request':{
                    'version':'v','source':{'timestamp':'now'},'rates':{'p/m':{'input':float('nan'),'cached':0,'output':0}}}}})
            self.assertEqual(read_state(root)['version'],0)

class GateIntegrationTests(unittest.TestCase):
    setUp=JournalIntegrationTests.setUp
    tearDown=JournalIntegrationTests.tearDown
    cli=JournalIntegrationTests.cli
    seed_repo=ExecutionIntegrationTests.seed_repo
    def test_missing_or_stale_hardening_proof_blocks_delivery(self):
        from workflow_lib.gates import hardening_ready
        self.seed_repo()
        self.cli('harden','configure',{'run_id':'run','actor_id':'human','gates':{'security':{'repo_id':'r','command':[sys.executable,'-c','print("ok")']}}},'config')
        self.assertFalse(hardening_ready(read_state(self.root)['data']['runs']['run']))
        self.cli('harden','gate',{'run_id':'run','gate_id':'security'},'gate')
        self.assertTrue(hardening_ready(read_state(self.root)['data']['runs']['run']))
        (self.repo/'app.py').write_text('changed\n')
        self.assertFalse(hardening_ready(read_state(self.root)['data']['runs']['run']))
    def test_migration_binding_keeps_predecessor_delivery_guard(self):
        self.seed_repo()
        self.cli('migrate','store',{'increments':{'increments':[{'id':'a','depends_on':[],'criteria':['a']},{'id':'b','depends_on':['a'],'criteria':['b']}]},'parity':[{'id':'a'},{'id':'b'}]},'plan')
        self.cli('migrate','bind',{'run_id':'run','increment_id':'b'},'bind')
        from workflow_lib.journal_domains import migration_delivery_guard
        with self.assertRaises(WorkflowError): migration_delivery_guard(read_state(self.root)['data'],'run')

class ClassificationIntegrationTests(unittest.TestCase):
    setUp=JournalIntegrationTests.setUp
    tearDown=JournalIntegrationTests.tearDown
    cli=JournalIntegrationTests.cli
    seed_delivery=DurableOutboxTests.seed_delivery
    def test_confirmed_classifications_are_counted_once_within_delivery_window(self):
        h=self.seed_delivery()
        request={'issue_id':'i1','proposal':{'kind':'escaped-defect','run_id':'run','requirement_ids':['R1']}}
        proposed=self.cli('issues','classify',request,'proposal')
        confirmed={**request,'confirmed_hash':proposed['proposal_hash'],'actor_id':'human','confirmed_at':'2026-10-05T00:00:00Z'}
        self.cli('issues','classify',confirmed,'confirmation')
        self.cli('issues','classify',confirmed,'duplicate-confirmation')
        early=self.cli('stats','metrics',{},'early',as_of='2026-10-02T00:00:00Z')['report']
        later=self.cli('stats','metrics',{},'later',as_of='2026-11-01T00:00:00Z')['report']
        self.assertEqual(early['escaped_defects'],0)
        self.assertEqual(later['escaped_defects'],1)
        self.assertEqual(later['escaped_defect_rate'],1)
    def test_caller_cannot_authorize_updating_a_human_comment(self):
        h=self.seed_delivery()
        with self.assertRaises(WorkflowError):
            transact(self.root,1,'edit-human',{'kind':'domain.issues.authorize-write','payload':{'request':{
                'run_id':'run','issue_id':'i1','snapshot_hash':h,'manifest_hash':'m','operation_id':'edit',
                'action':'update-comment','actor_id':'human','requirement_ids':['R1'],
                'payload':{'issue_id':'i1','body':'overwrite','ownership_marker':'devflow:run:i1','remote_comment_id':'human-comment'}}}})


class SnapshotRollupTests(unittest.TestCase):
    def test_repriced_snapshots_do_not_count_a_delivered_run_twice(self):
        from workflow_lib.reporting import rollup
        old={'id':'old','run_ids':['r'],'cost':1,'accepted_requirements':1,'as_of':'2026-10-01T00:00:00Z'}
        new={**old,'id':'new','cost':2,'as_of':'2026-10-02T00:00:00Z'}
        result=rollup([old,new],{})
        self.assertEqual(result['ratio'],2)
        self.assertEqual(result['eligible_run_ids'],['new'])
        self.assertIn('old',result['excluded_run_ids'])

class ReportInspectionTests(unittest.TestCase):
    setUp=JournalIntegrationTests.setUp
    tearDown=JournalIntegrationTests.tearDown
    cli=JournalIntegrationTests.cli
    def test_frozen_report_exports_without_resubmitting_its_content(self):
        record=self.cli('stats','metrics',{},'report',as_of='2026-10-06T00:00:00Z')['report']
        result=subprocess.run([sys.executable,str(ENTRY),'stats','export','--root',str(self.root),
            '--options',json.dumps({'report_id':record['id'],'format':'json'})],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(json.loads(result.stdout)['output']),record)
        self.assertEqual(read_state(self.root)['version'],1)

if __name__=='__main__': unittest.main()
