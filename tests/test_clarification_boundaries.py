"""Business ambiguity blocks affected work, not independent diagnostics."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/workflow/scripts'))
from workflow_lib.store import WorkflowError


class ClarificationTests(unittest.TestCase):
    def api(self):
        from workflow_lib import clarifications
        return clarifications

    def subject(self):
        return {'id': 'r', 'state_version': 1, 'enforcement': {'protocol':'devflow.python-enforcement/v1', 'policy_version': 1},
                'plan': {'spec_hash': 'spec', 'work_items': [
                    {'id': 'a', 'dependencies': []}, {'id': 'b', 'dependencies': ['a']},
                    {'id': 'c', 'dependencies': []}]}}

    def question(self, scope=None):
        return {'id': 'q', 'text': 'Which retention rule?', 'scope': scope,
                'source_identity': 'source', 'spec_hash': 'spec'}

    def test_unknown_impact_blocks_shared_work(self):
        api = self.api(); subject = api.record_question(self.subject(), self.question())
        self.assertTrue(api.clarification_blockers(subject, {'item_id': 'c'}))

    def test_unrelated_item_continues(self):
        api = self.api(); subject = api.record_question(self.subject(), self.question(['a']))
        self.assertTrue(api.clarification_blockers(subject, {'item_id': 'b'}))
        self.assertFalse(api.clarification_blockers(subject, {'item_id': 'c'}))
        self.assertTrue(api.clarification_blockers(subject, {}))

    def test_stale_or_conflicting_answer_blocks(self):
        api = self.api(); subject = api.record_question(self.subject(), self.question(['a']))
        answer = {'id': 'q', 'question_version': 99, 'answer': '30 days', 'actor_id': 'fixture-user',
                  'provenance': {'kind': 'user-message', 'ref': 'fixture-message'}, 'spec_hash': 'spec', 'material': False}
        with self.assertRaises(WorkflowError): api.record_answer(subject, answer)
        answer['question_version'] = 1
        answered = api.record_answer(subject, answer)
        self.assertFalse(api.clarification_blockers(answered, {'item_id': 'a'}))
        answer['answer'] = '60 days'
        with self.assertRaises(WorkflowError): api.record_answer(answered, answer)

    def test_unclassified_answer_is_retained_but_does_not_authorize_fix(self):
        api=self.api();subject=api.record_question(self.subject(),self.question(['a']))
        answer={'id':'q','question_version':1,'answer':'Thirty days.','actor_id':'fixture-user',
                'provenance':{'kind':'user-message','ref':'fixture-message'},'spec_hash':'spec'}
        updated=api.record_answer(subject,answer)
        self.assertEqual(updated['clarifications']['q']['answer']['answer'],'Thirty days.')
        self.assertTrue(api.clarification_blockers(updated,{'item_id':'a'}))

    def test_material_answer_requires_spec_approval(self):
        api = self.api(); subject = api.record_question(self.subject(), self.question(['a']))
        answer = {'id': 'q', 'question_version': 1, 'answer': '30 days', 'actor_id': 'fixture-user',
                  'provenance': {'kind': 'user-message', 'ref': 'fixture-message'}, 'spec_hash': 'new',
                  'material': True}
        subject = api.record_answer(subject, answer)
        self.assertTrue(api.clarification_blockers(subject, {'item_id': 'a'}))

    def test_review_binding_exposes_actual_scoped_question_and_user_answer(self):
        from workflow_lib.review_enforcement import review_bindings
        api=self.api();subject=api.record_question(self.subject(),self.question(['a']))
        answer={'id':'q','question_version':1,'answer':'Thirty days.','actor_id':'fixture-user',
                'provenance':{'kind':'user-message','ref':'fixture-message'},'spec_hash':'spec','material':False}
        subject=api.record_answer(subject,answer)
        binding=review_bindings(subject,'item','a')
        self.assertEqual(binding['logical']['question_answers'][0]['answer'],answer)
        self.assertEqual(review_bindings(subject,'item','c')['logical']['question_answers'],[])

    def test_question_after_prepare_blocks_launch(self):
        from workflow_lib.action_policy import subject_decision, require_action
        api = self.api(); subject = self.subject()
        before = subject_decision(subject, 'dispatch', {'item_id': 'a'})
        subject = api.record_question(subject, self.question(['a']))
        with self.assertRaises(WorkflowError): require_action(subject_decision(subject, 'dispatch', {'item_id': 'a'}))
        self.assertNotEqual(before['context_hash'], subject_decision(subject, 'dispatch', {'item_id': 'a'})['context_hash'])
        require_action(subject_decision(subject, 'review-report', {'item_id': 'a'}))

    def test_question_during_work_blocks_acceptance(self):
        from workflow_lib.action_policy import subject_decision
        api = self.api(); subject = api.record_question(self.subject(), self.question(['a']))
        for action in ('proof', 'completion', 'delivery', 'attempt', 'finding'):
            self.assertEqual(subject_decision(subject, action, {'item_id': 'a'})['status'], 'block')

    def test_actual_attempt_and_direct_event_blocked(self):
        from workflow_lib.runs import issue_attempt
        from workflow_lib.store import _apply_event
        api = self.api(); subject = self.subject()
        subject.update(status='active', items={i: {'status': 'pending', 'attempts': []} for i in ('a','b','c')}, active_attempt=None)
        subject = api.record_question(subject, self.question(['a']))
        with self.assertRaises(WorkflowError): issue_attempt(subject, 'a')
        state = {'data': {'runs': {'r': subject}}}
        with self.assertRaises(WorkflowError):
            _apply_event(state, {'kind': 'run.attempt.issued', 'payload': {'run_id': 'r',
                'attempt': {'item_id': 'a', 'token': 't', 'state_version': subject['state_version']+1}}})

    def test_question_invalidates_affected_evidence_and_preserves_independent_tokens(self):
        api=self.api();subject=self.subject()
        subject['verification_proofs']={i:{'item_id':i,'passed':True,'fresh':True} for i in ('a','b','c')}
        subject['verifier_proofs']={i:{'item_id':i,'passed':True,'fresh':True} for i in ('a','b','c')}
        subject['reviews']={'item':[{'item_id':'a','fresh':True},{'item_id':'c','fresh':True}]}
        subject['acceptances']=[{'fresh':True}]
        updated=api.record_question(subject,self.question(['a']))
        self.assertFalse(updated['verifier_proofs']['a']['passed'])
        self.assertFalse(updated['verifier_proofs']['b']['passed'])
        self.assertTrue(updated['verifier_proofs']['c']['passed'])
        self.assertTrue(updated['verification_proofs']['a']['passed'])
        self.assertFalse(updated['verification_proofs']['a']['fresh'])
        self.assertFalse(updated['reviews']['item'][0]['fresh'])
        self.assertTrue(updated['reviews']['item'][1]['fresh'])
        self.assertFalse(updated['acceptances'][0]['fresh'])
        self.assertEqual(updated['state_version'],subject['state_version'])
        self.assertTrue(subject['verifier_proofs']['a']['passed'])

    def test_direct_attempt_event_cannot_skip_dependencies_or_reopen_completed_item(self):
        from workflow_lib.store import _apply_event
        import copy
        base=self.subject()
        base.update(status='active',active_attempt=None,
            items={i:{'status':'pending','attempts':[]} for i in ('a','b','c')})
        for item_id, complete in (('b',False),('a',True)):
            subject=copy.deepcopy(base)
            if complete: subject['items']['a']['status']='complete'
            with self.subTest(item=item_id), self.assertRaises(WorkflowError):
                _apply_event({'data':{'runs':{'r':subject}}},{'kind':'run.attempt.issued',
                    'payload':{'run_id':'r','attempt':{'item_id':item_id,'token':'fresh',
                        'state_version':2,'status':'active','result':None}}})
