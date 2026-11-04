"""macOS desktops (Spaces) for the Chrome kit: which desktop a window is on, which desktop each screen shows now,
the iTerm2 window of a Claude session, and the Chrome window the kit opened for each project.

macOS has no public API for desktops: SkyLight's private calls are read here (read-only; they work with SIP on,
tested on macOS 26.6, 4 Nov 2026), with the public window list (CoreGraphics), through ctypes: standard library only
(the kit runs on /usr/bin/python3). Facts measured on this Mac (4 Nov 2026):
  - each screen has its own desktops ("Displays have separate Spaces", the macOS default);
  - iTerm2's AppleScript window id is the macOS window number (CGWindowID);
  - a Chrome window's project is known only for the windows the kit opened (agent-chrome show): one window per
    project (two projects on one desktop with the same profile get two windows; the user, 4 Nov 2026);
  - no program can move a window to a desktop that is not shown (macOS 26, SIP on): a window gets on a desktop by
    being created while that desktop is shown, on that desktop's screen.
Reads and writes $CHROME_STATE/windows/desktop-windows.json ({CGWindowID: {project, profile, ts}}).
"""
from __future__ import annotations  # "str | None" hints on Python 3.9

import ctypes
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chrome_kit as kit  # noqa: E402

_CF = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
_CG = ctypes.CDLL('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
_CS = ctypes.CDLL('/System/Library/Frameworks/ColorSync.framework/ColorSync')   # display UUIDs
_SL = ctypes.CDLL('/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight')
_P = ctypes.c_void_p
UTF8 = 0x08000100
CACHE = kit.WINDOWS / 'desktop-windows.json'
# iTerm2 runs click commands with PATH=/usr/bin:/bin:/usr/sbin:/sbin: Homebrew's tmux by its full path (4 Nov 2026)
TMUX = shutil.which('tmux') or next((p for p in ('/opt/homebrew/bin/tmux', '/usr/local/bin/tmux') if os.path.exists(p)), 'tmux')


class _Rect(ctypes.Structure):
    _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double), ('w', ctypes.c_double), ('h', ctypes.c_double)]


for _lib, _name, _res, _args in [
    (_CF, 'CFGetTypeID', ctypes.c_ulong, [_P]), (_CF, 'CFArrayGetTypeID', ctypes.c_ulong, []),
    (_CF, 'CFDictionaryGetTypeID', ctypes.c_ulong, []), (_CF, 'CFStringGetTypeID', ctypes.c_ulong, []),
    (_CF, 'CFNumberGetTypeID', ctypes.c_ulong, []), (_CF, 'CFBooleanGetTypeID', ctypes.c_ulong, []),
    (_CF, 'CFArrayGetCount', ctypes.c_long, [_P]), (_CF, 'CFArrayGetValueAtIndex', _P, [_P, ctypes.c_long]),
    (_CF, 'CFDictionaryGetCount', ctypes.c_long, [_P]), (_CF, 'CFDictionaryGetKeysAndValues', None, [_P, _P, _P]),
    (_CF, 'CFStringGetLength', ctypes.c_long, [_P]),
    (_CF, 'CFStringGetCString', ctypes.c_bool, [_P, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]),
    (_CF, 'CFNumberGetValue', ctypes.c_bool, [_P, ctypes.c_int, _P]), (_CF, 'CFNumberIsFloatType', ctypes.c_bool, [_P]),
    (_CF, 'CFBooleanGetValue', ctypes.c_bool, [_P]), (_CF, 'CFRelease', None, [_P]),
    (_CF, 'CFNumberCreate', _P, [_P, ctypes.c_int, _P]), (_CF, 'CFArrayCreate', _P, [_P, _P, ctypes.c_long, _P]),
    (_CF, 'CFUUIDCreateString', _P, [_P, _P]),
    (_CG, 'CGWindowListCopyWindowInfo', _P, [ctypes.c_uint32, ctypes.c_uint32]),
    (_CG, 'CGGetActiveDisplayList', ctypes.c_int32, [ctypes.c_uint32, _P, _P]),
    (_CS, 'CGDisplayCreateUUIDFromDisplayID', _P, [ctypes.c_uint32]),
    (_CG, 'CGDisplayIsBuiltin', ctypes.c_uint32, [ctypes.c_uint32]), (_CG, 'CGDisplayBounds', _Rect, [ctypes.c_uint32]),
    (_SL, 'SLSMainConnectionID', ctypes.c_int, []), (_SL, 'SLSCopyManagedDisplaySpaces', _P, [ctypes.c_int]),
    (_SL, 'SLSCopySpacesForWindows', _P, [ctypes.c_int, ctypes.c_int, _P]),
]:
    getattr(_lib, _name).restype, getattr(_lib, _name).argtypes = _res, _args
_T = {k: getattr(_CF, f'CF{k}GetTypeID')() for k in ('Array', 'Dictionary', 'String', 'Number', 'Boolean')}
_CID = _SL.SLSMainConnectionID()


def _py(ref):
    """A CoreFoundation value -> Python (arrays, dictionaries, strings, numbers, booleans; anything else None)."""
    if not ref:
        return None
    t = _CF.CFGetTypeID(ref)
    if t == _T['Array']:
        return [_py(_CF.CFArrayGetValueAtIndex(ref, i)) for i in range(_CF.CFArrayGetCount(ref))]
    if t == _T['Dictionary']:
        n = _CF.CFDictionaryGetCount(ref)
        keys, vals = (_P * n)(), (_P * n)()
        _CF.CFDictionaryGetKeysAndValues(ref, keys, vals)
        return {_py(k): _py(v) for k, v in zip(keys, vals)}
    if t == _T['String']:
        size = _CF.CFStringGetLength(ref) * 4 + 1
        buf = ctypes.create_string_buffer(size)
        return buf.value.decode() if _CF.CFStringGetCString(ref, buf, size, UTF8) else None
    if t == _T['Number']:
        if _CF.CFNumberIsFloatType(ref):
            v = ctypes.c_double()
            _CF.CFNumberGetValue(ref, 13, ctypes.byref(v))   # kCFNumberDoubleType
        else:
            v = ctypes.c_int64()
            _CF.CFNumberGetValue(ref, 4, ctypes.byref(v))    # kCFNumberSInt64Type
        return v.value
    if t == _T['Boolean']:
        return bool(_CF.CFBooleanGetValue(ref))
    return None


def _copied(ref):
    """A CF object we own (a Copy/Create call) -> Python, then released."""
    try:
        return _py(ref)
    finally:
        if ref:
            _CF.CFRelease(ref)


# ---------------------------------------------------------------- screens and desktops
def screens() -> dict:
    """{display UUID: {'name': 'built-in screen' | 'external screen' [N], 'bounds': (x, y, w, h)}}"""
    ids, n = (ctypes.c_uint32 * 16)(), ctypes.c_uint32()
    _CG.CGGetActiveDisplayList(16, ids, ctypes.byref(n))
    d, n_ext = {}, 0
    for did in ids[:n.value]:
        uuid = _copied(_CF.CFUUIDCreateString(None, _CS.CGDisplayCreateUUIDFromDisplayID(did)))
        b = _CG.CGDisplayBounds(did)
        builtin = bool(_CG.CGDisplayIsBuiltin(did))
        n_ext += not builtin
        d[(uuid or '').upper()] = {'name': 'built-in screen' if builtin else f'external screen {n_ext}',
                                   'bounds': (b.x, b.y, b.w, b.h)}
    if n_ext == 1:
        for v in d.values():
            v['name'] = v['name'].replace('external screen 1', 'external screen')
    return d


def layout() -> dict:
    """{space id: {'screen': name, 'n': its number on that screen (1 = leftmost), 'shown': bool, 'fullscreen': bool}}"""
    d_scr = screens()
    d = {}
    for disp in _copied(_SL.SLSCopyManagedDisplaySpaces(_CID)) or []:
        uid = (disp.get('Display Identifier') or '').upper()
        name = d_scr.get(uid, {}).get('name') or ('all screens' if uid == 'MAIN' else f'screen {uid[:8]}')
        shown = (disp.get('Current Space') or {}).get('ManagedSpaceID')
        for i, s in enumerate(disp.get('Spaces') or [], 1):
            d[s['ManagedSpaceID']] = {'screen': name, 'n': i, 'shown': s['ManagedSpaceID'] == shown,
                                      'fullscreen': s.get('type') == 4}
    return d


def label(space: int, d_lay: dict) -> str:
    s = d_lay.get(space)
    return f"{s['screen']}, desktop {s['n']}" + (' (full screen)' if s['fullscreen'] else '') if s else f'desktop id {space}'


def spaces_of(wid: int) -> list:
    """The desktops (space ids) a window is on: one; several for a window shown on all desktops; none when hidden."""
    n = ctypes.c_int64(wid)
    num = _CF.CFNumberCreate(None, 4, ctypes.byref(n))
    arr = _CF.CFArrayCreate(None, (_P * 1)(num), 1, ctypes.addressof(ctypes.c_char.in_dll(_CF, 'kCFTypeArrayCallBacks')))
    try:
        return [int(x) for x in _copied(_SL.SLSCopySpacesForWindows(_CID, 7, arr)) or []]
    finally:
        _CF.CFRelease(arr)
        _CF.CFRelease(num)


def windows(pid: int | None = None) -> list:
    """Normal windows (layer 0) of every desktop, front to back: {'id', 'pid', 'owner', 'title', 'rect': (x, y, w, h)}."""
    l = []
    for w in _copied(_CG.CGWindowListCopyWindowInfo(0, 0)) or []:   # kCGWindowListOptionAll
        b = w.get('kCGWindowBounds') or {}
        if w.get('kCGWindowLayer') == 0 and (pid is None or w.get('kCGWindowOwnerPID') == pid):
            l.append({'id': w['kCGWindowNumber'], 'pid': w.get('kCGWindowOwnerPID'), 'owner': w.get('kCGWindowOwnerName'),
                      'title': w.get('kCGWindowName') or '', 'rect': tuple(int(b.get(k, 0)) for k in ('X', 'Y', 'Width', 'Height'))})
    return l


# ---------------------------------------------------------------- the terminal of a Claude session
def osa(script: str) -> str:
    r = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ''


def session_ttys() -> list:
    """The terminals that show this shell: the clients of its tmux session, else the shell's own terminal."""
    if os.environ.get('TMUX'):
        pane = ['-t', os.environ['TMUX_PANE']] if os.environ.get('TMUX_PANE') else []
        sess = subprocess.run([TMUX, 'display', '-p', *pane, '#{session_name}'], capture_output=True, text=True).stdout.strip()
        out = subprocess.run([TMUX, 'list-clients', '-t', sess, '-F', '#{client_tty}'], capture_output=True, text=True).stdout
        return out.split()
    pid = os.getpid()
    for _ in range(20):   # up the parents: the first one with a terminal
        r = subprocess.run(['ps', '-o', 'ppid=,tty=', '-p', str(pid)], capture_output=True, text=True).stdout.split()
        if len(r) < 2:
            break
        if r[1] not in ('??', '-'):
            return [f'/dev/{r[1]}']
        pid = int(r[0])
    return []


def iterm_windows(clicked: bool = False) -> list:
    """The iTerm2 window ids (= CGWindowIDs) showing this session (clicked: iTerm2's current window, where the user just
    clicked). Empty when iTerm2 does not run or no window of it shows the session (the user is on the phone)."""
    if clicked:
        out = osa('if application "iTerm2" is running then tell application "iTerm2" to get id of current window')
        return [int(out)] if out.isdigit() else []
    s_tty = set(session_ttys())
    out = osa('if application "iTerm2" is running then tell application "iTerm2"\n set out to ""\n'
              ' repeat with w in windows\n repeat with t in tabs of w\n repeat with s in sessions of t\n'
              '  set out to out & (id of w as text) & "|" & (tty of s) & linefeed\n'
              ' end repeat\n end repeat\n end repeat\n return out\nend tell')
    l = []
    for line in out.splitlines():
        wid, _, tty = line.partition('|')
        if tty in s_tty and wid.isdigit() and int(wid) not in l:
            l.append(int(wid))
    return l


def session_desktop(clicked: bool = False):
    """(space id, iTerm2 window rect, layout) of the session's terminal, preferring a desktop shown now; (None, None,
    layout) when no iTerm2 window shows it."""
    d_lay = layout()
    d_rect = {w['id']: w['rect'] for w in windows()}
    l_cand = [(sp, d_rect.get(wid)) for wid in iterm_windows(clicked) for sp in spaces_of(wid)]
    l_cand.sort(key=lambda c: not d_lay.get(c[0], {}).get('shown'))
    return (*(l_cand[0] if l_cand else (None, None)), d_lay)


def clicked_folder() -> str | None:
    """The folder of the terminal the user just clicked in (iTerm2's current session): its tmux client's pane folder;
    None when it shows no tmux session."""
    tty = osa('if application "iTerm2" is running then tell application "iTerm2" to get tty of current session of current window')
    r = subprocess.run([TMUX, 'display', '-p', '-c', tty, '#{pane_current_path}'], capture_output=True, text=True) if tty else None
    return r.stdout.strip() or None if r and r.returncode == 0 else None


# ---------------------------------------------------------------- Chrome's windows, one per project
def chrome_windows(pid: int) -> list:
    """Chrome's AppleScript windows: [{'as_id', 'rect': (x, y, w, h)}] (its ids are not CGWindowIDs: matched by rect)."""
    out = osa('if application "Google Chrome" is running then tell application "Google Chrome"\n set out to ""\n'
              ' repeat with w in windows\n set b to bounds of w\n'
              '  set out to out & (id of w as text) & "|" & (item 1 of b) & "|" & (item 2 of b) & "|" & (item 3 of b) & "|" & (item 4 of b) & linefeed\n'
              ' end repeat\n return out\nend tell')
    l = []
    for line in out.splitlines():
        p = line.split('|')
        if len(p) == 5 and all(re.fullmatch(r'-?\d+', x) for x in p):
            x, y, r, b = (int(v) for v in p[1:])
            l.append({'as_id': int(p[0]), 'rect': (x, y, r - x, b - y)})
    return l


def project_windows(l_cg: list) -> dict:
    """{CGWindowID: {project, profile, ts}}: the windows the kit opened for a project and that still exist (the
    record, cleaned of windows that are gone)."""
    s_ids = {w['id'] for w in l_cg}
    d = {int(k): v for k, v in kit.read_json(CACHE).items() if k.isdigit() and int(k) in s_ids}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    kit.write_json(CACHE, {str(k): v for k, v in d.items()})
    return d


def remember(wid: int, project: str, profile: str):
    d = kit.read_json(CACHE)
    d[str(wid)] = {'project': project, 'profile': profile, 'ts': int(time.time())}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    kit.write_json(CACHE, d)


def pick(l_cg: list, d_win: dict, project: str, profile: str, space: int, d_spaces: dict) -> dict | None:
    """The front-most window the kit opened for this project, in this profile, on this desktop (the window list is
    front to back), else None. Never a window of another project, even in the same profile."""
    return next((w for w in l_cg if (d_win.get(w['id']) or {}).get('project') == project
                 and d_win[w['id']].get('profile') == profile and space in d_spaces.get(w['id'], [])), None)


def as_id_of(rect: tuple, l_as: list) -> int | None:
    return next((w['as_id'] for w in l_as if w['rect'] == rect), None)


def cg_of(rect: tuple, l_cg: list, exclude: set = frozenset()) -> dict | None:
    return next((w for w in l_cg if w['rect'] == rect and w['id'] not in exclude), None)


if __name__ == '__main__':   # a look at this Mac: python3 -I desktops.py
    sp, rect, lay = session_desktop()
    for k, v in lay.items():
        print(f"{k:>6}  {label(k, lay)}{'  <- shown' if v['shown'] else ''}{'  <- this session' if k == sp else ''}")
    if sp is None:
        print('no iTerm2 window shows this session')
