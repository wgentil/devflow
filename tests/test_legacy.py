import sys, tempfile, unittest, json, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.legacy import import_legacy
class LegacyTests(unittest.TestCase):
 def test_read_only_source_and_unsupported_version(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger.json'; data={'run_id':'x','stages':{},'rulings':[],'parked_findings':[],'artifacts':{},'artifact_paths':{},'attempts':[],'active_attempts':[],'work_items':[],'enabled_optional_stages':[],'target_increment':None,'context_decisions':{}}; p.write_text(json.dumps(data)); before=p.read_bytes(); out=import_legacy(p,1); self.assertEqual(p.read_bytes(),before); self.assertEqual(out['source_hash'],hashlib.sha256(before).hexdigest())
   with self.assertRaises(ValueError): import_legacy(p,2)
