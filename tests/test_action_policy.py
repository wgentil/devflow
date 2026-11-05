"""Policy decisions must fail closed without changing legacy contracts."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))


class ActionPolicyTests(unittest.TestCase):
    def policy(self):
        from workflow_lib import action_policy
        return action_policy

    def test_unknown_required_evidence_blocks(self):
        decision = self.policy().evaluate_action('delivery', {'run_id': 'r'},
            {'policy_version': 1, 'state_version': 4, 'required_evidence': ['acceptance'], 'evidence': {}})
        self.assertEqual(decision['status'], 'block')
        self.assertIn('acceptance', decision['blocker_ids'])

    def test_legacy_remains_inactive(self):
        self.assertEqual(self.policy().evaluate_action('delivery', {}, {})['status'], 'not-applicable')

    def test_unknown_policy_or_action_blocks(self):
        for action, version in [('delivery', 99), ('typo', 1)]:
            self.assertEqual(self.policy().evaluate_action(action, {}, {'policy_version': version})['status'], 'block')

    def test_binding_changes_with_state(self):
        p = self.policy()
        a = p.evaluate_action('delivery', {}, {'policy_version': 1, 'state_version': 1})
        b = p.evaluate_action('delivery', {}, {'policy_version': 1, 'state_version': 2})
        self.assertNotEqual(a['context_hash'], b['context_hash'])

    def test_adoption_requires_authorization_and_idle_workers(self):
        from workflow_lib.store import WorkflowError
        p = self.policy()
        run = {'id': 'r', 'state_version': 1, 'active_attempt': {'token': 't'}}
        with self.assertRaises(WorkflowError):
            p.adopt_enforcement(run, {'approved': True, 'actor_id': 'user', 'run_id': 'r', 'state_version': 1})
        run['active_attempt'] = None
        with self.assertRaises(WorkflowError):
            p.adopt_enforcement(run, {})

    def test_adoption_cannot_downgrade_or_erase_active_effect_authority(self):
        from workflow_lib.store import WorkflowError
        authorization={'approved':True,'actor_id':'user','run_id':'r','state_version':1}
        for fields in ({'effects':{'e':{'status':'launching'}}},
                       {'effects':{'e':{'status':'uncertain'}}},
                       {'enforcement':{'protocol':'devflow.python-enforcement/v2','policy_version':2}}):
            with self.subTest(fields=fields), self.assertRaises(WorkflowError):
                self.policy().adopt_enforcement({'id':'r','state_version':1,**fields},authorization)

    def test_direct_event_rejects_invalid_decision(self):
        from workflow_lib.journal_domains import reduce_event
        from workflow_lib.store import WorkflowError
        data = {'runs': {'r': {'id': 'r', 'state_version': 1}}}
        with self.assertRaises(WorkflowError):
            reduce_event(data, 'domain.enforcement.adopt', {'request': {'run_id': 'r',
                'authorization': {'approved': True, 'actor_id': 'human', 'run_id': 'r', 'state_version': 0}}}, 0)
        self.assertNotIn('enforcement', data['runs']['r'])

    def test_adoption_both_storage_formats_and_exact_replay(self):
        import tempfile
        from workflow_lib.store import transact, read_state
        from workflow_lib.sqlite_store import initialize_store
        from control_store_fixtures import legacy_root
        for initialize in (legacy_root, initialize_store):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / 'control'
                initialize(root)
                transact(root, 0, 'seed', {'kind': 'fixture', 'payload': {'runs': {
                    'r': {'id': 'r', 'state_version': 1, 'reviews': {'item': [{'fresh': True}]}}}}})
                event = {'kind': 'domain.enforcement.adopt', 'payload': {'request': {'run_id': 'r',
                    'authorization': {'approved': True, 'actor_id': 'fixture-human', 'run_id': 'r', 'state_version': 1}}}}
                transact(root, 1, 'adopt', event)
                self.assertTrue(transact(root, 0, 'adopt', event)['replayed'])
                run = read_state(root)['data']['runs']['r']
                self.assertEqual(run['enforcement']['policy_version'], 1)
                self.assertFalse(run['reviews']['item'][0]['fresh'])
                self.assertEqual(run['state_version'], 2)
    def test_malformed_or_unbounded_decision_context_is_rejected(self):
        from workflow_lib.store import WorkflowError
        for context in ({'policy_version':1,'required_evidence':'not-a-list'},
                        {'policy_version':1,'evidence':[]},
                        {'policy_version':1,'payload':'x'*1000000}):
            with self.assertRaises(WorkflowError):self.policy().evaluate_action('delivery',{},context)
    def test_legacy_subject_does_not_parse_unadopted_extension_records(self):
        from workflow_lib.action_policy import subject_decision
        subject={'clarifications':{'extension-record':{'status':'pending'}}}
        self.assertEqual(subject_decision(subject,'delivery',{})['status'],'not-applicable')
    def test_old_extension_using_policy_version_is_not_silent_adoption(self):
        from workflow_lib.action_policy import subject_decision
        old_profile={'policy_version':1}
        subject={'enforcement':old_profile,'clarifications':{'opaque':{'status':'pending'}}}
        self.assertEqual(subject_decision(subject,'delivery',{})['status'],'not-applicable')
    def test_generic_event_cannot_remove_an_adopted_contract(self):
        import tempfile
        from workflow_lib.store import transact,read_state,WorkflowError
        from workflow_lib.sqlite_store import initialize_store
        from control_store_fixtures import legacy_root
        for initialize in (legacy_root,initialize_store):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)/'control';initialize(root)
                transact(root,0,'seed',{'kind':'fixture','payload':{'runs':{'r':{'id':'r','status':'active','state_version':0}}}})
                transact(root,1,'adopt',{'kind':'domain.enforcement.adopt','payload':{'request':{'run_id':'r','authorization':{
                    'approved':True,'actor_id':'fixture-user','run_id':'r','state_version':0}}}})
                with self.assertRaises(WorkflowError):
                    transact(root,2,'bypass',{'kind':'note','payload':{'runs':{'r':{'id':'r','status':'active','state_version':0}}}})
                self.assertEqual(read_state(root)['data']['runs']['r']['enforcement']['policy_version'],1)

    def test_opaque_legacy_metadata_does_not_block_original_finding_resolution(self):
        from workflow_lib.store import _apply_event
        state={'data':{'runs':{'r':{'id':'r','enforcement':{'extension':'older metadata'},
            'unresolved_findings':[{'id':'f'}]}}}}
        _apply_event(state,{'kind':'finding.resolved','payload':{'run_id':'r','finding_id':'f',
            'resolution':{'actor_id':'fixture-author','why':'legacy evidence','evidence_refs':['fixture-proof']}}})
        self.assertEqual(state['data']['runs']['r']['unresolved_findings'][0]['status'],'resolved')
