import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.outbox import enqueue_write, retry_writes
class OutboxTests(unittest.TestCase):
 def test_partial_external_failure_and_retry(self):
  import hashlib,json
  payload={'comment':'generated'}; digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
  authorization={'approved':True,'manifest_hash':'approved','operation_id':'op','payload_hash':digest}
  state=enqueue_write({'write_authorizations':{'a':authorization}},'approved',{'id':'op','payload':payload,'authorization_id':'a'}); adapter=type('A',(),{'send':lambda self,op:{'receipt':'r1'}})(); result=retry_writes(state,adapter); again=retry_writes(result,adapter); self.assertEqual(again['outbox']['op']['receipt'],'r1')
  calls=[]
  class Uncertain:
   def send(self,op): calls.append('send'); return {}
   def reconcile(self,op): return None
  uncertain=retry_writes(state,Uncertain()); retry_writes(uncertain,Uncertain()); self.assertEqual(calls,['send'])
