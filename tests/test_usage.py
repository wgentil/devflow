import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.usage import import_usage, usage_coverage
class UsageTests(unittest.TestCase):
 def test_duplicate_shared_agent_records(self):
  rec=[{'source_id':'s','event_id':'e','provider':'openai','model':'m','input_tokens':10,'cached_tokens':2,'output_tokens':3}]
  out=import_usage(rec+rec,'v1',{}); self.assertEqual(len(out['events']),1)
 def test_missing_unsupported_and_unbound(self):
  out=import_usage([{'source_id':'s','event_id':'e','x':1}],'bad',{}); self.assertFalse(out['complete']); self.assertTrue(out['gaps'])
 def test_partial_backfill_idempotency(self):
  rec=[{'source_id':'s','event_id':'e','provider':'p','model':'m','input_tokens':1,'cached_tokens':0,'output_tokens':0}]; a=import_usage(rec,'v1',{}); b=import_usage(rec+rec,'v1',{}); self.assertEqual(a['events'],b['events'])
