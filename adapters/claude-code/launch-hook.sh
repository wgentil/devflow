#!/bin/sh
# Host expands CLAUDE_PLUGIN_ROOT; no user-supplied setup or payload interpolation.
for runtime in python3 python; do
    if command -v "$runtime" >/dev/null 2>&1 && "$runtime" -c 'import sys; sys.exit(sys.version_info < (3,11))' >/dev/null 2>&1; then
        exec "$runtime" -B "$(dirname "$0")/hook.py"
    fi
done
printf '%s\n' 'DevFlow requires an existing Python 3.11+ runtime; this plugin does not provision it.' >&2
exit 0
