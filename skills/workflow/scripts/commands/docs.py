"""Generated workflow documentation."""
import argparse,json
from pathlib import Path
from workflow_lib.docs import generate_docs

def register_commands(parser:argparse.ArgumentParser):
 p=parser.add_parser('docs'); p.add_argument('--catalog',required=True); p.add_argument('--profiles',required=True)
def dispatch(parsed):return generate_docs(json.loads(Path(parsed.catalog).read_text()),json.loads(Path(parsed.profiles).read_text()))
