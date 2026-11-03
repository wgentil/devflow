import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--mode', choices=['local', 'github'], required=True)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
source, output = args.source.resolve(), args.output.resolve()
output.parent.mkdir(parents=True, exist_ok=True)
transcript = []
with tempfile.TemporaryDirectory(prefix='devflow-0317-' + args.mode + '-hosts-') as temporary:
    base = Path(temporary).resolve()
    codex_config, claude_config = base / 'codex', base / 'claude'
    codex_config.mkdir()
    claude_config.mkdir()
    environment = {**os.environ, 'CODEX_HOME': str(codex_config),
                   'CLAUDE_CONFIG_DIR': str(claude_config), 'GIT_TERMINAL_PROMPT': '0', 'NO_COLOR': '1'}

    def run(argv, *, save=None, timeout=180):
        started = time.perf_counter()
        child = subprocess.run([str(x) for x in argv], cwd=base, env=environment,
                               capture_output=True, encoding='utf-8', timeout=timeout)
        transcript.append({'argv': [str(x) for x in argv], 'exit': child.returncode,
                           'elapsed_seconds': time.perf_counter() - started,
                           'stdout': child.stdout, 'stderr': child.stderr})
        output.with_suffix('.commands.json').write_text(json.dumps(transcript, indent=2) + '\n')
        if child.returncode:
            raise RuntimeError('Isolated install command failed: ' + ' '.join(str(x) for x in argv)
                               + '\n' + child.stdout[-4000:] + child.stderr[-4000:])
        if save is not None:
            save.write_text(child.stdout, encoding='utf-8')
        return child

    marketplace = str(source) if args.mode == 'local' else 'wgentil/devflow'
    run(['claude', 'plugin', 'validate', source])
    run(['codex', 'plugin', 'marketplace', 'add', marketplace])
    run(['codex', 'plugin', 'add', 'devflow@devflow-marketplace'])
    run(['claude', 'plugin', 'marketplace', 'add', marketplace, '--scope', 'user'])
    run(['claude', 'plugin', 'install', 'devflow@devflow-marketplace', '--scope', 'user', '-y'])
    codex_list, claude_list = base / 'codex-installed.json', base / 'claude-installed.json'
    run(['codex', 'plugin', 'list', '--json'], save=codex_list)
    run(['claude', 'plugin', 'list', '--json'], save=claude_list)
    run([sys.executable, '-B', source / 'scripts/verify_windows_install.py',
         '--source-root', source, '--codex-list', codex_list,
         '--codex-cache', codex_config / 'plugins/cache', '--claude-list', claude_list,
         '--output', output], timeout=360)
    report = json.loads(output.read_text())
    assert report['success'] and len(report['gates']) == 8
    assert all(gate['status'] == 'PASS' for gate in report['gates'].values())
    assert report['descriptor']['plugin_version'] == '0.3.17'
print(json.dumps({'success': True, 'mode': args.mode,
                  'fingerprint': report['descriptor']['fingerprint'],
                  'gates': len(report['gates']), 'isolated_configs_removed': not base.exists()}))
