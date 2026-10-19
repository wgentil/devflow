import copy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))


class HostRouteControlTests(unittest.TestCase):
    def evidence(self, **changes):
        return {'schema_version':1,'host_version':'2.1.299','source':'enclosing-host',
                'supported':True,'account_key':'account','configuration_hash':'config',
                'model_efforts':{'m':['low','medium','high'],'other':['high']},
                'overrides':{},'custom_agent':{},'spawn':{'model':'m','effort':'medium'},
                'agent_defaults':{},'parent':{'model':'m','effort':'high'}, **changes}
    def assess(self, host='claude', path='interactive-nonfork', evidence=None):
        from workflow_lib.host_route_controls import assess_route_controls
        return assess_route_controls(host,path,{'model':'m','effort':'medium'}, evidence or self.evidence())
    def test_claude_version_boundary_and_fork_support_are_separate(self):
        self.assertEqual(self.assess(evidence=self.evidence(host_version='2.1.291'))['status'],'unsupported')
        self.assertEqual(self.assess(evidence=self.evidence(host_version='2.1.292'))['status'],'compatible')
        self.assertEqual(self.assess(path='interactive-fork')['status'],'unsupported')
        self.assertEqual(self.assess(evidence=self.evidence(host_version=None))['status'],'unknown')
    def test_claude_environment_overrides_and_privacy(self):
        from workflow_lib.host_route_controls import collect_claude_overrides
        values=collect_claude_overrides({'CLAUDE_CODE_EFFORT_LEVEL':'high','SECRET':'password',
            'CLAUDE_CODE_SUBAGENT_MODEL':'other','CLAUDE_CODE_SUBAGENT_MODEL_FORCE':'1'})
        result=self.assess(evidence=self.evidence(overrides=values))
        self.assertEqual(result['status'],'conflict')
        self.assertEqual(result['effective'],{'model':'other','effort':'high'})
        self.assertNotIn('password',str(result));self.assertNotIn('SECRET',str(values))
    def test_codex_custom_agent_fields_win_and_effort_support_is_checked(self):
        ev=self.evidence(custom_agent={'model':'other','model_reasoning_effort':'high'})
        result=self.assess('codex',evidence=ev)
        self.assertEqual(result['status'],'conflict')
        self.assertEqual(result['effective'],{'model':'other','effort':'high'})
        result=self.assess('codex',evidence=self.evidence(custom_agent={'model':'other'}))
        self.assertEqual(result['status'],'unsupported')
    def test_unknown_and_caller_metadata_cannot_establish_host_controls(self):
        self.assertEqual(self.assess(evidence=self.evidence(source='caller'))['status'],'unknown')
        self.assertEqual(self.assess(evidence=self.evidence(configuration_hash=None))['status'],'unknown')
        self.assertEqual(self.assess(evidence=self.evidence(model_efforts={}))['status'],'unknown')
    def test_precedence_is_content_bound_and_does_not_mutate(self):
        ev=self.evidence();before=copy.deepcopy(ev)
        first=self.assess(evidence=ev)
        self.assertEqual(first['requested'],{'model':'m','effort':'medium'})
        self.assertEqual(ev,before)
        self.assertNotEqual(first['evidence_hash'],self.assess(evidence=self.evidence(configuration_hash='changed'))['evidence_hash'])
