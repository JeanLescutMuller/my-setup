"""Headless test of the "Agent tab notes" extension (chrome/extension/) and its native host (chrome/native_host.py),
against a temporary $CHROME_STATE, in a Chrome for Testing with a throwaway profile (branded Chrome ignores
--load-extension since version 137). Nothing touches the real record or a real Chrome profile.

Usage: <python with playwright 1.55> tests/test_extension.py <Chrome for Testing binary> <scratch dir> [<screenshots dir>]
  e.g. npx @puppeteer/browsers install chrome@stable --path <scratch>   # gets a Chrome for Testing
Reads: chrome/extension/, chrome/native_host.py, chrome/chrome_kit.py, chrome/agent_chrome.py.
Writes: in <scratch dir>: state/ (the temporary record), profile/ (throwaway, with NativeMessagingHosts/), host.sh;
screenshots in <screenshots dir> (default <scratch dir>). Prints PASS/FAIL per check; terminates its Chrome.
"""
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
EXT, EXT_ID, HOST = KIT / 'extension', 'hfnfcdbehfbggjaccimmnolmhdkbfdie', 'com.jeanlescut.agent_tab_notes'
SCRATCH = Path(sys.argv[2]).resolve()
SHOTS = Path(sys.argv[3]).resolve() if len(sys.argv) > 3 else SCRATCH
STATE = SCRATCH / 'state'
shutil.rmtree(STATE, ignore_errors=True)
os.environ['CHROME_STATE'] = str(STATE)
os.environ.pop('TMUX_PANE', None)
PS = SCRATCH / 'ps.txt'                     # the "user's Chrome", started an hour ago: tabs opened since then are shown
PS.write_text('  501 01:00:00 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome\n')
os.environ['CHROME_TEST_PS'] = str(PS)
sys.path.insert(0, str(KIT))
import chrome_kit as kit  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

GEN = '331a94e7-f123-4e09-a755-cdc63980187f'
SID, SID2 = '3f2a9c1e-77b0-4d1e-9a51-0c0ffee12345', '7d41e2aa-1b9c-4c55-8e0f-2a6b9c3d4e5f'
PROJ = SCRATCH / 'job-applications'         # a "repo": its folder name is the project
(PROJ / '.git').mkdir(parents=True, exist_ok=True)
results = []

# "Covered": visible page elements that paint something (text, image, control, coloured box) under the bar
MEASURE = """() => {
  const H = parseFloat(getComputedStyle(document.documentElement).marginTop) || 28;   // push.js: html margin = the bar's height
  const bar = [...document.querySelectorAll('agent-tab-note')];
  const painted = e => {
    if (e === document.documentElement || e === document.body || bar.includes(e)) return false;
    const cs = getComputedStyle(e);
    if (cs.visibility !== 'visible' || +cs.opacity === 0 || cs.display === 'none') return false;
    if (/^(IMG|SVG|INPUT|BUTTON|TEXTAREA|SELECT|IFRAME|VIDEO|CANVAS)$/i.test(e.tagName)) return true;
    if ([...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return true;
    return cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent';
  };
  return [...document.querySelectorAll('body *')].filter(painted).filter(e => { const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.top < H && r.bottom > 0; }).map(e => e.tagName).slice(0, 5);
}"""


def check(name, ok, detail=''):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {str(detail)[:160]}", flush=True)


class Pages(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = ("<!doctype html><title>Fixed header page</title><body style='margin:0;font:16px sans-serif'>"
                "<header style='position:fixed;top:0;left:0;right:0;height:56px;background:#0a66c2;color:#fff;padding:12px;"
                f"box-sizing:border-box'>Fixed site header {self.path} (like LinkedIn logged in)</header>"
                "<main style='padding:72px 24px'><h1>A page with a fixed header</h1><p>Lorem ipsum.</p></main></body>").encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def claim(*args, sid=SID):
    r = subprocess.run(['/usr/bin/python3', '-I', str(KIT / 'agent_chrome.py'), *args], cwd=PROJ, capture_output=True,
                       text=True, env={**os.environ, 'CLAUDE_CODE_SESSION_ID': sid})
    assert r.returncode == 0, r.stderr


def bar_text(page) -> str:
    """The bar's text, read through its closed shadow root (CDP DOM with pierce)."""
    cdp = page.context.new_cdp_session(page)
    root = cdp.send('DOM.getDocument', {'depth': -1, 'pierce': True})['root']
    out, stack, inside = [], [(root, False)], False
    while stack:
        n, inside = stack.pop()
        inside = inside or n.get('localName') == 'agent-tab-note'
        if inside and n.get('nodeType') == 3:
            out.append(n.get('nodeValue', ''))
        kids = n.get('children', []) + n.get('shadowRoots', [])
        stack += [(k, inside) for k in reversed(kids)]
    cdp.detach()
    return ''.join(out)


def bar_on_top(page) -> bool:
    return page.evaluate("document.elementFromPoint(innerWidth / 2, 8)?.tagName") == 'AGENT-TAB-NOTE'


def windows(ctx, ctl, base):
    """7. One agent window per project (extension/place.js): a session's tab group of project A that lands in another
    window moves to A's window; the user's tabs never move; a window owned by B is never taken."""
    js = ctl.evaluate
    sids = iter(['aaaa0000-0000-4000-8000-00000000000%d' % i for i in range(1, 9)])
    l_proj = {}
    for name in ('proj-a', 'proj-b'):
        (SCRATCH / name / '.git').mkdir(parents=True, exist_ok=True)
        l_proj[name] = str(SCRATCH / name)

    def agent_group(win, project, path):   # what Claude in Chrome does: an inactive tab, in its own group
        tab = js(f"chrome.tabs.create({{windowId: {win}, url: '{base}/{path}', active: false}}).then(t => t.id)")
        gid = js(f"chrome.tabs.group({{tabIds: [{tab}], createProperties: {{windowId: {win}}}}})")
        return tab, gid

    def rec(tab, project, url):
        kit.record([{'event': 'open', 'tab_id': tab, 'url': url, 'profile': 'Claude - general', 'device_id': GEN}],
                   {'session_id': next(sids), 'cwd': l_proj[project]})

    tab_of = lambda t: js(f'chrome.tabs.get({t})')
    s_win = lambda: set(js("chrome.windows.getAll({windowTypes: ['normal']}).then(l => l.map(w => w.id))"))
    mapping = lambda: js("chrome.storage.local.get('map').then(r => r.map || {})")
    active = lambda w: js(f'chrome.tabs.query({{windowId: {w}, active: true}}).then(l => l[0].id)')
    marker = lambda proj: f'chrome-extension://{EXT_ID}/window.html?project={proj}&profile=Claude+-+general'

    # 7a. `agent-chrome open-profile-window` opened A's window (its first tab: window.html?project=proj-a)
    w_a = js(f"chrome.windows.create({{focused: false, url: '{marker('proj-a')}'}}).then(w => w.id)")
    time.sleep(1.5)
    d_rep = kit.read_json(STATE / 'windows' / 'Claude - general.json')
    l_mk = js(f'chrome.tabs.query({{windowId: {w_a}}})')
    check('7a. the window opened for A (marker tab, pinned) is A\'s window; reported in windows/<profile>.json',
          mapping().get('proj-a') == w_a and l_mk[0]['pinned'] and w_a in d_rep.get('windows', [])
          and d_rep.get('projects', {}).get('proj-a') == w_a, (mapping(), d_rep))

    # 7b. the user's window (focused, a page of theirs); a new session of A lands there
    w_u = js(f"chrome.windows.create({{focused: true, url: '{base}/user-page'}}).then(w => w.id)")
    time.sleep(1)
    t_user = active(w_u)
    t1, g1 = agent_group(w_u, 'proj-a', 'a1')
    time.sleep(1)
    pg = next(x for x in ctx.pages if x.url.endswith('/a1'))   # a CDP session attached before the move (as Claude in Chrome's)
    a_before = active(w_a)
    rec(t1, 'proj-a', f'{base}/a1')
    time.sleep(2.5)
    t1i = tab_of(t1)
    check('7b. A\'s group moved from the user\'s window to A\'s window, same group id, not made active',
          t1i['windowId'] == w_a and t1i['groupId'] == g1 and not t1i['active'] and active(w_a) == a_before, t1i)
    check('7b. the user\'s tab and window untouched (still there, still active)',
          tab_of(t_user)['windowId'] == w_u and active(w_u) == t_user and w_u in s_win())
    try:
        title = pg.evaluate('document.title')
        pg.goto(f'{base}/a1-next')
        shot = len(pg.screenshot())
        ok = 'Fixed header' in title and tab_of(t1)['url'].endswith('/a1-next') and shot > 1000
    except Exception as e:  # noqa: BLE001
        ok, title = False, str(e)
    check('7b. after the move the same CDP session still reads, navigates and screenshots the tab', ok, title)

    # 7c. a session of B lands in A's window: B gets its own new window (A's is never taken)
    t2, g2 = agent_group(w_a, 'proj-b', 'b1')
    rec(t2, 'proj-b', f'{base}/b1')
    time.sleep(2.5)
    t2i, m = tab_of(t2), mapping()
    w_b = m.get('proj-b')
    check('7c. B landed in A\'s window: a new window for B, its group moved there; A keeps its window',
          w_b not in (None, w_a, w_u) and t2i['windowId'] == w_b and t2i['groupId'] == g2 and m.get('proj-a') == w_a, (m, t2i))
    check('7c. B\'s new window starts with its marker tab', any('project=proj-b' in (x.get('url') or x.get('pendingUrl') or '')
                                                             for x in js(f'chrome.tabs.query({{windowId: {w_b}}})')))

    # 7d. a window created by the group's arrival (unfocused, only a new tab): moved out, then closed
    w_new = js("chrome.windows.create({focused: false}).then(w => w.id)")
    time.sleep(0.5)
    t3, _ = agent_group(w_new, 'proj-a', 'a2')
    rec(t3, 'proj-a', f'{base}/a2')
    time.sleep(2.5)
    check('7d. a window the arrival created: group moved to A\'s, the empty window closed',
          tab_of(t3)['windowId'] == w_a and w_new not in s_win(), s_win())

    # 7e. a group holding a user's tab (not in open.json): never moved
    t4, g4 = agent_group(w_u, 'proj-a', 'a3')
    t_mine = js(f"chrome.tabs.create({{windowId: {w_u}, url: '{base}/user-2', active: false}}).then(t => t.id)")
    js(f'chrome.tabs.group({{tabIds: [{t_mine}], groupId: {g4}}})')
    rec(t4, 'proj-a', f'{base}/a3')
    time.sleep(2.5)
    check('7e. a group with a user\'s tab in it stays where it is', tab_of(t4)['windowId'] == w_u and tab_of(t_mine)['windowId'] == w_u)
    log = js("chrome.storage.session.get('placeLog').then(r => r.placeLog || [])")
    print('      placeLog:', [(x.get('action'), x.get('project'), x.get('tab')) for x in log][-8:])


def main():
    profile = SCRATCH / 'profile'
    shutil.rmtree(profile, ignore_errors=True)
    (profile / 'NativeMessagingHosts').mkdir(parents=True)
    host_sh = SCRATCH / 'host.sh'               # what modules/chrome_kit.sh's manifest points to, with the test's record
    host_sh.write_text(f"#!/bin/sh\nCHROME_STATE='{STATE}' CHROME_TEST_PS='{PS}' exec /usr/bin/python3 '{KIT / 'native_host.py'}' \"$@\"\n")
    host_sh.chmod(0o755)
    (profile / 'NativeMessagingHosts' / f'{HOST}.json').write_text(json.dumps(
        {'name': HOST, 'description': 'test', 'path': str(host_sh), 'type': 'stdio', 'allowed_origins': [f'chrome-extension://{EXT_ID}/']}))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Pages)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_port}'
    proc = subprocess.Popen([sys.argv[1], '--headless=new', f'--user-data-dir={profile}', '--remote-debugging-port=0',
                             '--no-first-run', '--no-default-browser-check', '--window-size=1280,800',
                             f'--load-extension={EXT}', f'--disable-extensions-except={EXT}', 'about:blank'],
                            stdout=subprocess.DEVNULL, stderr=open(SCRATCH / 'chrome.stderr.log', 'w'))
    try:
        port_file = profile / 'DevToolsActivePort'
        for _ in range(120):
            if port_file.exists() and port_file.read_text().strip():
                break
            time.sleep(0.25)
        with sync_playwright() as p:
            ctx = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port_file.read_text().split()[0]}").contexts[0]
            ctl = ctx.new_page()
            ctl.goto(f'chrome-extension://{EXT_ID}/sidepanel.html')
            check('extension loaded with its fixed id', ctl.title() == 'Agent tab note', ctl.title())
            newest = lambda: max(t['id'] for t in ctl.evaluate('chrome.tabs.query({})'))
            badge = lambda t: ctl.evaluate(f'chrome.action.getBadgeText({{tabId: {t}}})')

            # 1. a session opens a tab and says the user must act: the bar shows the required fields, covers nothing
            page = ctx.new_page()
            page.set_viewport_size({'width': 1280, 'height': 720})
            page.goto(f'{base}/apply')
            tid = newest()
            page.screenshot(path=str(SHOTS / 'ext_bar_before.png'))
            kit.record([{'event': 'open', 'tab_id': tid, 'url': f'{base}/apply', 'profile': 'Claude - LinkedIn',
                         'device_id': GEN}], {'session_id': SID, 'cwd': str(PROJ)})
            claim('authorize-tab', 'Apply to job 4312 (Data Engineer, Zurich)', '--visibility', 'focused',
                  '--visibility-reason', 'the human solves a captcha', '--project', 'job-applications')
            active = lambda t: ctl.evaluate(f'chrome.tabs.get({t}).then(t => t.active)')
            other = ctx.new_page()            # the human is elsewhere: another tab in front
            other.goto(f'{base}/job')
            time.sleep(2)
            check('focused, no need yet: the tab is not brought to the front', not active(tid))
            claim('mark-as-needing-human', 'solve the captcha')
            time.sleep(2)
            check('focused + mark-as-needing-human: the tab is brought to the front', active(tid))
            other.bring_to_front()
            time.sleep(2)
            check('brought to the front once: the human moved away, it stays behind', not active(tid))
            other.close()
            time.sleep(1)
            txt = bar_text(page)
            opened = kit.read_open()[str(tid)]['opened_ts']
            day = time.strftime('%d', time.localtime(opened))
            check('bar on top, red, badge "!"', bar_on_top(page) and badge(tid) == '!')
            check('bar fields: opened (date + time), session UUID, project, purpose, NEEDS HUMAN; no job',
                  all(s in txt for s in ['opened', day, SID, 'job-applications', 'Apply to job 4312', 'NEEDS HUMAN: solve the captcha'])
                  and 'job ' not in txt.replace('job-applications', '').replace('to job', ''), txt)
            covered = page.evaluate(MEASURE)
            check('nothing covered (page and its fixed header pushed down)', covered == [], covered)
            page.screenshot(path=str(SHOTS / 'ext_bar_after.png'))
            page.reload()
            time.sleep(1)
            check('after a reload: bar back, nothing covered', bar_on_top(page) and page.evaluate(MEASURE) == [])

            # 2. a tab opened by a scheduled job: the bar names the job
            jpage = ctx.new_page()
            jpage.set_viewport_size({'width': 1280, 'height': 720})
            jpage.goto(f'{base}/job')
            jtid = newest()
            kit.record([{'event': 'open', 'tab_id': jtid, 'url': f'{base}/job', 'profile': 'Claude - general', 'device_id': GEN,
                         'purpose': 'post the weekly listing', 'job': 'marketplace-seller.post'}], {'session_id': SID2, 'cwd': str(PROJ)})
            time.sleep(2)
            jtxt = bar_text(jpage)
            check('a job\'s tab: the bar shows the job', 'job' in jtxt and 'marketplace-seller.post' in jtxt, jtxt)
            jpage.screenshot(path=str(SHOTS / 'ext_bar_job.png'))
            jpage.close()

            # 3. comment round trip: typed in the side panel -> comments.jsonl; the agent's reply (agent-chrome reply-to-human)
            sp = ctx.new_page()
            sp.set_viewport_size({'width': 380, 'height': 640})
            sp.goto(f'chrome-extension://{EXT_ID}/sidepanel.html?tabId={tid}')
            time.sleep(1)
            body = sp.inner_text('body')
            check('side panel details: visibility and why that visibility', 'why that visibility' in body and 'focused' in body
                  and 'the human solves a captcha' in body, body[:300])
            sp.fill('#text', 'Captcha solved, go on')
            sp.click('button')
            time.sleep(1.5)
            rows = [json.loads(x) for x in kit.COMMENTS.read_text().splitlines()] if kit.COMMENTS.exists() else []
            last = rows[-1] if rows else {}
            check('comment -> comments.jsonl: ts, dt, session_id, tab_id, url, text',
                  list(last) == ['ts', 'dt', 'session_id', 'tab_id', 'url', 'text'] and last['session_id'] == SID
                  and last['tab_id'] == tid and last['url'] == f'{base}/apply' and last['text'] == 'Captcha solved, go on', last)
            claim('mark-as-human-done')
            claim('reply-to-human', 'Thanks, I see it. Continuing the application.')
            time.sleep(2)
            body = sp.inner_text('body')
            check('side panel thread: the comment, then the agent\'s reply', body.find('Captcha solved') < body.find('Continuing the application') and 'Captcha solved' in body, body[:120])
            sp.screenshot(path=str(SHOTS / 'ext_side_panel_thread.png'))
            sp.close()
            txt = bar_text(page)
            check('bar after mark-as-human-done + reply-to-human: no NEEDS HUMAN, agent message shown, badge not "!"',
                  'NEEDS HUMAN' not in txt and 'agent: Thanks, I see it' in txt and badge(tid) != '!', txt)
            page.screenshot(path=str(SHOTS / 'ext_bar_reply.png'))

            # 4. side panel: no click -> refused; a click on the bar's "details · reply" -> opened
            sw = next(w for w in ctx.service_workers if EXT_ID in w.url)
            r = sw.evaluate(f'chrome.sidePanel.open({{tabId: {tid}}}).then(() => "opened", e => String(e))')
            check('side panel never opens by itself', r != 'opened', r)
            h = page.evaluate('parseFloat(getComputedStyle(document.documentElement).marginTop)')
            page.mouse.click(1280 - 120, h - 14)      # "details · reply": the bar's right end, on its last line
            time.sleep(1)
            r = ctl.evaluate("chrome.storage.session.get('lastOpen').then(r => r.lastOpen)")
            check('a click on the bar opens the side panel', r == 'opened', r)

            # 5. LinkedIn (a quiet site): no bar unless the user must act
            lpage = ctx.new_page()
            lpage.set_viewport_size({'width': 1280, 'height': 720})
            try:
                lpage.goto('https://www.linkedin.com/jobs/search?keywords=engineer&location=Zurich', wait_until='domcontentloaded', timeout=30000)
                lpage.wait_for_timeout(2000)
                ltid = newest()
                kit.record([{'event': 'open', 'tab_id': ltid, 'url': lpage.url, 'profile': 'Claude - LinkedIn', 'device_id': GEN,
                             'purpose': 'read job offers'}], {'session_id': SID2, 'cwd': str(PROJ)})
                time.sleep(2)
                check('LinkedIn, nothing to do: no bar, page untouched', not bar_on_top(lpage)
                      and lpage.evaluate('getComputedStyle(document.documentElement).marginTop') == '0px' and badge(ltid) == 'AI')
                kit.record([{'event': 'needs_human', 'tab_id': ltid, 'needs_human': 'log in to LinkedIn'}], {'session_id': SID2, 'cwd': str(PROJ)})
                time.sleep(2)
                covered = lpage.evaluate(MEASURE)
                check('LinkedIn, user must act: bar shown, nothing covered', bar_on_top(lpage) and covered == [], covered)
                lpage.screenshot(path=str(SHOTS / 'ext_bar_linkedin.png'))
            except Exception as e:  # noqa: BLE001  offline: skip, say so
                print(f'SKIP  LinkedIn checks: {str(e)[:80]}')
            lpage.close()

            # 6. the tab is closed in the record: bar and page margin gone
            kit.record([{'event': 'close', 'tab_id': tid}], {'session_id': SID, 'cwd': str(PROJ)})
            time.sleep(2)
            check('close: bar gone, page margin back to 0', not page.evaluate("!!document.querySelector('agent-tab-note')")
                  and page.evaluate('getComputedStyle(document.documentElement).marginTop') == '0px' and badge(tid) == '')

            windows(ctx, ctl, base)
    finally:
        proc.terminate()
        proc.wait(30)
        srv.shutdown()
    time.sleep(2)
    check('Chrome gone: its windows report removed (the host deletes it when the port closes)',
          not (STATE / 'windows' / 'Claude - general.json').exists())
    print(f'{sum(results)}/{len(results)} checks passed')
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
