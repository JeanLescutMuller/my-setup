// Side panel (opened by the toolbar icon or the bar's "details · reply"): the tab's note, the thread of messages
// with the agent, and a comment box. A comment goes to the background, then native_host.py, which appends it to
// comments.jsonl (hook.py gives it to the session) and sends it back in note.thread with the agent's replies
// (agent-chrome reply-to-human).
const tabId = Number(new URLSearchParams(location.search).get("tabId"));
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const hhmm = ts => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const ROWS = [["opened_dt", "opened (UTC)"], ["session_id", "session"], ["project", "project"], ["job", "scheduled job"],
              ["purpose", "why"], ["visibility", "visibility"], ["visibility_reason", "why that visibility"],
              ["needs_human", "needs human"], ["reply_to", "reach it"], ["dt", "last event (UTC)"],
              ["event", "last event"], ["machine", "machine"], ["cwd", "folder"], ["profile", "Chrome profile"], ["url", "url"]];
let shown = "";
async function draw() {
  const { note } = await chrome.runtime.sendMessage({ type: "get", tabId });
  const key = JSON.stringify(note);
  if (!note || key === shown) return;
  shown = key;
  document.getElementById("action").innerHTML = note.needs_human ? `<div class="action">⚠ NEEDS HUMAN: ${esc(note.needs_human)}</div>` : "";
  const thread = note.thread || [];
  if (thread.length) document.getElementById("thread").innerHTML = thread.map(m =>
    `<div class="msg ${m.from}"><small>${m.from === "you" ? "you" : "agent"} · ${hhmm(m.ts)}</small>${esc(m.text)}</div>`).join("");
  document.getElementById("out").innerHTML =
    `<table>${ROWS.filter(([k]) => note[k]).map(([k, label]) => `<tr><td>${label}</td><td>${esc(note[k])}</td></tr>`).join("")}</table>`;
}
document.getElementById("send").onsubmit = async e => {
  e.preventDefault();
  const box = document.getElementById("text"), text = box.value.trim();
  if (!text) return;
  const r = await chrome.runtime.sendMessage({ type: "comment", tabId, text });
  document.getElementById("status").textContent = r.ok ? "Sent." : `Not sent: ${r.error}`;
  if (r.ok) box.value = "";
};
document.getElementById("text").onkeydown = e => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) document.getElementById("send").requestSubmit(); };
draw(); setInterval(draw, 1000);
