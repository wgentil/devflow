import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.outbox import classify_issue, prepare_reconciliation
class IssueVerdictTests(unittest.TestCase):
 def test_confirmed_classification_and_metric_eligibility(self):
  x=classify_issue({},'i',{'kind':'escaped-defect'},None); self.assertFalse(x['confirmed']); self.assertFalse(x['metric_eligible'])
 def test_exact_manifest_eligible_only(self):
  self.assertFalse(prepare_reconciliation({'snapshot_complete':False},{'head':'a'})['eligible'])
