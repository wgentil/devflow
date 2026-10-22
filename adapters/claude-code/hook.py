#!/usr/bin/env python3
"""Claude protocol translation only; shared helper owns eligibility."""
import json
import re
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'skills/workflow/scripts'))
from workflow_lib.utf8_io import write_utf8

LIMIT=65536


def main():
    event=None
    try:
        raw=sys.stdin.buffer.read(LIMIT+1)
        known_event = re.search(rb'"hook_event_name"\s*:\s*"(TaskCompleted|UserPromptSubmit)"', raw)
        if known_event:event=known_event[1].decode('ascii')
        if len(raw)>LIMIT:raise ValueError('hook input exceeds 64 KiB')
        payload=json.loads(raw)
        if not isinstance(payload,dict):raise ValueError('hook payload must be an object')
        event=payload.get('hook_event_name')
        if event == 'Stop':return 0
        if event not in {'SessionStart','UserPromptSubmit','TaskCompleted'}:raise ValueError('unsupported hook event')
        for field in ('cwd','session_id'):
            if not isinstance(payload.get(field),str) or not payload[field] or len(payload[field])>4096:raise ValueError('missing or oversized '+field)
        if event == 'TaskCompleted' and (not isinstance(payload.get('task_id'),str) or not payload['task_id'] or len(payload['task_id'])>1024):raise ValueError('task_id required')
        argv=[sys.executable,'-B',str(ROOT/'skills/workflow/scripts/run.py'),'host','hook-evaluate',
              '--project-dir',payload['cwd'],'--session-id',payload['session_id'],'--event',event]
        if event == 'TaskCompleted':argv+=['--task-id',payload['task_id']]
        result=subprocess.run(argv,capture_output=True,timeout=8)
        if len(result.stdout)>LIMIT or len(result.stderr)>LIMIT:raise ValueError('helper output exceeds budget; inspect host status')
        decision=json.loads(result.stdout)
        if result.returncode or decision.get('status') == 'block':
            reason=decision.get('reason_code') or decision.get('error') or 'HOST_CHECK_FAILED'
            write_utf8('DevFlow: '+reason+'. '+decision.get('message','Inspect host status and rework the mapped task.')+'\n',stream=sys.stderr)
            return 2 if event in {'TaskCompleted', 'UserPromptSubmit'} else 0
        if decision.get('brief'):
            write_utf8(json.dumps({'hookSpecificOutput':{'hookEventName':event,'additionalContext':'DevFlow resume: '+json.dumps(decision['brief'],separators=(',',':'))}},separators=(',',':'))+'\n')
        elif decision.get('message'):write_utf8('DevFlow: '+decision['message']+'\n',stream=sys.stderr)
        return 0
    except (OSError,ValueError,TypeError,subprocess.TimeoutExpired) as exc:
        write_utf8('DevFlow hook diagnostic: '+str(exc)[:1000]+'. Inspect attachment before completing mapped work.\n',stream=sys.stderr)
        return 2 if event in {'TaskCompleted', 'UserPromptSubmit'} else 0


if __name__ == '__main__':raise SystemExit(main())
