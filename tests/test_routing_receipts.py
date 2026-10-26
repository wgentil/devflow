import copy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from test_hosts import host_state, attachment
from test_task_routing import task
from workflow_lib.hosts import apply_host_event, invocation_scope
from workflow_lib.document_units import digest
from workflow_lib.store import WorkflowError


class RoutingReceiptTests(unittest.TestCase):
    def setUp(self):
        self.state=host_state();apply_host_event(self.state,'attach',attachment())
        self.binding=self.state['host_bindings']['b1']
        self.scope=invocation_scope(self.binding,self.state['runs']['run'],'implementation',{})
        facts=task(actor_id='a1')
        self.routing={'routing_schema_version':1,'task_facts':facts,'task_hash':digest(facts),
            'policy_hash':'a'*64,'lineage_id':digest(['run','T1','implementation']),
            'scope_hash':digest(self.scope),'execution_path':'isolated-native',
            'classification_origin':'plan','reasons':['BOUNDED_IMPLEMENTATION'],'controls':{'status':'unknown'}}
    def start(self, routing=None):
        return apply_host_event(self.state,'native-start',{'binding_id':'b1','revision':1,
            'invocation_id':'i','stage':'implementation','request_hash':'request','policy_revision':0,
            'decision':{'status':'allow','mode':'advisory','resolved':{'provider':'openai','model':'m','effort':'medium'},
                        'routing':copy.deepcopy(self.routing if routing is None else routing)}})
    def test_receipt_retains_routing_and_bound_observations(self):
        self.start()
        receipt=apply_host_event(self.state,'native-finish',{'binding_id':'b1','revision':1,'invocation_id':'i',
            'result':{'status':'completed','observed':{'provider':'openai','model':'m','effort':'medium'},
             'observation_source':'host-effective-configuration'}})
        self.assertEqual(receipt['routing'],self.routing)
        self.assertEqual(receipt['scope']['token'],'t')
    def test_stale_task_hash_scope_or_origin_cannot_start(self):
        for change in ({'task_hash':'b'*64},{'scope_hash':'b'*64},{'classification_origin':'user'},
                       {'task_facts':task(actor_id='different')},{'lineage_id':'c'*64}):
            with self.subTest(change=change),self.assertRaises(WorkflowError):
                self.start({**self.routing,**change})
        self.assertFalse(self.state['runs']['run'].get('native_invocations'))
    def test_portable_receipt_cannot_claim_new_trusted_interactive_evidence(self):
        receipt={'invocation_id':'claimed','stage':'implementation','routing':self.routing,
                 'observed':{'model':'m','effort':'medium'},'observation_source':'host-effective-configuration'}
        with self.assertRaises(WorkflowError):
            apply_host_event(self.state,'model-receipt',{'binding_id':'b1','revision':1,'receipt':receipt})
    def test_partial_output_and_scope_mismatch_never_become_completed(self):
        from workflow_lib.routing_receipts import normalize_worker_outcome
        value={'status':'completed','scope':self.scope,'completed_scope':['W1'],
               'evidence_refs':['proof:run:W1:t'],'unresolved_facts':[]}
        self.assertEqual(normalize_worker_outcome(value,self.scope)['status'],'completed')
        for change in ({'status':'partial'},{'evidence_refs':[]},{'unresolved_facts':['Missing R1']},
                       {'scope':{**self.scope,'token':'old'}},{'completed_scope':[]}):
            with self.subTest(change=change):
                self.assertNotEqual(normalize_worker_outcome({**value,**change},self.scope)['status'],'completed')
    def test_partial_native_result_blocks_new_routed_receipt(self):
        self.start()
        receipt=apply_host_event(self.state,'native-finish',{'binding_id':'b1','revision':1,'invocation_id':'i',
            'result':{'status':'partial','observed':{'provider':'openai','model':'m','effort':'medium'},
                      'observation_source':'host-effective-configuration'}})
        self.assertEqual(receipt['status'],'block')
        self.assertEqual(receipt['reason_code'],'WORKER_PARTIAL')
        self.assertEqual(self.state['runs']['run']['active_attempt']['token'],'t')

    def test_routed_journal_replays_exact_metadata_without_host_io(self):
        import tempfile
        from unittest.mock import patch
        from workflow_lib.store import transact, read_state
        seed=copy.deepcopy(self.state)
        record=self.start()
        with tempfile.TemporaryDirectory() as temp:
            from control_store_fixtures import legacy_root
            root=legacy_root(Path(temp))
            transact(root,0,'seed',{'kind':'fixture','payload':seed})
            event={'kind':'domain.host.native-start','payload':{'request':record}}
            committed=transact(root,1,'start',event)
            expected=committed['state']['data']['runs']['run']['native_invocations']['i']
            (root/'state.json').unlink()
            with patch('subprocess.run',side_effect=AssertionError('replay must not launch host')):
                replayed=read_state(root)
            self.assertEqual(replayed['data']['runs']['run']['native_invocations']['i'],expected)
            self.assertTrue(transact(root,1,'start',event)['replayed'])
            with self.assertRaises(WorkflowError):
                transact(root,2,'changed-start',{'kind':event['kind'],'payload':{'request':{**record,'request_hash':'changed'}}})
