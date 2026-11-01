// Agent tab notes: the bar at the top of an agent's tab. Runs in the extension's isolated world on every page load,
// so it comes back after each navigation and reload. It never lies on the page: push.js moves the page (and its
// fixed or sticky headers) down by the bar's height, measured, since a narrow window wraps it onto two lines.
// Drawn in a closed shadow root with a constructed stylesheet and no web_accessible_resources: the page's CSP and
// CSS do not apply to it, and the page cannot probe for it by URL.
// Fields, in the user's order: opened (date, time), session UUID, subagent (if one opened it), project, job (only when a job opened it),
// purpose, visibility, then NEEDS HUMAN (with the time the tab closes if nobody acts); then the agent's last message.
(() => {
  let host = null, root = null, current = null, hidden = false, sizer = null;

  const CSS = `
    :host { all: initial; }
    .bar { position: fixed; z-index: 2147483647; top: 0; left: 0; right: 0; box-sizing: border-box; min-height: 28px;
           display: flex; flex-wrap: wrap; align-items: center; gap: 2px 10px; padding: 5px 10px;
           font: 13px/18px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #fff; background: #3c4043; }
    .bar.action { background: #b3261e; }
    .bar.done { background: #188038; }
    .f { white-space: nowrap; }
    .f b { font-weight: 600; }
    .dim { opacity: .8; font-size: 12px; }
    .turn { font-weight: 700; background: #ffd54f; color: #3c1e00; padding: 0 6px; border-radius: 3px; white-space: normal; }
    .msg { white-space: normal; }
    .sp { flex: 1 1 0; }
    button { all: unset; cursor: pointer; padding: 1px 8px; border: 1px solid rgba(255,255,255,.7); border-radius: 4px; font-size: 12px; white-space: nowrap; }
  `;

  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const hhmm = ts => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const opened = ts => ts ? new Date(ts * 1000).toLocaleString([], { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "?";

  function remove() { sizer?.disconnect(); sizer = null; host?.remove(); host = null; self.agentPush.off(); }

  function render(note) {
    current = note;
    if (!note || hidden) return remove();
    if (!host || !host.isConnected) {
      host = document.createElement("agent-tab-note");
      root = host.attachShadow({ mode: "closed" });
      const sheet = new CSSStyleSheet(); sheet.replaceSync(CSS); root.adoptedStyleSheets = [sheet];
      document.documentElement.appendChild(host);
    }
    const cls = note.needs_human ? "action" : note.event === "done" ? "done" : "info";
    const parts = [
      `<span class="f"><span class="dim">opened</span> <b>${esc(opened(note.opened_ts))}</b></span>`,
      `<span class="f"><span class="dim">session</span> ${esc(note.session_id || "?")}</span>`,
      note.agent_id ? `<span class="f"><span class="dim">subagent</span> ${esc(note.agent_id)}</span>` : "",
      `<span class="f"><span class="dim">project</span> <b>${esc(note.project || "?")}</b></span>`,
      note.job ? `<span class="f"><span class="dim">job</span> <b>${esc(note.job)}</b></span>` : "",
      `<span class="f">${esc(note.purpose || "(no purpose given)")}</span>`,
      note.visibility ? `<span class="f"><span class="dim">visibility</span> ${esc(note.visibility)}</span>` : "",
      note.needs_human ? `<span class="turn">⚠ NEEDS HUMAN: ${esc(note.needs_human)}${note.expires_ts ? ` <span class="dim">(closes at ${esc(hhmm(note.expires_ts))} if nobody acts)</span>` : ""}</span>`
        : cls === "done" ? `<span class="f"><b>✓ nothing to do: you may close this tab</b></span>`
        : `<span class="f"><b>nothing to do</b></span>`,
      note.message ? `<span class="msg">💬 agent: ${esc(note.message)}</span>` : "",
    ];
    root.innerHTML = `<div class="bar ${cls}">${parts.join("")}<span class="sp"></span>
      <button class="open">details · reply</button><button class="hide">hide</button></div>`;
    root.querySelector(".open").onclick = () => chrome.runtime.sendMessage({ type: "openPanel" });
    root.querySelector(".hide").onclick = () => { hidden = true; remove(); };
    const bar = root.querySelector(".bar");
    self.agentPush.on(bar.offsetHeight);
    sizer?.disconnect();
    sizer = new ResizeObserver(() => { if (host?.isConnected) self.agentPush.on(bar.offsetHeight); });
    sizer.observe(bar);
  }

  chrome.runtime.onMessage.addListener(m => {
    if (m.type !== "note") return;
    if (m.note?.needs_human && m.note.needs_human !== current?.needs_human) hidden = false;   // a new request shows again
    render(m.note);
  });
  chrome.runtime.sendMessage({ type: "hello" }).then(r => render(r?.note || null)).catch(() => {});
  // Single-page sites (LinkedIn, Facebook) may rebuild the document: put the bar back if removed.
  new MutationObserver(() => { if (current && !hidden && host && !host.isConnected) render(current); })
    .observe(document.documentElement, { childList: true });
})();
