import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.usage import import_usage
from workflow_lib.pricing import store_prices,price_usage
from workflow_lib.reporting import rollup
class FullFlowTests(unittest.TestCase):
 def test_full_workflow_reporting(self):
  u=import_usage([{'source_id':'s','event_id':'e','provider':'p','model':'m','input_tokens':10,'cached_tokens':0,'output_tokens':2}],'v1',{})
  p=store_prices({},'v1',{'source':'fixture'},{'p/m':{'input':1,'cached':1,'output':2}}); cost=price_usage(u,p,{'coverage':1}); self.assertTrue(cost['eligible']); self.assertIsNotNone(rollup([{'id':'r','numerator':1,'denominator':1}],{})['ratio'])
 def test_unavailable_conditions_remain_visible(self):
  self.assertFalse(price_usage({'events':[]},{'rates':{}},{'coverage':.5})['eligible'])
