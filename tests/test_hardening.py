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

 def test_arbitrary_gate_logs_stay_raw_and_structured_stdout_is_strict(self):
  import hashlib, subprocess
  with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
   root=Path(d); artifacts=Path(a)
   subprocess.run(['git','init','-q'],cwd=root,check=True)
   subprocess.run(['git','-c','user.name=x','-c','user.email=x@y','commit','--allow-empty','-qm','base'],cwd=root,check=True)
   raw=b'caf\xe9\r\n'
   command=[sys.executable,'-c',f'import sys;sys.stdout.buffer.write({raw!r})']
   result=verify_gate(root,'r','g',command,artifacts_root=artifacts)
   self.assertTrue(result['passed'], result)
   self.assertEqual(result['output_hash'],hashlib.sha256(raw).hexdigest())
   self.assertEqual((artifacts/result['stdout_ref']).read_bytes(),raw)
   invalid=verify_gate(root,'r','g',command,{'kind':'json-report','version':1},artifacts_root=artifacts)
   self.assertEqual(invalid['failure'],'INVALID_REPORT_ENCODING')
   self.assertEqual((artifacts/invalid['stdout_ref']).read_bytes(),raw)
   body=b'{"findings":[]}'
   command=[sys.executable,'-c',f'import sys;sys.stdout.buffer.write({body!r});sys.stderr.buffer.write({raw!r})']
   valid=verify_gate(root,'r','g',command,{'kind':'json-report','version':1},artifacts_root=artifacts)
   self.assertTrue(valid['passed'],valid)
   self.assertEqual((artifacts/valid['stderr_ref']).read_bytes(),raw)

 def test_structured_gate_preserves_raw_crlf(self):
  import hashlib, subprocess
  with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as a:
   root=Path(d); artifacts=Path(a)
   subprocess.run(['git','init','-q'],cwd=root,check=True)
   subprocess.run(['git','-c','user.name=x','-c','user.email=x@y','commit','--allow-empty','-qm','base'],cwd=root,check=True)
   raw=b'{"findings":[]}\r\n'
   command=[sys.executable,'-c',f'import sys;sys.stdout.buffer.write({raw!r})']
   result=verify_gate(root,'r','g',command,{'kind':'json-report','version':1},artifacts_root=artifacts)
   self.assertTrue(result['passed'],result)
   self.assertEqual((artifacts/result['stdout_ref']).read_bytes(),raw)
   self.assertEqual(result['output_hash'],hashlib.sha256(raw).hexdigest())
