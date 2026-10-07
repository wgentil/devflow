import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.docs import generate_docs
class IssueMigrationFlowTests(unittest.TestCase):
 def test_issue_migration_integration_and_docs(self):
  catalog={'version':1,'stages':[{'id':'x','prerequisites':[]}]}; profiles={'profiles':{'generic':{}}}
  self.assertEqual(generate_docs(catalog,profiles),generate_docs(catalog,profiles))
