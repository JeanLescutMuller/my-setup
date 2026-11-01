#!/usr/bin/env python3
"""chrome-who: the old name of `agent-chrome status` (renamed 2026-11-01; this alias goes on 2026-11-08): says so in
one line on stderr, then runs it with the same options ([--since 7d] [--project P] [--json])."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the deployed copy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_chrome  # noqa: E402

if __name__ == '__main__':
    print('chrome-who: renamed: agent-chrome status (the old name stops working on 2026-11-08)', file=sys.stderr)
    agent_chrome.main(['status', *sys.argv[1:]])
