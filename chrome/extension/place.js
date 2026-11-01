// Agent tab notes: one agent window per project (the Chrome kit's question 4c), per profile.
// The first window that holds a tab of project P (or the window `agent-chrome open-profile-window` opened for P: its first tab is
// window.html?project=P) becomes P's window; a later session's tab group of P that Claude in Chrome put in another
// window (it uses the profile's last-focused window) is moved there with chrome.tabGroups.move, in the background.
// Only agent tabs (in the kit's open.json, sent by the native host as notes) are ever moved, never the user's; a
// window another project already owns is never taken: P then gets its own new window (unfocused). The window a group
// left is closed only when that group's arrival created it (unfocused, under 30 s before) and nothing else is in it.
// Kept: chrome.storage.local {map: {project: windowId}, profile} (window ids live as long as Chrome runs: cleared at
// startup); chrome.storage.session {placed: {tabId: 1}, created: {windowId: ms}, placeLog: [last 30 decisions]}.
// decide() and leftEmpty() are pure: tests/test_place.js runs them in Node.

const BLANK = ["", "about:blank", "chrome://newtab/", "chrome://new-tab-page/"];
const NEW_WINDOW_MS = 30000;

// Where should this agent tab go?  -> {action: skip|adopt|stay|new_window|wait|move, ...}
function decide({ tab, project, map, normal, groupTabIds, notes }) {
  if (!project) return { action: "skip", why: "no project" };
  const target = map[project];
  if (target == null || !normal.includes(target)) {
    const owner = Object.keys(map).find(p => p !== project && map[p] === tab.windowId && normal.includes(map[p]));
    return owner ? { action: "new_window", why: `window ${tab.windowId} is ${owner}'s` }
                 : { action: "adopt", windowId: tab.windowId };
  }
  if (target === tab.windowId) return { action: "stay" };
  const ids = tab.groupId === -1 || tab.groupId == null ? [tab.id] : groupTabIds;
  const unknown = ids.filter(i => !notes[String(i)]);
  if (unknown.length) return { action: "wait", why: `tab(s) ${unknown.join(",")} of the group are not an agent's (yet)` };
  if (ids.some(i => notes[String(i)].project !== project)) return { action: "skip", why: "the group mixes projects" };
  return { action: "move", windowId: target, groupId: tab.groupId == null ? -1 : tab.groupId, tabIds: ids };
}

// After a move: close the window the group left?
function leftEmpty({ created, now, remaining }) {
  return created != null && now - created <= NEW_WINDOW_MS && remaining.every(t => BLANK.includes(t.url || t.pendingUrl || ""));
}

if (typeof module !== "undefined") module.exports = { decide, leftEmpty, BLANK, NEW_WINDOW_MS };

if (typeof chrome !== "undefined" && chrome.windows) {
  var Place = (() => {
    let queue = Promise.resolve();
    const run = fn => (queue = queue.then(fn).catch(e => log({ error: String(e) })));
    const local = async () => ({ map: {}, profile: null, ...(await chrome.storage.local.get(["map", "profile"])) });
    const sess = async () => ({ placed: {}, created: {}, placeLog: [], ...(await chrome.storage.session.get(["placed", "created", "placeLog"])) });
    const normalIds = async () => (await chrome.windows.getAll({ windowTypes: ["normal"] })).map(w => w.id);
    const marker = (project, profile) => chrome.runtime.getURL(`window.html?${new URLSearchParams({ project, profile: profile || "" })}`);
    let report = () => {};           // set by background.js: sends the windows to the native host

    async function log(entry) {
      const s = await sess();
      s.placeLog.push({ t: Date.now(), ...entry });
      await chrome.storage.session.set({ placeLog: s.placeLog.slice(-30) });
    }

    async function placeOne(id, notes) {
      const note = notes[id];
      const tab = await chrome.tabs.get(Number(id)).catch(() => null);
      if (!tab) return;                                   // not in this profile, or gone
      let { map, profile } = await local();
      if (!profile && note.profile) { profile = note.profile; await chrome.storage.local.set({ profile }); }
      const s = await sess();
      if (s.placed[id]) return;                           // placed once: the user may move it after, we never do
      const groupTabIds = tab.groupId > -1 ? (await chrome.tabs.query({ groupId: tab.groupId })).map(t => t.id) : [tab.id];
      let d = decide({ tab, project: note.project, map, normal: await normalIds(), groupTabIds, notes });
      if (d.action === "new_window") {
        const w = await chrome.windows.create({ focused: false, url: marker(note.project, profile) });
        map = { ...map, [note.project]: w.id };
        await chrome.storage.local.set({ map });
        await log({ tab: tab.id, project: note.project, action: "new_window", windowId: w.id, why: d.why });
        d = decide({ tab, project: note.project, map, normal: await normalIds(), groupTabIds, notes });
      }
      if (d.action === "adopt") { map = { ...map, [note.project]: d.windowId }; await chrome.storage.local.set({ map }); }
      if (d.action === "move") {
        const src = tab.windowId;
        if (d.groupId > -1) await chrome.tabGroups.move(d.groupId, { windowId: d.windowId, index: -1 });
        else await chrome.tabs.move(tab.id, { windowId: d.windowId, index: -1 });
        const remaining = await chrome.tabs.query({ windowId: src }).catch(() => []);
        if (remaining.length && leftEmpty({ created: s.created[src], now: Date.now(), remaining })) {
          await chrome.windows.remove(src).catch(() => {});
          d.closed = src;
        }
      }
      if (["adopt", "stay", "move", "skip"].includes(d.action)) {
        const s2 = await sess();
        for (const t of d.tabIds || groupTabIds) s2.placed[String(t)] = 1;
        await chrome.storage.session.set({ placed: s2.placed });
      }
      if (d.action !== "stay") await log({ tab: tab.id, project: note.project, from: tab.windowId, ...d });
    }

    return {
      setReport(fn) { report = fn; },
      local, normalIds,
      place: notes => run(async () => { for (const id of Object.keys(notes)) await placeOne(id, notes); await report(); }),
      // window.html, the first tab of a window `agent-chrome open-profile-window` (or decide's new_window) opened for a project
      marker: (project, profile, tab) => run(async () => {
        let { map } = await local();
        if (profile) await chrome.storage.local.set({ profile });
        if (project && !(map[project] != null && (await normalIds()).includes(map[project]))) {
          map = { ...map, [project]: tab.windowId };
          await chrome.storage.local.set({ map });
          await log({ tab: tab.id, project, action: "marker", windowId: tab.windowId });
        }
        if (!tab.pinned) await chrome.tabs.update(tab.id, { pinned: true }).catch(() => {});
        await report();
        return { mine: map[project] === tab.windowId, windowId: map[project] };
      }),
      created: w => run(async () => {
        if (!w.focused) { const s = await sess(); s.created[w.id] = Date.now(); await chrome.storage.session.set({ created: s.created }); }
        await report();
      }),
      removed: wid => run(async () => {
        const { map } = await local();
        const left = Object.fromEntries(Object.entries(map).filter(([, w]) => w !== wid));
        await chrome.storage.local.set({ map: left });
        await report();
      }),
      startup: () => run(() => chrome.storage.local.set({ map: {} })),   // new Chrome: old window ids mean nothing
    };
  })();
}
