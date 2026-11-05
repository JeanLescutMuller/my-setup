// Agent tab notes: formats a local Markdown file (file:///….md), which Chrome shows as raw text in one <pre>, so a
// click on a .md path in iTerm2 (agent-chrome show --clicked) reads like a page, in the project's profile, instead of
// opening VS Code (user, 6 Nov 2026). Needs "Allow access to file URLs" on the extension (chrome://extensions,
// Details), once per profile; without it Chrome shows the raw text. The text is read once: after an edit, reload.
// marked.js (v15.0.12, MIT, vendored unchanged from cdn.jsdelivr.net/npm/marked@15.0.12/lib/marked.umd.js) does the
// formatting. Raw HTML in the file is shown as text and javascript: links are dropped: an agent's .md may hold text
// copied from the web, and nothing in it runs.
(() => {
  const pre = document.body && document.body.childElementCount === 1 && document.body.firstElementChild.tagName === "PRE"
    ? document.body.firstElementChild : null;
  if (!pre || typeof marked === "undefined") return;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  marked.use({ gfm: true, renderer: { html: ({ text }) => esc(text) } });
  const article = document.createElement("article");
  article.innerHTML = marked.parse(pre.textContent);
  for (const a of article.querySelectorAll("a[href]"))
    if (/^\s*javascript:/i.test(a.getAttribute("href"))) a.removeAttribute("href");
  const style = document.createElement("style");
  style.textContent = `
    :root { color-scheme: light dark; --fg: #1f2328; --bg: #fff; --dim: #59636e; --line: #d1d9e0; --code: #f6f8fa; --link: #0969da; }
    @media (prefers-color-scheme: dark) { :root { --fg: #e6edf3; --bg: #0d1117; --dim: #9198a1; --line: #3d444d; --code: #151b23; --link: #4493f8; } }
    html, body { background: var(--bg); color: var(--fg); margin: 0; }
    article { max-width: 900px; margin: 0 auto; padding: 32px 16px 64px; font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    h1, h2 { border-bottom: 1px solid var(--line); padding-bottom: .3em; }
    h1, h2, h3, h4 { line-height: 1.25; margin: 1.5em 0 .6em; }
    a { color: var(--link); }
    code, pre { font: 13.5px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--code); border-radius: 6px; }
    code { padding: .15em .35em; }
    pre { padding: 12px 16px; overflow-x: auto; }
    pre code { padding: 0; background: none; }
    blockquote { margin: 0; padding: 0 1em; color: var(--dim); border-left: 4px solid var(--line); }
    table { border-collapse: collapse; display: block; overflow-x: auto; }
    th, td { border: 1px solid var(--line); padding: 6px 12px; }
    th { background: var(--code); }
    img { max-width: 100%; }
    hr { border: 0; border-top: 1px solid var(--line); }`;
  document.head.append(style);
  pre.replaceWith(article);
  const h1 = article.querySelector("h1");
  document.title = (h1 ? h1.textContent.trim() + " · " : "") + decodeURIComponent(location.pathname.split("/").pop());
})();
