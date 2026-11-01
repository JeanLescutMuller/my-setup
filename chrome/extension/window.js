// window.html: the first tab (pinned) of a project's agent window, opened by `chrome-claim window` or by place.js.
// Tells the background which project this window is for; its title names the project in Mission Control.
const q = new URLSearchParams(location.search);
const project = q.get("project") || "", profile = q.get("profile") || "";
document.title = `${project || "?"} · agent window`;
document.getElementById("title").textContent = `${project || "?"} · agent window`;
document.getElementById("profile").textContent = profile ? `Chrome profile: ${profile}` : "";
chrome.runtime.sendMessage({ type: "marker", project, profile }).then(r => {
  document.getElementById("status").textContent = r && r.mine ? "This is the project's agent window."
    : r ? `This project's agent window is another one (window ${r.windowId}).` : "";
}, () => {});
