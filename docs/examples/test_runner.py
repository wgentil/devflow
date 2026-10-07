"""Run actual unittest cases and emit DevFlow's portable JSON report on stdout."""
import json
import sys
import unittest
from pathlib import Path


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({'id': test.id(), 'outcome': 'passed'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({'id': test.id(), 'outcome': 'failed'})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({'id': test.id(), 'outcome': 'error'})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({'id': test.id(), 'outcome': 'skipped'})


if __name__ == '__main__':
    sys.path.insert(0, str(Path.cwd()))
    suite = unittest.defaultTestLoader.discover('tests')
    result = unittest.TextTestRunner(stream=sys.stderr, resultclass=RecordedResult).run(suite)
    print(json.dumps({'tests': result.records}))
    sys.exit(0 if result.wasSuccessful() else 1)
