// Agent tab notes: background service worker.
// Gets the Chrome kit's record of agent tabs from the native host (chrome/native_host.py) and shows each tab's note:
// the toolbar badge, the bar at the top of the page (note.js; push.js moves the page down so nothing is covered),
// and the side panel (details, the thread with the agent, a comment box). Comments go back to the host, which
// appends them to comments.jsonl for the session. Each project's agent tab groups go to that project's window
// (place.js: moved with chrome.tabGroups.move, never the user's tabs); the profile's windows are reported to the host
// (windows/<profile>.json: chrome-claim window opens a window only for a profile without one).
importScripts("place.js");
const HOST = "com.jeanlescut.agent_tab_notes";
// Sites with strong bot checks: the bar only when the human must act there (the badge always).
const QUIET_HOSTS = ["linkedin.com", "facebook.com", "messenger.com", "instagram.com"];

let notes = {};          // tab_id (string) -> note: an open.json entry + thread
let port = null;

function quiet(url) {
  try { const h = new URL(url).hostname; return QUIET_HOSTS.some(q => h === q || h.endsWith("." + q)); }
  catch { return false; }
}

function forPage(note, url) { return note && (!quiet(url) || note.needs_human) ? note : null; }

async function show(tabId) {
  const note = notes[String(tabId)] || null;
  const action = note && note.needs_human;
  const [text, color] = !note ? ["", "#5f6368"] : action ? ["!", "#d93025"] : note.event === "done" ? ["✓", "#188038"] : ["AI", "#5f6368"];
  await chrome.action.setBadgeText({ tabId, text }).catch(() => {});
  await chrome.action.setBadgeBackgroundColor({ tabId, color }).catch(() => {});
  await chrome.action.setTitle({ tabId, title: note ? `${action ? "YOUR TURN: " + note.needs_human + "\n" : ""}${note.project || ""} · ${note.purpose || ""}` : "Agent tab notes" }).catch(() => {});
  await chrome.sidePanel.setOptions({ tabId, path: `sidepanel.html?tabId=${tabId}`, enabled: true }).catch(() => {});
  let tab; try { tab = await chrome.tabs.get(tabId); } catch { return; }
  chrome.tabs.sendMessage(tabId, { type: "note", note: forPage(note, tab.url) }).catch(() => {});  // chrome:// pages: badge only
}

async function apply(newNotes) {
  const old = notes; notes = newNotes;
  await chrome.storage.session.set({ notes });
  for (const id of new Set([...Object.keys(old), ...Object.keys(newNotes)]))
    if (JSON.stringify(old[id]) !== JSON.stringify(newNotes[id])) await show(Number(id));
  Place.place(notes);
}

async function report() {   // this profile's windows -> the host -> windows/<profile>.json
  const { map, profile } = await Place.local();
  if (port && profile) port.postMessage({ windows: { profile, windows: await Place.normalIds(), projects: map } });
}
Place.setReport(report);

function connect() {
  if (port) return;
  try { port = chrome.runtime.connectNative(HOST); } catch (e) { console.warn("native host", e); return; }
  port.onMessage.addListener(m => { if (m.notes) apply(m.notes); });
  port.onDisconnect.addListener(() => { console.warn("native host gone", chrome.runtime.lastError?.message); port = null; setTimeout(connect, 5000); });
  port.postMessage({ hello: 1 });   // the host then sends {notes} at once and after every change of the record
  report();
}

chrome.runtime.onMessage.addListener((m, sender, reply) => {
  if (m.type === "hello" && sender.tab) {        // note.js, on each page load
    reply({ note: forPage(notes[String(sender.tab.id)] || null, sender.tab.url) });
  } else if (m.type === "get") {                 // the side panel
    reply({ note: notes[String(m.tabId)] || null, connected: !!port });
  } else if (m.type === "openPanel" && sender.tab) {   // the bar's "details · reply" (a click: allowed to open it)
    chrome.sidePanel.open({ tabId: sender.tab.id }).then(() => "opened", e => String(e))
      .then(r => { chrome.storage.session.set({ lastOpen: r }); reply({ result: r }); });
    return true;
  } else if (m.type === "marker" && sender.tab) {   // window.html: this window is the project's agent window
    Place.marker(m.project, m.profile, sender.tab).then(reply);
    return true;
  } else if (m.type === "comment") {             // the side panel: the user's message to the agent
    chrome.tabs.get(m.tabId).then(tab => {
      if (!port) return reply({ ok: false, error: "native host not connected" });
      port.postMessage({ comment: { tab_id: m.tabId, url: tab.url, text: m.text } });
      reply({ ok: true });
    }, e => reply({ ok: false, error: String(e) }));
    return true;
  }
});
chrome.tabs.onUpdated.addListener((tabId, info) => { if (info.status === "complete" && notes[String(tabId)]) show(tabId); });
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});   // click the icon = the panel
chrome.windows.onCreated.addListener(w => Place.created(w), { windowTypes: ["normal"] });
chrome.windows.onRemoved.addListener(wid => Place.removed(wid), { windowTypes: ["normal"] });
chrome.runtime.onStartup.addListener(() => { Place.startup(); connect(); });
chrome.runtime.onInstalled.addListener(connect);
chrome.storage.session.get("notes").then(r => { notes = r.notes || {}; connect(); });
