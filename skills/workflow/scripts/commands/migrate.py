"""Migration and parity validation helpers."""
import argparse,json
from pathlib import Path
from workflow_lib.migrations import validate_increments,review_specification,record_parity

def register_commands(parser:argparse.ArgumentParser):
 p=parser.add_parser('migrate'); p.add_argument('operation',choices=['validate','review-spec','record-parity']); p.add_argument('--input',required=True)
def dispatch(parsed):
 d=json.loads(Path(parsed.input).read_text())
 if parsed.operation=='validate':return validate_increments(d['increments'],d['parity'])
 if parsed.operation=='review-spec':return review_specification(d['spec'],d['source_index'])
 return record_parity(d['state'],d['increment_id'],d['verified'],d.get('ruling'))
