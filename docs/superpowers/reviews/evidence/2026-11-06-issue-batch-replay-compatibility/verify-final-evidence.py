"""Validate the completed stable-source suite without repeating it."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
report = json.loads((HERE / 'final-platform.json').read_text())
assert report['success'] is True
assert report['tests_run'] == 1302, report['tests_run']
for key in ('failures','errors','expected_failures','unexpected_successes'):
    assert report[key] == [], (key, report[key])
assert report['metadata']['patterns'] == ['test_*.py']
assert report['metadata']['failfast'] is False
snapshot = json.loads((HERE / 'final-source-snapshot.json').read_text())
files = subprocess.check_output(['rg','--files','skills','adapters','definitions','scripts','tests'],cwd=ROOT,text=True).splitlines()
actual = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(files)
          if '__pycache__' not in p and not p.endswith('.pyc')}
assert actual == snapshot['files'], 'Runtime/test source changed after final-run snapshot.'
assert hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest() == snapshot['sha256']
print(f"Complete stable-source suite verified: {report['tests_run']} tests, {len(report['skips'])} documented skips, zero failures/errors.")
