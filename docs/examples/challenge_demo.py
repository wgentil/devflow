"""Owned offline diagnostic; run from the checkout, no provider or user source writes."""
from pathlib import Path
import hashlib,json,sys,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'skills/workflow/scripts'))
from workflow_lib.test_challenges import execute_challenge

def main():
    with tempfile.TemporaryDirectory(prefix='devflow-owned-example-') as directory:
        base=Path(directory);repo=base/'repo';repo.mkdir()
        (repo/'behavior.py').write_text('def retention(): return 30\n')
        (repo/'oracle.json').write_text('{"retention":30}')
        (repo/'check.py').write_text("""import json
from behavior import retention
expected=json.load(open('oracle.json'))['retention']
try:
    assert retention()==expected
    outcome,phase='passed',None
except AssertionError:
    outcome,phase='failed','test-assertion'
print(json.dumps({'schema':'devflow-test-report-v2','tests':[{'id':'retention','outcome':outcome,'failure_phase':phase}]}))
raise SystemExit(0 if outcome=='passed' else 1)
""")
        request={'schema_version':1,'source_paths':['behavior.py'],'input_paths':['check.py','oracle.json'],
            'input_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in repo.iterdir()},
            'replacements':[{'path':'behavior.py','before':'return 30','after':'return 60'}],
            'argv':[sys.executable,'-B','check.py'],'target_ids':['retention'],'report_format':'json','timeout_seconds':5,
            'incorrect_behavior':'Return sixty instead of the independently authored thirty-day rule.',
            'authority_refs':['owned-example:thirty-day-rule']}
        result=execute_challenge(repo,request,base/'artifacts')
        print(json.dumps({'detected':result['detected'],'disposition':result['disposition'],
            'user_source_unchanged':result['user_source_unchanged']}))
        return 0 if result['detected'] else 1

if __name__=='__main__':raise SystemExit(main())
