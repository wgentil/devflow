import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.outbox import enqueue_write, retry_writes
class OutboxTests(unittest.TestCase):
 def test_enqueue_binds_authorization_and_preserves_generated_payload(self):
  import hashlib,json
  payload={'comment':'generated'}
  digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
  authorization={'approved':True,'manifest_hash':'approved','operation_id':'op','payload_hash':digest}
  state={'write_authorizations':{'a':authorization}}
  result=enqueue_write(state,'approved',{'id':'op','payload':payload,'authorization_id':'a'})
  self.assertEqual(result['outbox']['op']['payload'],payload)
  self.assertNotIn('outbox',state)
  with self.assertRaises(ValueError):
   enqueue_write(state,'different',{'id':'op','payload':payload,'authorization_id':'a'})
  with self.assertRaises(TypeError): retry_writes(result,object())
