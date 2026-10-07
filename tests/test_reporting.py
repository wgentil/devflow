import sys, unittest, json, csv, io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.reporting import rollup, export_report
class ReportingTests(unittest.TestCase):
 def test_ratio_of_sums_and_zero_denominator(self):
  r=rollup([{'id':'a','numerator':1,'denominator':2},{'id':'b','numerator':9,'denominator':10}],{}); self.assertAlmostEqual(r['ratio'],10/12); self.assertIsNone(rollup([], {})['ratio'])
 def test_project_version_month_filters_and_exclusions(self):
  r=rollup([{'id':'a','project':'p','version':'1','date':'2026-01-01T00:00:00Z','numerator':1,'denominator':1}],{'project':'p','month':'2026-01'}); self.assertEqual(r['eligible_run_ids'],['a'])
 def test_export_formats_unicode_and_injection(self):
  r={'status':'final','label':'=SUM(1,2)','ratio':.5}; self.assertIn("'=SUM",export_report(r,'csv')); self.assertEqual(json.loads(export_report(r,'json')),r)
