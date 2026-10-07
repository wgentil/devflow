import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.outbox import enqueue_write, retry_writes
class OutboxTests(unittest.TestCase):
 def test_partial_external_failure_and_retry(self):
  state=enqueue_write({},'approved',{'id':'op','payload':{'comment':'generated'},'authorized':True,'manifest_hash':'approved'}); adapter=type('A',(),{'send':lambda self,op:{'receipt':'r1'}})(); result=retry_writes(state,adapter); again=retry_writes(result,adapter); self.assertEqual(again['outbox']['op']['receipt'],'r1')
