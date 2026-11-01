#!/usr/bin/env python3
"""chrome-claim: the old name of `agent-chrome` (renamed 2026-11-01; this alias goes on 2026-11-08). Translates the
old options to the new subcommands, says so in one line on stderr, and runs them:

  chrome-claim --purpose P --visible-because V   ->  agent-chrome authorize-tab P --visibility unfocused --visibility-reason V
  chrome-claim --purpose P --needs-human N       ->  the same (reason: a human must act), then mark-as-needing-human N
  chrome-claim --needs-human N                                    ->  agent-chrome mark-as-needing-human N
  chrome-claim done                                               ->  agent-chrome mark-as-human-done
  chrome-claim --message M                                        ->  agent-chrome reply-to-human M
  chrome-claim open [--project P] [--json]                        ->  agent-chrome status --mine [--project P] [--json]
  chrome-claim window [--project P]                               ->  agent-chrome open-profile-window [--project P]
"""
import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the deployed copy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent_chrome  # noqa: E402


def main():
    ap = argparse.ArgumentParser(prog='chrome-claim', description=__doc__.split('\n')[0])
    ap.add_argument('cmd', nargs='?', choices=['done', 'open', 'window'])
    for opt in ('--purpose', '--needs-human', '--visible-because', '--message', '--project'):
        ap.add_argument(opt)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    l_run = []
    if a.cmd == 'open':
        l_run.append(['status'] + (['--project', a.project] if a.project else ['--mine']) + (['--json'] if a.json else []))
    elif a.cmd == 'window':
        l_run.append(['open-profile-window'] + (['--project', a.project] if a.project else []))
    elif a.cmd == 'done':
        l_run.append(['mark-as-human-done'])
    elif a.purpose:  # the old visible reason becomes an unfocused authorization; a human's part, a mark after it
        if not (a.needs_human or a.visible_because):
            sys.exit('chrome-claim: refused: --purpose alone is not enough. Now:\n' + agent_chrome.AUTHORIZE_HELP)
        l_run.append(['authorize-tab', '--mode', 'single', a.purpose, '--visibility', 'unfocused', '--visibility-reason',
                      a.visible_because or f'a human must act in the tab: {a.needs_human}']
                     + (['--project', a.project] if a.project else []))
        if a.needs_human:
            l_run.append(['mark-as-needing-human', a.needs_human])
    elif a.needs_human:
        l_run.append(['mark-as-needing-human', a.needs_human])
    if a.message:
        l_run.append(['reply-to-human', a.message])
    if not l_run:
        ap.print_help()
        return
    for argv in l_run:
        print(f'chrome-claim: renamed: agent-chrome {argv[0]} (the old name stops working on 2026-11-08)', file=sys.stderr)
        agent_chrome.main(argv)


if __name__ == '__main__':
    main()
