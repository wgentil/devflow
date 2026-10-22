"""Generated workflow documentation."""
import argparse,json
from pathlib import Path
from workflow_lib.docs import generate_docs
from workflow_lib.documentation import discover_documentation
from workflow_lib.store import WorkflowError

def register_commands(parser:argparse.ArgumentParser):
 p=parser.add_parser('docs'); p.add_argument('--catalog'); p.add_argument('--profiles')
 p.add_argument('--discover',action='store_true'); p.add_argument('--include-history',action='store_true')
 p.add_argument('--required-source-id',action='append',default=[])
def dispatch(parsed):
 if parsed.discover:
  if parsed.catalog or parsed.profiles:raise WorkflowError('INVALID_INPUT','discovery and catalog generation are separate modes')
  return discover_documentation(Path(__file__).resolve().parents[4],include_history=parsed.include_history,required_ids=parsed.required_source_id)
 if not parsed.catalog or not parsed.profiles:raise WorkflowError('INVALID_INPUT','catalog generation requires --catalog and --profiles')
 return generate_docs(json.loads(Path(parsed.catalog).read_text(encoding='utf-8')),json.loads(Path(parsed.profiles).read_text(encoding='utf-8')))
