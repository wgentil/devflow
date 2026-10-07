import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class ExampleRunnerTests(unittest.TestCase):
    def test_absolute_runner_imports_project_and_reports_real_red_green(self):
        with tempfile.TemporaryDirectory() as temp:
            repo=Path(temp);(repo/'tests').mkdir();(repo/'app.py').write_text('VALUE=1\n')
            (repo/'tests/test_feature.py').write_text('import unittest\nfrom app import VALUE\nclass Feature(unittest.TestCase):\n def test_feature(self):self.assertEqual(VALUE,2)\n')
            command=[sys.executable,'-B',str(ROOT/'docs/examples/test_runner.py')]
            red=subprocess.run(command,cwd=repo,capture_output=True,text=True)
            self.assertEqual(json.loads(red.stdout)['tests'],[{'id':'test_feature.Feature.test_feature','outcome':'failed'}])
            (repo/'app.py').write_text('VALUE=2\n')
            green=subprocess.run(command,cwd=repo,capture_output=True,text=True)
            self.assertEqual(green.returncode,0,green.stderr)
            self.assertEqual(json.loads(green.stdout)['tests'][0]['outcome'],'passed')
