"""Read-only source indexing command."""
import argparse, json
from pathlib import Path
from workflow_lib.ingestion import ingest_sources

def register_commands(parser: argparse.ArgumentParser):
    ingest=parser.add_parser('ingest'); ingest.add_argument('--repo-json',required=True); ingest.add_argument('--scope',action='append',required=True); ingest.add_argument('--profile-json',required=True)
def dispatch(parsed):
    return ingest_sources(json.loads(Path(parsed.repo_json).read_text()),parsed.scope,json.loads(Path(parsed.profile_json).read_text()),{})
