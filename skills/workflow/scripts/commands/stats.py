"""Append-only usage, pricing, compatibility imports and frozen reports."""
import json
from pathlib import Path
from .journal import add_journal_options, commit
from workflow_lib.store import read_state, WorkflowError
from workflow_lib.pricing import price_usage
from workflow_lib.reporting import rollup, export_report
from workflow_lib.legacy import import_legacy


def register_commands(parser):
    command = parser.add_parser('stats')
    command.add_argument('operation', choices=['usage-import','expectations','prices','price','metrics','rollup','export','legacy-import','inspect','trace','context'])
    command.add_argument('--input')
    command.add_argument('--options', default='{}')
    add_journal_options(command)


def dispatch(parsed):
    opts = json.loads(parsed.options)
    if parsed.operation == 'context':
        if not parsed.root:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'context statistics require a selected control root')
        from workflow_lib.context_metrics import context_statistics
        return context_statistics(Path(parsed.root), opts)
    if parsed.operation == 'trace':
        if not parsed.root or not opts.get('run_id'):
            raise WorkflowError('TRACE_INPUT_REQUIRED', 'trace requires --root and options run_id')
        from workflow_lib.improvement_traces import project_run_trace
        from workflow_lib.journal_domains import digest
        trace = project_run_trace(read_state(Path(parsed.root)), opts['run_id'],
                                  opts.get('include_usage', True))
        return {**trace, 'trace_hash': digest(trace)}
    if parsed.operation == 'inspect':
        if not parsed.root:
            raise WorkflowError('CONTROL_ROOT_REQUIRED', 'inspection requires --root')
        state = read_state(Path(parsed.root))['data']
        return {k: state.get(k, {}) for k in ('usage','usage_expectations','prices','reports','legacy_imports')}
    if parsed.operation == 'metrics':
        return commit(parsed, 'domain.stats.metrics', opts)
    if parsed.root and parsed.operation == 'rollup':
        return rollup(read_state(Path(parsed.root))['data'].get('reports', []), opts.get('scope', {}))
    if parsed.root and parsed.operation == 'export' and opts.get('report_id'):
        report = next((r for r in read_state(Path(parsed.root))['data'].get('reports', []) if r['id'] == opts['report_id']), None)
        if report is None:
            raise WorkflowError('REPORT_NOT_FOUND', 'frozen report is unavailable')
        return {'output': export_report(report, opts.get('format', 'json'))}
    if not parsed.input:
        raise WorkflowError('INVALID_INPUT', '--input is required')
    if parsed.operation == 'legacy-import':
        return commit(parsed, 'domain.stats.legacy-import', {'record': import_legacy(Path(parsed.input), opts.get('schema_version', 1))})
    request = json.loads(Path(parsed.input).read_text())
    if parsed.operation == 'usage-import':
        return commit(parsed, 'domain.stats.usage-import', {'records': request,
                      'adapter_version': opts.get('adapter_version', 'v1'), 'bindings': opts.get('bindings', {})})
    if parsed.operation in {'prices','expectations'}:
        return commit(parsed, 'domain.stats.' + parsed.operation, request)
    if parsed.operation == 'price':
        return price_usage(request['usage'], request['prices'], request['coverage'])
    if parsed.operation == 'rollup':
        reports = read_state(Path(parsed.root))['data'].get('reports', []) if parsed.root else request
        return rollup(reports, opts.get('scope', {}))
    return {'output': export_report(request, opts.get('format', 'json'))}
