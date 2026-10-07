import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.migrations import validate_increments, record_parity
class MigrationTests(unittest.TestCase):
 def test_parity_preserve_waive_and_idempotency(self):
  x=validate_increments({'increments':[{'id':'a','depends_on':[],'criteria':['c1']}]},[{'id':'c1'},{'id':'c2'}]); self.assertFalse(x['valid'])
  s=record_parity({},'a',['c1'],None); s=record_parity(s,'a',['c1'],None); self.assertEqual(len(s['parity']),1)
 def test_increment_delivery_dependency(self):
  x=validate_increments({'increments':[{'id':'a','depends_on':[],'criteria':['c']},{'id':'b','depends_on':['a'],'criteria':['d']}]},[{'id':'c'},{'id':'d'}]); self.assertTrue(x['valid'])
  self.assertFalse(x['ready']['b'])
