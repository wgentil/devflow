import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.pricing import store_prices, price_usage
class PricingTests(unittest.TestCase):
 def test_coverage_89_90_and_missing_rates(self):
  p=store_prices({},'v1',{'timestamp':'2026-01-01'},{'p/m':{'input':1,'cached':.5,'output':2}})
  usage={'events':[{'provider':'p','model':'m','input_tokens':1000000,'cached_tokens':0,'output_tokens':0}]}
  self.assertFalse(price_usage(usage,p,{'coverage':.89})['eligible']); self.assertTrue(price_usage(usage,p,{'coverage':.90})['eligible'])
 def test_model_identity_and_cached_categories(self):
  p=store_prices({},'1',{'timestamp':'now'},{'p/a':{'input':2,'cached':1,'output':3}}); out=price_usage({'events':[{'provider':'p','model':'a','input_tokens':10,'cached_tokens':10,'output_tokens':0}]},p,{'coverage':1}); self.assertEqual(out['cost'],.00001)
 def test_reprice_preserves_frozen_report(self):
  a=store_prices({},'1',{'timestamp':'t'},{'p/m':{'input':1,'cached':1,'output':1}}); b=store_prices({},'2',{'timestamp':'t2'},{'p/m':{'input':2,'cached':2,'output':2}}); self.assertNotEqual(a['id'],b['id'])
