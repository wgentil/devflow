import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.issues import capture_issue, validate_snapshot, revise_groups, start_issue_run
class IssueTests(unittest.TestCase):
 def test_partial_snapshot_no_bulk(self):
  snap={'complete':False,'pages':[1],'expected_pages':2}; self.assertFalse(validate_snapshot(snap)['valid'])
  with self.assertRaises(ValueError): revise_groups({},'x',[{'id':'g','issue_ids':['i']}])
 def test_group_assignment_and_revisions(self):
  snap={'complete':True,'pages':[1],'expected_pages':1,'issues':[{'id':'i'}]}; import hashlib,json; h=hashlib.sha256(json.dumps(snap,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(); s=revise_groups({'snapshots':{'h':snap}},h,[{'id':'g','issue_ids':['i']}]); self.assertTrue(s['groups'])
  self.assertEqual(start_issue_run(s,'g','build')['intent'],'build')
 def test_capture_intents_and_human_content(self):
  r=capture_issue({}, {'id':'i','description':'human'}); self.assertEqual(r['issues']['i']['original']['description'],'human')
  with self.assertRaises(ValueError): start_issue_run({'snapshots':{}},'g','build')
