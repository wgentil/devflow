import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.migrations import review_specification
class SpecRefinementTests(unittest.TestCase):
 def test_scope_contradiction_and_source_grounding(self):
  spec={'requirements':[{'id':'R1','text':'must work','provenance':{'sources':[{'path':'x','commit':'a','start_line':1,'end_line':2}]}}]}
  self.assertFalse(review_specification(spec,{'sources':[]})['complete'])
  self.assertTrue(review_specification(spec,{'sources':[{'path':'x','commit':'a','line_start':1,'line_end':2} ]})['complete'])
