#!/usr/bin/env python3
"""Run the complete platform suite and retain all failures plus locale metadata."""
from __future__ import annotations

import argparse
import json
import locale
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.utf8_io import write_utf8


def sqlite_metadata():
    try:
        import sqlite3
        with tempfile.TemporaryDirectory(prefix='devflow-sqlite-platform-') as temporary:
            conn=sqlite3.connect(Path(temporary)/'probe.sqlite3',timeout=1)
            try:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=FULL')
                conn.execute('PRAGMA foreign_keys=ON')
                return {'version':sqlite3.sqlite_version,
                    'compile_options':[row[0] for row in conn.execute('PRAGMA compile_options')],
                    'durability':{key:conn.execute('PRAGMA '+key).fetchone()[0]
                        for key in ('journal_mode','synchronous','foreign_keys','busy_timeout')}}
            finally:conn.close()
    except (ImportError,OSError,RuntimeError) as exc:
        return {'status':'UNAVAILABLE','reason':str(exc)}


def run_suite(start_dir: Path, patterns: list[str], report_path: Path) -> dict:
    started = time.monotonic()
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for pattern in patterns:
        suite.addTests(loader.discover(str(start_dir.resolve()), pattern=pattern))
    result = unittest.TextTestRunner(verbosity=2, failfast=False).run(suite)
    git = subprocess.run(['git', '--version'], capture_output=True, encoding='utf-8', check=False)
    def traces(rows):
        limit=65536
        return [{'id':test.id(),'traceback':trace if len(trace)<=limit else
                 trace[:limit//2]+'\n[traceback excerpt truncated]\n'+trace[-limit//2:],
                 'truncated':len(trace)>limit} for test,trace in rows]
    report = {'schema_version': 1, 'success': result.wasSuccessful() and result.testsRun > 0,
        'tests_run': result.testsRun, 'failures': [test.id() for test, _ in result.failures],
        'errors': [test.id() for test, _ in result.errors],
        'failure_traces':traces(result.failures),'error_traces':traces(result.errors),
        'skips': [{'id': test.id(), 'reason': reason} for test, reason in result.skipped],
        'expected_failures': [test.id() for test, _ in result.expectedFailures],
        'unexpected_successes': [test.id() for test in result.unexpectedSuccesses],
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'metadata': {'platform': platform.platform(), 'python': sys.version, 'executable': sys.executable,
            'git': git.stdout.strip(), 'preferred_encoding': locale.getpreferredencoding(False),
            'filesystem_encoding': sys.getfilesystemencoding(), 'stdout_encoding': sys.stdout.encoding,
            'stderr_encoding': sys.stderr.encoding, 'utf8_mode': sys.flags.utf8_mode,
            'PYTHONUTF8': os.environ.get('PYTHONUTF8'), 'PYTHONIOENCODING': os.environ.get('PYTHONIOENCODING'),
            'git_sha': os.environ.get('GITHUB_SHA'), 'patterns': patterns, 'sqlite':sqlite_metadata()}}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pattern', action='append')
    parser.add_argument('--start-dir', type=Path, default=ROOT / 'tests')
    args = parser.parse_args()
    report = run_suite(args.start_dir, args.pattern or ['test_*.py'], args.output)
    write_utf8(json.dumps({'success': report['success'], 'tests_run': report['tests_run'],
                           'failures': report['failures'], 'errors': report['errors']}) + '\n')
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
