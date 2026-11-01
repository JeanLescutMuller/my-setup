#!/usr/bin/python3
"""Native messaging host of the "Agent tab notes" extension (chrome/extension/): the Chrome kit's record, on the tab.

Chrome starts it when the extension connects (chrome.runtime.connectNative("com.jeanlescut.agent_tab_notes")) and
stops it when the extension goes; the host manifest that allows it is written by modules/chrome_kit.sh into
Chrome's own NativeMessagingHosts/ folder (not a profile).
Reads $CHROME_STATE (chrome_kit): open.json (what is open now), history/YYYY-MM.jsonl (the agents' "message" events:
their replies), comments.jsonl (the user's comments). Writes one line to comments.jsonl per comment typed in the
side panel: ts, dt, session_id, tab_id, url, text (hook.py gives it to the session). Writes windows/<profile>.json
while the extension runs: ts, dt, pid, profile, windows (ids), projects ({project: its agent window}); removed when
the extension goes (agent-chrome open-profile-window reads it: does this profile have a window?).
Sends the extension {"notes": {tab_id: entry + "thread"}} at start and after every change of those files: only
Claude in Chrome tabs (device_id set) opened since the user's Chrome started (Chrome reuses tab ids after a restart).
Python 3.9 (macOS /usr/bin/python3), standard library only.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import threading
import time
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the deployed copy
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome_kit as kit  # noqa: E402

lock_out = threading.Lock()
d_mine = {'windows_file': None}   # the windows/<profile>.json this host wrote: removed when Chrome closes the port


def read_message() -> dict:
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:                                  # Chrome closed the port (from the reader thread too)
        if d_mine['windows_file']:
            Path(d_mine['windows_file']).unlink(missing_ok=True)
        os._exit(0)
    return json.loads(sys.stdin.buffer.read(struct.unpack('<I', raw)[0]))


def send(obj: dict):
    data = json.dumps(obj, ensure_ascii=False).encode()
    with lock_out:
        sys.stdout.buffer.write(struct.pack('<I', len(data)) + data)
        sys.stdout.buffer.flush()


def jsonl(path: Path):
    try:
        with open(path) as f:
            for line in f:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except FileNotFoundError:
        return


def history_files() -> list[Path]:
    """This month's and last month's history: a tab is rarely open longer."""
    return sorted(kit.HISTORY.glob('*.jsonl'))[-2:]


def notes() -> dict:
    l_main = [p['start_ts'] for p in kit.chrome_processes() if p['kind'] == "user's Chrome"]
    since = min(l_main) - 5 if l_main else 0
    d_notes = {k: dict(e, thread=[]) for k, e in kit.read_open().items()
               if e.get('device_id') and (e.get('opened_ts') or 0) >= since}
    by_sid = {}
    for e in d_notes.values():
        by_sid.setdefault(e.get('session_id'), []).append(e)
    for f in history_files():
        for r in jsonl(f):
            if r.get('event') == 'message' and r.get('message'):
                for e in by_sid.get(r.get('session_id'), []):
                    if r.get('ts', 0) >= e.get('opened_ts', 0):
                        e['thread'].append({'ts': r['ts'], 'from': 'agent', 'text': r['message']})
    for c in jsonl(kit.COMMENTS):
        e = d_notes.get(str(c.get('tab_id')))
        l_e = [e] if e else by_sid.get(c.get('session_id'), []) if c.get('session_id') else []
        for e in l_e:
            if c.get('ts', 0) >= e.get('opened_ts', 0):
                e['thread'].append({'ts': c.get('ts'), 'from': 'you', 'text': c.get('text')})
    for e in d_notes.values():
        e['thread'].sort(key=lambda m: m['ts'] or 0)
    return d_notes


def add_comment(d: dict):
    entry = kit.read_open().get(str(d.get('tab_id')), {})
    ts = int(time.time())
    row = {'ts': ts, 'dt': kit.utc(ts), 'session_id': entry.get('session_id'), 'tab_id': d.get('tab_id'),
           'url': d.get('url') or entry.get('url'), 'text': d.get('text')}
    with kit.locked(kit.COMMENTS):                    # one line per write: hook.py reads it by byte offset
        with open(kit.COMMENTS, 'a') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')


def write_windows(d: dict):
    """The extension's report of its profile's windows -> windows/<profile>.json (one profile per extension)."""
    profile = str(d.get('profile') or '')
    if not profile or '/' in profile or profile.startswith('.'):
        return
    ts = int(time.time())
    kit.WINDOWS.mkdir(parents=True, exist_ok=True)
    f = kit.WINDOWS / f'{profile}.json'
    kit.write_json(f, {'ts': ts, 'dt': kit.utc(ts), 'pid': os.getpid(), 'profile': profile,
                       'windows': d.get('windows') or [], 'projects': d.get('projects') or {}})
    d_mine['windows_file'] = str(f)


def stamp() -> tuple:
    l = []
    for p in [kit.OPEN, kit.COMMENTS, *history_files()]:
        try:
            st = p.stat()
            l.append((str(p), st.st_mtime_ns, st.st_size))
        except FileNotFoundError:
            l.append((str(p), None))
    return tuple(l)


def main():
    read_message()                                    # the extension's hello

    def reader():
        while True:
            m = read_message()
            if m.get('comment'):
                add_comment(m['comment'])
            if m.get('windows'):
                write_windows(m['windows'])

    threading.Thread(target=reader, daemon=True).start()
    last = None
    while True:
        now = stamp()
        if now != last:
            last = now
            send({'notes': notes()})
        time.sleep(0.5)


if __name__ == '__main__':
    main()
