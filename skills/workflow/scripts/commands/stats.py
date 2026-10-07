"""Usage and reporting command adapters."""
import argparse,json
from pathlib import Path
from workflow_lib.usage import import_usage
from workflow_lib.pricing import store_prices,price_usage
from workflow_lib.metrics import calculate_metrics
from workflow_lib.reporting import rollup,export_report
from workflow_lib.legacy import import_legacy

def register_commands(parser:argparse.ArgumentParser):
 p=parser.add_parser('stats'); p.add_argument('operation',choices=['usage-import','price','metrics','rollup','export','legacy-import']); p.add_argument('--input',required=True); p.add_argument('--options',default='{}')
def dispatch(parsed):
 data=json.loads(Path(parsed.input).read_text()); opts=json.loads(parsed.options)
 if parsed.operation=='legacy-import': return import_legacy(Path(parsed.input),opts.get('schema_version',1))
 if parsed.operation=='usage-import': return import_usage(data,opts.get('adapter_version','v1'),opts.get('bindings',{}))
 if parsed.operation=='price': return price_usage(data['usage'],data['prices'],data['coverage'])
 if parsed.operation=='metrics': return calculate_metrics(data.get('runs',[]),data.get('usage',{}),opts['as_of'])
 if parsed.operation=='rollup': return rollup(data,opts.get('scope',{}))
 return {'output':export_report(data,opts.get('format','json'))}
