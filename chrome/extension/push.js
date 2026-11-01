// Agent tab notes: make room for the bar at the top, so it never lies on the page.
// Loaded before note.js (same content-script world). Exposes self.agentPush = {on(h), off()}.
// What it does, all reverted by off():
//   1. html gets margin-top: h and position: relative, so the page flow and its absolutely
//      positioned parts move down by h;
//   2. a page that does not scroll (an "app" page: html/body 100% high, overflow hidden) gets
//      html height 100vh - h, so its bottom is not pushed out of sight;
//   3. every fixed or sticky element whose top edge sits in [0, h) gets top + h, and a fixed one
//      that reached the bottom of the window gets max-height 100vh - its new top (kept up to date
//      while the page changes, since single-page sites add headers and dialogs later).
(() => {
  let h = 0, timer = null, observer = null, htmlOrig = null;
  const shifted = new Map();   // element -> {orig: inline top value, origPrio, set: px we set}
  const HTML_PROPS = ["margin-top", "position", "height", "min-height"];

  // CSSOM (element.style) is never blocked by a page's CSP, unlike a <style> element.
  function setHtml(appPage) {
    const st = document.documentElement.style;
    if (!htmlOrig) htmlOrig = HTML_PROPS.map(k => [k, st.getPropertyValue(k), st.getPropertyPriority(k)]);
    st.setProperty("margin-top", `${h}px`, "important");
    st.setProperty("position", "relative", "important");
    if (appPage) { st.setProperty("height", `calc(100vh - ${h}px)`, "important"); st.setProperty("min-height", "0", "important"); }
  }

  function shiftAll() {
    timer = null;
    for (const [el, s] of shifted) if (!el.isConnected) shifted.delete(el);
    for (const el of document.querySelectorAll("body *, body")) {
      if (el.tagName === "AGENT-TAB-NOTE") continue;
      const cs = getComputedStyle(el);
      if (cs.position !== "fixed" && cs.position !== "sticky") continue;
      const done = shifted.get(el);
      if (done && el.style.getPropertyValue("top") === `${done.set}px`) continue;   // still ours
      if (cs.top === "auto") continue;                       // anchored to the bottom: leave it
      const top = parseFloat(cs.top);
      if (cs.position === "fixed" && el.getBoundingClientRect().top >= h) continue;
      if (top >= h) continue;
      const orig = done ? done.orig : el.style.getPropertyValue("top");
      const origPrio = done ? done.origPrio : el.style.getPropertyPriority("top");
      const origMax = done ? done.origMax : el.style.getPropertyValue("max-height");
      const reachedBottom = cs.position === "fixed" && el.getBoundingClientRect().bottom >= innerHeight - 1;
      shifted.set(el, { orig, origPrio, origMax, set: top + h });
      el.style.setProperty("top", `${top + h}px`, "important");
      // a full-height layer (dialog backdrop, app frame) would now stick out at the bottom: shorten it
      if (reachedBottom && el.getBoundingClientRect().bottom > innerHeight + 1)
        el.style.setProperty("max-height", `calc(100vh - ${top + h}px)`, "important");
    }
  }

  const later = () => { if (!timer) timer = setTimeout(shiftAll, 150); };

  self.agentPush = {
    on(height) {
      if (h === height) return;
      if (h) this.off();
      h = height;
      const scrolls = document.scrollingElement && document.scrollingElement.scrollHeight > innerHeight + 1;
      setHtml(!scrolls);
      shiftAll();
      observer = observer || new MutationObserver(later);
      observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class"] });
      addEventListener("resize", later);
    },
    off() {
      if (!h) return;
      h = 0;
      observer?.disconnect();
      removeEventListener("resize", later);
      const st = document.documentElement.style;
      for (const [k, v, prio] of htmlOrig || []) { if (v) st.setProperty(k, v, prio); else st.removeProperty(k); }
      htmlOrig = null;
      for (const [el, s] of shifted) {
        if (s.orig) el.style.setProperty("top", s.orig, s.origPrio); else el.style.removeProperty("top");
        if (s.origMax) el.style.setProperty("max-height", s.origMax); else el.style.removeProperty("max-height");
      }
      shifted.clear();
    },
  };
})();
