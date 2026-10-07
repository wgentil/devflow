import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.metrics import eligible_runs, calculate_metrics, freeze_report
class MetricsTests(unittest.TestCase):
 def test_standalone_grouped_and_pending_eligibility(self):
  runs=[{'id':'a','status':'delivered','delivery_at':'2026-01-01T00:00:00Z','acceptance':True},{'id':'b','status':'active'}]; self.assertEqual([r['id'] for r in eligible_runs({'runs':runs},'2026-01-02T00:00:00Z')],['a'])
 def test_confirmations_and_30_day_boundary(self):
  report=calculate_metrics([{'id':'a','status':'delivered','delivery_at':'2026-01-01T00:00:00Z','acceptance':True}],{},'2026-01-31T00:00:00Z'); self.assertEqual(report['defect_window_status'],'final')
 def test_missing_event_metric_unavailable(self):
  x=calculate_metrics([],{},'2026-01-01T00:00:00Z'); self.assertIsNone(x['human_touchpoints'])
