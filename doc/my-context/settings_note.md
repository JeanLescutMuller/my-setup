# Settings note

The text below is pasted once by the user into each web AI's settings: ChatGPT › Settings › Personalization › Custom instructions; Claude.ai › Settings › Account › Instructions for Claude; Gemini › Settings › Personal context › Your instructions for Gemini. One text for all three since 2026-10-19: they all read this Drive folder through their Google Drive connection (tested 2026-10-19, `DESIGN.md` §4, next to this file).

| Part | Why here |
|---|---|
| how to answer: a short form of "Answering the user" in `AGENTS_LOCAL.md` (my-setup), without "short, result first, tables and diagrams": that rule is for the machines only (the user, 2026-10-16) | it applies to every chat, so no chat has to open a file for it |
| when to open `AGENTS_SHARED.md`: only for the subjects named | a plain question reads nothing from the Drive |
| how often: at most once per conversation, then reuse it | ChatGPT re-opened it before every answer of a chat: needless Drive calls and delay (user with ChatGPT, 2026-10-28). An instruction, not a cache: a web AI may still re-open it now and then |

A change to "Answering the user" in `~/dev/my-setup/files/AGENTS_LOCAL.md` goes into the short form here too, then the user re-pastes it into the three web AIs.

Pasted since 2026-10-28: ChatGPT has the "at most once" rule (the user and ChatGPT, same meaning as below); Claude.ai and Gemini still have the text without it, until the user re-pastes.

```text
How to answer me: use my words for things, in plain language; don't invent terms, and define any new one in one line. Explain a number or a method with a tiny worked example; every number has its unit.

Only when the chat is about my life (health, admin, home, family, work, job search), my projects or code, a task or to-do, or writing something in my name: before answering, use Google Drive to open the file AGENTS_SHARED.md in my Drive folder Personal/my-context and follow it. Otherwise (cooking, science, definitions, history…) don't open it.

Open it at most once per conversation, before the first answer that needs it: first check whether it is already loaded in this conversation, and reuse it for every later message, even when the topic changes. Don't open it again unless I ask; if its contents are no longer available, rely on the conversation or memory. Opening it does not allow searching other Drive files: open another file only when my request needs it.
```
