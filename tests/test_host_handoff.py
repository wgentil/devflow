import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from test_hosts import host_state, attachment
from workflow_lib.hosts import apply_host_event, prepare_handoff, accept_handoff, validate_binding
from workflow_lib.store import WorkflowError

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.state=host_state(); self.source=apply_host_event(self.state,'attach',attachment())
        self.release=self.source['release']
        self.envelope=prepare_handoff(self.state,{'binding_id':'b1','revision':1,'handoff_id':'h1','target_host':'claude','target_session_id':'s2','target_actor_id':'a2'})
        self.destination=attachment(binding_id='b2',host='claude',session_id='s2',actor_id='a2')
    def accept(self,source=None,destination=None,decision=None):
        return accept_handoff(self.state,{'handoff_id':'h1','destination':self.destination},source or self.release,destination or self.release,decision or {'status':'allow','mode':'advisory'})
    def test_preserve_token_and_invalidate_source(self):
        self.assertEqual(self.state['host_bindings']['b1']['status'],'active')
        result=self.accept();self.assertEqual(result['binding_id'],'b2')
        self.assertEqual(self.state['runs']['run']['active_attempt']['token'],'t')
        self.assertEqual(self.state['runs']['run']['implementer_actors'],['original','a1','a2'])
        with self.assertRaises(WorkflowError):validate_binding(self.state,'b1',1)
        with self.assertRaises(WorkflowError):self.accept()
    def test_mismatch_each_direction_preserves_owner(self):
        for field in ('plugin_version','fingerprint','host_protocol_version'):
            for side in ('source','destination'):
                with self.subTest(field=field,side=side):
                    changed={**self.release,field:'changed'}
                    with self.assertRaises(WorkflowError): self.accept(**{side:changed})
                    self.assertEqual(self.state['host_bindings']['b1']['status'],'active')
    def test_destination_strict_suitability_blocks(self):
        with self.assertRaises(WorkflowError):self.accept(decision={'status':'block','mode':'strict'})
        self.assertEqual(self.state['host_bindings']['b1']['status'],'active')
    def test_target_scope_and_source_revision(self):
        self.destination['actor_id']='wrong'
        with self.assertRaises(WorkflowError):self.accept()
        self.destination['actor_id']='a2'
        apply_host_event(self.state,'detach',{'binding_id':'b1','revision':1})
        with self.assertRaises(WorkflowError):self.accept()
    def test_detached_resume_cannot_bypass_parity(self):
        apply_host_event(self.state,'detach',{'binding_id':'b1','revision':1})
        changed={**self.release,'fingerprint':'changed'}
        with self.assertRaises(WorkflowError):apply_host_event(self.state,'attach',attachment(binding_id='b3',session_id='s3',release=changed))
    def test_explicit_compatible_refresh_preserves_history(self):
        release={**self.release,'fingerprint':'new','release_id':'new'}
        result=apply_host_event(self.state,'attach',attachment(refresh=True,revision=1,release=release))
        self.assertEqual(result['revision'],2);self.assertEqual(len(result['release_history']),2)
        self.assertEqual(self.state['runs']['run']['active_attempt']['token'],'t')
    def test_active_repair_blocks_handoff(self):
        self.state['runs']['run']['repair_cycles']=[{'cycle_id':'c','status':'claimed'}]
        with self.assertRaises(WorkflowError) as caught:self.accept()
        self.assertEqual(caught.exception.code,'REPAIR_LEASE_ACTIVE')
        self.assertEqual(self.state['host_bindings']['b1']['status'],'active')
