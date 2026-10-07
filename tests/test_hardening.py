import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/workflow/scripts'))
from workflow_lib.hardening import verify_gate, repository_schedule
class HardeningTests(unittest.TestCase):
 def test_hardening_missing_tool_stale_config(self):
  with tempfile.TemporaryDirectory() as d:
   result=verify_gate(Path(d),'r','g',['missing-tool']); self.assertFalse(result['passed']); self.assertEqual(result['failure'],'COMMAND_UNAVAILABLE')
   import subprocess
   root=Path(d); (root/'config').write_text('before'); subprocess.run(['git','init','-q'],cwd=root); subprocess.run(['git','-c','user.name=x','-c','user.email=x@y','add','.'],cwd=root); subprocess.run(['git','-c','user.name=x','-c','user.email=x@y','commit','-qm','base'],cwd=root)
   command=[sys.executable,'-c',"from pathlib import Path; Path('config').write_text('after')"]
   stale=verify_gate(root,'r','g',command); self.assertEqual(stale['failure'],'STALE_CONFIGURATION')
 def test_multi_repo_dependencies_and_proofs(self):
  schedule=repository_schedule({'work_items':[{'id':'a','repo_id':'r1','dependencies':[]},{'id':'b','repo_id':'r2','dependencies':['a']}]},{'r1':{'location':'/tmp/a'},'r2':{'location':'/tmp/b'}}); self.assertEqual(schedule['order'],['a','b'])
