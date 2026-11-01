// Unit tests of extension/place.js's pure decisions (one agent window per project). Run: node tests/test_place.js
const { decide, leftEmpty } = require("../extension/place.js");
let fail = 0;
const check = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  fail += !ok;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${ok ? "" : `  got ${JSON.stringify(got)} want ${JSON.stringify(want)}`}`);
};
const notes = { 11: { project: "A" }, 12: { project: "A" }, 21: { project: "B" } };
const tab = (id, windowId, groupId = 7) => ({ id, windowId, groupId });
const a = (o) => decide({ notes, groupTabIds: [11], normal: [1, 2, 3], map: {}, project: "A", ...o }).action;

check("no project: skip", a({ project: "" }), "skip");
check("first tab of A: its window becomes A's", decide({ tab: tab(11, 2), project: "A", map: {}, normal: [1, 2], groupTabIds: [11], notes }),
      { action: "adopt", windowId: 2 });
check("A's window is gone: adopt the new one", a({ tab: tab(11, 2), map: { A: 9 } }), "adopt");
check("already in A's window: stay", a({ tab: tab(11, 1), map: { A: 1 } }), "stay");
check("in another window: move the group to A's", decide({ tab: tab(11, 2), project: "A", map: { A: 1 }, normal: [1, 2], groupTabIds: [11, 12], notes }),
      { action: "move", windowId: 1, groupId: 7, tabIds: [11, 12] });
check("an ungrouped agent tab: move the tab", decide({ tab: tab(11, 2, -1), project: "A", map: { A: 1 }, normal: [1, 2], groupTabIds: [11], notes }),
      { action: "move", windowId: 1, groupId: -1, tabIds: [11] });
check("the group holds a tab not in open.json (the user's): wait, never move", a({ tab: tab(11, 2), map: { A: 1 }, groupTabIds: [11, 99] }), "wait");
check("the group mixes projects: skip", a({ tab: tab(11, 2), map: { A: 1 }, groupTabIds: [11, 21] }), "skip");
check("landed in B's window and A has none: a new window for A", a({ tab: tab(11, 2), map: { B: 2 } }), "new_window");
check("B's window is gone: A may take it", a({ tab: tab(11, 2), map: { B: 2 }, normal: [1, 3] }), "adopt");

const now = 100000;
check("left window: created by the arrival, only a new tab -> close", leftEmpty({ created: now - 2000, now, remaining: [{ url: "chrome://newtab/" }] }), true);
check("left window: not created by an arrival -> keep", leftEmpty({ created: undefined, now, remaining: [{ url: "chrome://newtab/" }] }), false);
check("left window: created long ago -> keep", leftEmpty({ created: now - 60000, now, remaining: [] }), false);
check("left window: holds a real page -> keep", leftEmpty({ created: now - 2000, now, remaining: [{ url: "https://example.com/" }] }), false);
console.log(fail ? `${fail} FAILED` : "all passed");
process.exit(fail ? 1 : 0);
