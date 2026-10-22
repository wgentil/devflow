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
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.utf8_io import write_utf8


def run_suite(start_dir: Path, patterns: list[str], report_path: Path) -> dict:
    started = time.monotonic()
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for pattern in patterns:
        suite.addTests(loader.discover(str(start_dir.resolve()), pattern=pattern))
    result = unittest.TextTestRunner(verbosity=2, failfast=False).run(suite)
    git = subprocess.run(['git', '--version'], capture_output=True, encoding='utf-8', check=False)
    report = {'schema_version': 1, 'success': result.wasSuccessful() and result.testsRun > 0,
        'tests_run': result.testsRun, 'failures': [test.id() for test, _ in result.failures],
        'errors': [test.id() for test, _ in result.errors],
        'skips': [{'id': test.id(), 'reason': reason} for test, reason in result.skipped],
        'expected_failures': [test.id() for test, _ in result.expectedFailures],
        'unexpected_successes': [test.id() for test in result.unexpectedSuccesses],
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'metadata': {'platform': platform.platform(), 'python': sys.version, 'executable': sys.executable,
            'git': git.stdout.strip(), 'preferred_encoding': locale.getpreferredencoding(False),
            'filesystem_encoding': sys.getfilesystemencoding(), 'stdout_encoding': sys.stdout.encoding,
            'stderr_encoding': sys.stderr.encoding, 'utf8_mode': sys.flags.utf8_mode,
            'PYTHONUTF8': os.environ.get('PYTHONUTF8'), 'PYTHONIOENCODING': os.environ.get('PYTHONIOENCODING'),
            'git_sha': os.environ.get('GITHUB_SHA'), 'patterns': patterns}}
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
