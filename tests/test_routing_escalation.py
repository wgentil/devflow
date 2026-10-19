import copy
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
import test_model_policy as model_fixtures
import test_routing_receipts as receipt_fixtures
from workflow_lib.document_units import digest
from workflow_lib.hosts import apply_host_event
from workflow_lib.store import WorkflowError, transact, read_state


class RoutingEscalationTests(unittest.TestCase):
    def setUp(self):
        fixture=model_fixtures.ModelPolicyTests();fixture.setUp()
        self.policy=fixture.policy
        self.policy['task_routing']={'max_escalations':1,'escalation_routes':[{'profile':'deep-reasoning','effort':'high'}]}
        self.lineage={'lineage_id':'l','task_hash':'t','policy_hash':digest(self.policy),
            'configuration_hash':'c','host':'codex','stage':'implementation','count':0,
            'predecessor_invocation_id':'previous','current':{'model':'deep','effort':'medium'},
            'preferences':{'mode':'advisory'},'capabilities':{**fixture.cap,'observe':True},
            'discovery':fixture.discovery,'prices':None}
        self.auth={'approved':True,'actor_id':'human','lineage_id':'l','task_hash':'t',
            'policy_hash':digest(self.policy),'configuration_hash':'c','host':'codex',
            'stage':'implementation','max_escalations':1,'eligible_routes':[{'model':'deep','effort':'high'}]}
        self.failure={'kind':'reasoning','evidence_refs':['verification:failed'],'reason':'Unresolved diagnosis'}
    def plan(self, **changes):
        from workflow_lib.routing_escalation import plan_escalation
        return plan_escalation(self.policy,changes.get('lineage',self.lineage),
            changes.get('failure',self.failure),changes.get('authorization',self.auth))
    def test_one_scoped_authorized_successor_and_no_second_escalation(self):
        result=self.plan()
        self.assertEqual(result['status'],'eligible')
        self.assertEqual(result['candidate']['resolved'],{'provider':'openai','model':'deep','effort':'high'})
        self.assertEqual(result['escalation_index'],1)
        self.assertEqual(self.plan(lineage={**self.lineage,'count':1})['status'],'block')
        self.assertEqual(self.plan(authorization={})['status'],'recommendation')
    def test_operational_blockers_and_unknown_inputs_do_not_buy_more_reasoning(self):
        for kind in ('auth','quota','missing-input','configuration','approval','network'):
            with self.subTest(kind=kind):
                self.assertEqual(self.plan(failure={**self.failure,'kind':kind})['status'],'block')
        self.assertEqual(self.plan(failure={**self.failure,'evidence_refs':[]})['status'],'block')
        self.assertNotEqual(self.plan(authorization={**self.auth,'task_hash':'stale'})['status'],'eligible')
    def test_pins_allowlists_and_unknown_cost_are_not_cleared(self):
        for prefs in ({'pin':'different'},{'allowed_models':[]},{'effort':'medium'},{'max_cost':0.1}):
            with self.subTest(prefs=prefs):
                self.assertEqual(self.plan(lineage={**self.lineage,'preferences':{'mode':'advisory',**prefs}})['status'],'block')
        self.policy['task_routing']['escalation_routes']=[]
        self.assertEqual(self.plan()['status'],'block')
    def test_same_route_or_policy_attempt_to_clear_preferences_cannot_escalate(self):
        self.assertEqual(self.plan(lineage={**self.lineage,'current':{'model':'deep','effort':'high'}})['status'],'block')
        self.policy['task_routing']['escalation_routes'][0]['allowed_models']=['deep']
        lineage={**self.lineage,'policy_hash':digest(self.policy),'preferences':{'allowed_models':[]}}
        auth={**self.auth,'policy_hash':digest(self.policy)}
        self.assertEqual(self.plan(lineage=lineage,authorization=auth)['status'],'block')

    def test_changed_configuration_requires_a_fresh_authorization(self):
        self.assertEqual(self.plan(lineage={**self.lineage,'configuration_hash':'changed'})['status'],'recommendation')
    def test_journal_spends_allowance_once_and_survives_attempt_or_binding_changes(self):
        fixture=receipt_fixtures.RoutingReceiptTests();fixture.setUp()
        fixture.start()
        apply_host_event(fixture.state,'native-finish',{'binding_id':'b1','revision':1,'invocation_id':'i',
            'result':{'status':'interrupted','error_kind':'unavailable'}})
        routing=copy.deepcopy(fixture.routing)
        authorization={'approved':True,'actor_id':'human','lineage_id':routing['lineage_id'],
            'task_hash':routing['task_hash'],'policy_hash':routing['policy_hash'],
            'configuration_hash':'c','host':'codex','stage':'implementation','max_escalations':1,
            'eligible_routes':[{'model':'m','effort':'high'}]}
        routing.update(escalation_index=1,predecessor_invocation_id='i',
            escalation_authorization=authorization,escalation_evidence=self.failure,
            configuration_hash='c')
        req={'binding_id':'b1','revision':1,'invocation_id':'next','stage':'implementation',
            'request_hash':'next','policy_revision':0,'replacement_of':'i',
            'replacement_authorization':{'approved':True,'actor_id':'human'},
            'decision':{'status':'allow','mode':'advisory','resolved':{'model':'m','effort':'high'},'routing':routing}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            transact(root,0,'seed',{'kind':'fixture','payload':fixture.state})
            transact(root,1,'next',{'kind':'domain.host.native-start','payload':{'request':req}})
            with self.assertRaises(WorkflowError):
                transact(root,1,'concurrent',{'kind':'domain.host.native-start','payload':{'request':{**req,'invocation_id':'other'}}})
            state=read_state(root)['data']
            self.assertEqual(state['runs']['run']['routing_lineages'][routing['lineage_id']]['count'],1)

            apply_host_event(state,'native-finish',{'binding_id':'b1','revision':1,'invocation_id':'next',
                'result':{'status':'interrupted','error_kind':'unavailable'}})
            from workflow_lib.hosts import prepare_handoff,accept_handoff,invocation_scope
            from test_hosts import attachment
            prepare_handoff(state,{'binding_id':'b1','revision':1,'handoff_id':'h','target_host':'claude',
                                  'target_session_id':'s2','target_actor_id':'a2'})
            release=state['host_bindings']['b1']['release']
            destination=attachment(binding_id='b2',host='claude',session_id='s2',actor_id='a2')
            accept_handoff(state,{'handoff_id':'h','destination':destination},release,release,{'status':'allow'})
            state['runs']['run']['active_attempt']['token']='new-attempt'
            scope=invocation_scope(state['host_bindings']['b2'],state['runs']['run'],'implementation',{})
            for label in ('T1','new-label'):
                retry_routing=copy.deepcopy(routing)
                facts={**retry_routing['task_facts'],'actor_id':'a2','task_id':label}
                retry_routing.update(task_facts=facts,task_hash=digest(facts),scope_hash=digest(scope),
                    lineage_id=digest(['run',label,'implementation']),escalation_index=0)
                with self.subTest(label=label),self.assertRaises(WorkflowError) as caught:
                    apply_host_event(state,'native-start',{**req,'binding_id':'b2','invocation_id':'retry',
                        'decision':{**req['decision'],'routing':retry_routing}})
                self.assertEqual(caught.exception.code,'ESCALATION_CONFLICT')
