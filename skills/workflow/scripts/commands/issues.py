"""Local issue snapshot helpers; no connector is invoked here."""
import argparse,json
from pathlib import Path
from workflow_lib.issues import capture_issue,validate_snapshot,revise_groups

def register_commands(parser:argparse.ArgumentParser):
 p=parser.add_parser('issues'); p.add_argument('operation',choices=['capture','validate-snapshot','group']); p.add_argument('--input',required=True)
def dispatch(parsed):
 data=json.loads(Path(parsed.input).read_text())
 if parsed.operation=='capture':return capture_issue(data.get('state',{}),data['issue'])
 if parsed.operation=='validate-snapshot':return validate_snapshot(data['snapshot'])
 return revise_groups(data['state'],data['snapshot_hash'],data['groups'])
