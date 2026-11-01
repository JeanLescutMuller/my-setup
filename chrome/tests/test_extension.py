"""Headless test of the "Agent tab notes" extension (chrome/extension/) and its native host (chrome/native_host.py),
against a temporary $CHROME_STATE, in a Chrome for Testing with a throwaway profile (branded Chrome ignores
--load-extension since version 137). Nothing touches the real record or a real Chrome profile.

Usage: <python with playwright 1.55> tests/test_extension.py <Chrome for Testing binary> <scratch dir> [<screenshots dir>]
  e.g. npx @puppeteer/browsers install chrome@stable --path <scratch>   # gets a Chrome for Testing
Reads: chrome/extension/, chrome/native_host.py, chrome/chrome_kit.py, chrome/chrome_claim.py.
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
    r = subprocess.run(['/usr/bin/python3', '-I', str(KIT / 'chrome_claim.py'), *args], cwd=PROJ, capture_output=True,
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
            claim('--purpose', 'Apply to job 4312 (Data Engineer, Zurich)', '--needs-human', 'solve the captcha')
            time.sleep(2)
            txt = bar_text(page)
            opened = kit.read_open()[str(tid)]['opened_ts']
            day = time.strftime('%d', time.localtime(opened))
            check('bar on top, red, badge "!"', bar_on_top(page) and badge(tid) == '!')
            check('bar fields: opened (date + time), session UUID, project, purpose, YOUR TURN; no job',
                  all(s in txt for s in ['opened', day, SID, 'job-applications', 'Apply to job 4312', 'YOUR TURN: solve the captcha'])
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

            # 3. comment round trip: typed in the side panel -> comments.jsonl; the agent's reply (chrome-claim --message)
            sp = ctx.new_page()
            sp.set_viewport_size({'width': 380, 'height': 640})
            sp.goto(f'chrome-extension://{EXT_ID}/sidepanel.html?tabId={tid}')
            time.sleep(1)
            sp.fill('#text', 'Captcha solved, go on')
            sp.click('button')
            time.sleep(1.5)
            rows = [json.loads(x) for x in kit.COMMENTS.read_text().splitlines()] if kit.COMMENTS.exists() else []
            last = rows[-1] if rows else {}
            check('comment -> comments.jsonl: ts, dt, session_id, tab_id, url, text',
                  list(last) == ['ts', 'dt', 'session_id', 'tab_id', 'url', 'text'] and last['session_id'] == SID
                  and last['tab_id'] == tid and last['url'] == f'{base}/apply' and last['text'] == 'Captcha solved, go on', last)
            claim('done')
            claim('--message', 'Thanks, I see it. Continuing the application.')
            time.sleep(2)
            body = sp.inner_text('body')
            check('side panel thread: the comment, then the agent\'s reply', body.find('Captcha solved') < body.find('Continuing the application') and 'Captcha solved' in body, body[:120])
            sp.screenshot(path=str(SHOTS / 'ext_side_panel_thread.png'))
            sp.close()
            txt = bar_text(page)
            check('bar after chrome-claim done + --message: no YOUR TURN, agent message shown, badge not "!"',
                  'YOUR TURN' not in txt and 'agent: Thanks, I see it' in txt and badge(tid) != '!', txt)
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
    finally:
        proc.terminate()
        proc.wait(30)
        srv.shutdown()
    print(f'{sum(results)}/{len(results)} checks passed')
    sys.exit(0 if all(results) else 1)


if __name__ == '__main__':
    main()
