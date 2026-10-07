"""Configured hardening gate runner."""
import argparse,json
from pathlib import Path
from workflow_lib.hardening import verify_gate,repository_schedule

def register_commands(parser:argparse.ArgumentParser):
 p=parser.add_parser('harden'); p.add_argument('operation',choices=['gate','schedule']); p.add_argument('--input',required=True)
def dispatch(parsed):
 d=json.loads(Path(parsed.input).read_text())
 if parsed.operation=='gate':return verify_gate(Path(d['root']),d['run_id'],d['gate_id'],d['command'])
 return repository_schedule(d['plan'],d['repositories'])
