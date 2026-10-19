import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import test_interactive_routing as interactive_fixtures
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/workflow/scripts'))
from workflow_lib.document_units import canonical
from workflow_lib.store import WorkflowError,read_state


class RoutingContextTests(unittest.TestCase):
    def test_exact_unicode_payload_and_repeated_preload_measurement(self):
        from workflow_lib.interactive_routing import measure_delegation_payload
        content='Required 東京';key=hashlib.sha256(content.encode()).hexdigest()
        config={'description':'Scoped worker é'};prompt='Task context '+key
        unit={'id':'skill','content':content,'content_hash':key}
        value=measure_delegation_payload(config,prompt,[unit])
        self.assertEqual(value['configuration_bytes'],len(canonical(config)))
        self.assertEqual(value['turn_bytes'],len(prompt.encode()))
        self.assertEqual(value['preload_bytes'],len(canonical([unit])))
        self.assertEqual(value['known_payload_bytes'],len(canonical(config))+len(prompt.encode())+len(canonical([unit])))
        self.assertEqual(value['duplicate_content_bytes'],len(content.encode()))
    def setUp(self):
        self.fixture=interactive_fixtures.InteractiveRoutingTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
    def test_required_context_and_task_output_are_supplied_once(self):
        from workflow_lib.interactive_routing import prepare_delegation
        request={**self.fixture.request,'task':{**self.fixture.request['task'],'required_output':'UNIQUE_REQUIRED_OUTPUT'}}
        value=prepare_delegation(self.fixture.root,request,self.fixture.context)
        worker=value['worker_input'];text=worker['configuration_text']+worker['prompt']
        self.assertIn('UNIQUE_REQUIRED_OUTPUT',text)
        self.assertEqual(text.count('Fixture required behavior'),1)
        self.assertIn('completed_scope',text)
        self.assertGreater(value['known_payload']['known_payload_bytes'],worker['known_text_bytes'])
    def test_duplicate_or_unregistered_preloads_cannot_hide_behind_smaller_context(self):
        from workflow_lib.interactive_routing import prepare_delegation
        for content in ('Fixture required behavior','Unregistered instruction'):
            unit={'id':'extra','content':content,'content_hash':hashlib.sha256(content.encode()).hexdigest()}
            with self.subTest(content=content),self.assertRaises(WorkflowError):
                prepare_delegation(self.fixture.root,{**self.fixture.request,'preloaded_units':[unit]},self.fixture.context)
    def test_completed_text_without_required_scoped_report_is_partial(self):
        from workflow_lib.interactive_routing import dispatch_delegation
        bridge=interactive_fixtures.Bridge(self.fixture.context)
        bridge.collect=lambda handle:{'status':'completed','observed':{'provider':'openai','model':'candidate','effort':'high'},
            'observation_source':'host-invocation-metadata','output':'Done, trust me.'}
        result=dispatch_delegation(self.fixture.root,self.fixture.request,'unstructured',bridge)
        self.assertEqual(result['status'],'block');self.assertEqual(result['reason_code'],'WORKER_PARTIAL')
        self.assertEqual(read_state(self.fixture.root)['data']['runs']['run']['active_attempt']['token'],'t')
