#!/usr/bin/env python3
"""Offline documentation checks; --write only replaces generated route blocks."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/workflow/scripts'))
from workflow_lib.documentation import check_documentation, load_documentation_policy, navigation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--check', action='store_true')
    group.add_argument('--write', action='store_true')
    args = parser.parse_args()
    policy = load_documentation_policy(ROOT)
    if args.write:
        for path in {ROOT / source['path'] for source in policy['sources'].values()}:
            text = path.read_text(encoding='utf-8')
            result = re.sub(r'<!-- devflow:routes:([^ >]+) -->.*?<!-- /devflow:routes -->',
                            lambda m: navigation(policy, m[1]), text, flags=re.S)
            if result != text:
                path.write_text(result, encoding='utf-8')
    report = check_documentation(ROOT)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return bool(report['problems'])


if __name__ == '__main__':
    raise SystemExit(main())
