import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.legacy import compare_parity
class ParityTests(unittest.TestCase):
 def test_reference_outcome_fixtures(self): self.assertTrue(compare_parity({'a':1},{'a':1})['matches'])
 def test_full_requirement_evidence(self): self.assertFalse(compare_parity({'a':1,'b':2},{'a':1})['matches'])
