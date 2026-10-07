"""Independent-review regressions for durable integration boundaries."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.journal_domains import reduce_event, digest, migration_delivery_guard
from workflow_lib.store import WorkflowError

class IntegrationReviewTests(unittest.TestCase):
    def event(self, data, kind, request):
        return reduce_event(data, 'domain.' + kind, {'request': request}, 9)
    def delivered(self, identifier):
        return {'id':identifier,'status':'delivered','delivery':{'recorded_at':'2026-10-01T00:00:00Z','manifest_hash':'m'},
                'acceptances':[{'complete':True,'requirements':[{'id':'R','verdict':'MET'}]}]}
    def test_coverage_is_per_run_and_excludes_unavailable_denominator(self):
        data={'runs':{r:self.delivered(r) for r in ('A','B')},'usage_expectations':[],
              'usage':{'events':[]},'prices':{'p':{'rates':{'p/m':{'input':1,'cached':0,'output':0}}}}}
        for i in range(10):
            data['usage_expectations'].append({'run_id':'A','source_id':'s','event_id':str(i)})
            data['usage']['events'].append({'binding':{'run_id':'A'},'source_id':'s','event_id':str(i),
               'provider':'p','model':'m','input_tokens':1000000,'cached_tokens':0,'output_tokens':0})
        data['usage_expectations'].append({'run_id':'B','source_id':'s','event_id':'missing'})
        report=self.event(data,'stats.metrics',{'as_of':'2026-11-01T00:00:00Z','price_version':'p'})['report']
        self.assertIsNone(report['cost'])
        self.assertEqual(report['cost_excluded_run_ids'],['B'])
        self.assertEqual(report['cost_denominator'],1)
        self.assertEqual(report['priced_cost'],10)
        from workflow_lib.reporting import rollup
        self.assertEqual(rollup([report], {})['ratio'],10)
    def test_issue_run_freezes_per_issue_scope(self):
        snap={'complete':True,'repo_id':'r','issues':[{'id':'I'}]}; h=digest(snap)
        data={'snapshots':{h:snap},'snapshot_hash':h,'snapshot_valid':True,'issues':{'I':{'fingerprint':digest({'id':'I'})}},
              'groups':[{'id':'g','issue_ids':['I'],'requirement_ids':{'I':['R']}}],
              'plan':{'work_items':[]}}
        # Capture intent preserves the immutable group scope without needing a build plan.
        result=self.event(data,'issues.start',{'group_id':'g','snapshot_hash':h,'intent':'capture'})
        data['groups'][0]['issue_ids']=['other']
        self.assertEqual(data['issue_runs'][result['run_id']]['issue_ids'],['I'])
        self.assertEqual(result['requirement_ids'],{'I':['R']})
    def test_import_rejects_conflicts_and_impossible_cached_counts(self):
        row={'source_id':'s','event_id':'e','provider':'p','model':'m','input_tokens':1,'cached_tokens':0,'output_tokens':0}
        for rows in ([row,{**row,'input_tokens':2}],[{**row,'cached_tokens':100}]):
            with self.assertRaises(WorkflowError): self.event({},'stats.usage-import',{'records':rows})
    def test_report_rejects_cross_run_expectation_binding_and_usage_gaps(self):
        data={'runs':{r:self.delivered(r) for r in ('A','B')},
              'usage_expectations':[{'run_id':'A','source_id':'s','event_id':'e'}],
              'usage':{'gaps':['conflicting shared event'],'events':[{'binding':{'run_id':'B'},'source_id':'s','event_id':'e','provider':'p','model':'m','input_tokens':1,'cached_tokens':0,'output_tokens':0}]},
              'prices':{'p':{'rates':{'p/m':{'input':1,'cached':0,'output':0}}}}}
        report=self.event(data,'stats.metrics',{'as_of':'2026-11-01T00:00:00Z','price_version':'p'})['report']
        self.assertIsNone(report['cost'])
    def test_parity_requires_bound_final_current_scoped_proof_and_retains_refs(self):
        migration={'hash':'h','increments':{'increments':[{'id':'A','criteria':['c'],'depends_on':[]}]},'criteria':[{'id':'c','requirement_ids':['R']}],'parity':[]}
        run={'id':'r','migration_increment_id':'A','items':{'W':{'attempts':[{'token':'t'}]}},
            'plan':{'work_items':[{'id':'W','kind':'code','requirement_ids':['R']}]},
            'verification_proofs':{'p':{'kind':'code','phase':'GREEN','passed':True,'fresh':True,'item_id':'W','token':'t'}},
            'verifier_proofs':{'p':{'passed':True,'item_id':'W','token':'t','evidence_id':'p'}}}
        req={'increment_id':'A','verified':['c'],'evidence':{'c':{'run_id':'r','proof_id':'p','requirement_ids':['R']}}}
        for change in ('unbound','RED','old','scope'):
            data={'migration':deepcopy(migration),'runs':{'r':deepcopy(run)}}
            if change=='unbound': data['runs']['r'].pop('migration_increment_id')
            if change=='RED': data['runs']['r']['verification_proofs']['p']['phase']='RED'
            if change=='old': data['runs']['r']['verification_proofs']['p']['token']='old'
            bad=deepcopy(req)
            if change=='scope': bad['evidence']['c']['requirement_ids']=['other']
            with self.assertRaises(WorkflowError): self.event(data,'migrate.record-parity',bad)
        data={'migration':deepcopy(migration),'runs':{'r':run}}
        self.event(data,'migrate.record-parity',req)
        self.assertEqual(data['migration']['parity'][0]['evidence'],req['evidence'])
    def test_migration_delivery_cannot_borrow_or_overwrite(self):
        data={'migration':{'increments':{'increments':[{'id':'A','criteria':[],'depends_on':[]}]},'parity':[{'increment_id':'A','verified':[]}]},'runs':{'r':self.delivered('r')}}
        with self.assertRaises(WorkflowError): self.event(data,'migrate.delivered',{'increment_id':'A','run_id':'r'})
        data['runs']['r']['migration_increment_id']='A'
        data['migration']['deliveries']={'A':{'run_id':'other','manifest_hash':'old'}}
        with self.assertRaises(WorkflowError): migration_delivery_guard(data,'r')
    def test_regrouping_cannot_retarget_delivered_issue_scope(self):
        snap={'complete':True,'repo_id':'r','issues':[{'id':'I2'}]}; h=digest(snap)
        run=self.delivered('r');run['issue_group_id']='g'
        run['issue_scope']={'snapshot_hash':'old','issue_ids':['I1'],'requirement_ids':{'I1':['R']}}
        data={'runs':{'r':run},'snapshots':{h:snap},'snapshot_hash':h,'issues':{'I2':{'fingerprint':digest({'id':'I2'})}},'groups':[{'id':'g','issue_ids':['I2']}]}
        req={'run_id':'r','issue_id':'I2','snapshot_hash':h,'manifest_hash':'m','actor_id':'human','operation_id':'close','action':'close-issue','requirement_ids':['R'],'payload':{'issue_id':'I2','ownership_marker':'devflow:r:I2'}}
        with self.assertRaises(WorkflowError): self.event(data,'issues.authorize-write',req)
    def test_outbox_identity_includes_action_authorization_and_manifest(self):
        from workflow_lib.outbox import enqueue_write
        payload={'issue_id':'I','ownership_marker':'marker'}
        first={'approved':True,'manifest_hash':'m','operation_id':'same','payload_hash':digest(payload),'action':'create-comment'}
        second={**first,'action':'close-issue'}
        data={'write_authorizations':{'a':first,'b':second}}
        data=enqueue_write(data,'m',{'id':'same','authorization_id':'a','payload':payload})
        data['outbox']['same'].update(status='sent',receipt='COMMENT')
        with self.assertRaises(ValueError): enqueue_write(data,'m',{'id':'same','authorization_id':'b','payload':payload})
    def test_same_content_indexes_preserve_repository_identity(self):
        data={'repositories':{'A':{},'B':{}}}
        index={'fingerprint':'content','sources':[],'cache_hit':False}
        ids=[]
        for r in ('A','B'):
            ids.append(self.event(data,'ingest.record',{'repo_id':r,'index':index,'cache':{},'repository_fingerprint':{},'profile':{},'scope':[]})['index_id'])
        self.assertNotEqual(*ids)
        for r in ('A','B'): self.assertEqual(data['source_indexes'][data['current_source_indexes'][r]]['repo_id'],r)
    def test_classification_uses_effective_revision_before_run_selection(self):
        c=lambda r,at:{'issue_id':'I','confirmed':True,'confirmed_at':at,'proposal':{'run_id':r,'kind':'escaped-defect'}}
        data={'runs':{r:self.delivered(r) for r in ('A','B')},'classifications':[c('A','2026-10-02T00:00:00Z'),c('B','2026-10-03T00:00:00Z')]}
        self.assertEqual(self.event(data,'stats.metrics',{'as_of':'2026-11-01T00:00:00Z'})['report']['escaped_defects'],1)
        self.assertEqual(self.event(data,'stats.metrics',{'as_of':'2026-11-01T00:00:00Z','run_ids':['A']})['report']['escaped_defects'],0)
    def test_rollup_uses_utc_and_latest_revision_for_ties(self):
        from workflow_lib.reporting import rollup
        old={'id':'old','run_ids':['r'],'as_of':'2026-10-01T01:00:00+01:00','cost':1,'accepted_requirements':1,'source_version':1}
        new={**old,'id':'new','as_of':'2026-10-01T00:00:00Z','cost':9,'source_version':2}
        self.assertEqual(rollup([old,new],{})['ratio'],9)

import test_delivery
class ReplayIntegrationTests(unittest.TestCase):
    setUp=test_delivery.DeliveryTests.setUp
    tearDown=test_delivery.DeliveryTests.tearDown
    git=test_delivery.DeliveryTests.git
    repos=test_delivery.DeliveryTests.repos
    def test_delivery_replay_does_not_read_live_repositories(self):
        from workflow_lib.delivery import prepare_delivery, verify_delivery, record_delivery
        from workflow_lib.evidence import repository_fingerprint
        from workflow_lib.store import transact, read_state
        self.run.update(repositories={'repo-1':{'location':str(self.repo)}},required_hardening_gates=['security'],hardening_config_hash='cfg',hardening_proofs={'security':{'passed':True,'config_hash':'cfg','repo_id':'repo-1','repository_fingerprint':repository_fingerprint(self.repo)}})
        manifest=prepare_delivery(self.run,self.repos(),'local-merge')
        checked=verify_delivery(self.run,manifest,manifest['manifest_hash'],self.repos())
        actual={'authorization':{'approved':True,'actor_id':'human','manifest_hash':manifest['manifest_hash'],'action':'delivery.local-merge'},'outcome':'local-merge','repository_heads':{'repo-1':self.head},'merge_commits':{'repo-1':self.head}}
        terminal=record_delivery(self.run,checked,actual)
        root=Path(self.temp.name)/'control'
        transact(root,0,'fixture',{'kind':'fixture','payload':{'runs':{'run-1':self.run}}})
        transact(root,1,'delivery',{'kind':'delivery.recorded','payload':{'run_id':'run-1','delivery':terminal['delivery']}})
        (self.repo/'app.py').write_text('later change\n')
        with patch('subprocess.run',side_effect=AssertionError('replay cannot execute git')):
            self.assertEqual(read_state(root)['data']['runs']['run-1']['status'],'delivered')
        self.repo.rename(self.repo.with_name('relocated'))
        self.assertEqual(read_state(root)['data']['runs']['run-1']['status'],'delivered')
