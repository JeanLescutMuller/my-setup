#!/usr/bin/env python3
"""What every Claude / Codex session loads at startup vs only on use, in tokens and in % of each context window.

Run by hand:  python3 ~/dev/my-setup/tools/context_inventory.py [--descriptions]
Measures files only (instructions, memory, skills). MCP servers and Claude Code's built-in skills are not files here:
they are listed at the end as a reminder, measure them from a session's own context if needed.
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

HOME = Path.home()
CHARS_PER_TOKEN = 4  # rough: ~4 characters per token for English/Markdown
SKILL_FRAMING = 20   # chars the harness adds around each skill line ("- name: ")
# Claude's window, measured 2026-10-11 from a statusline payload (.context_window.context_window_size, claude-opus-5-5)
CLAUDE_WINDOW = int(os.environ.get("CLAUDE_WINDOW", 1_000_000))


def codex_window() -> int:
    # Codex writes its window into every session file; take the newest one
    l_files = sorted(glob.glob(str(HOME / ".codex/sessions/**/*.jsonl"), recursive=True), key=os.path.getmtime)
    for f in reversed(l_files[-5:]):
        l_hits = re.findall(r'"model_context_window":(\d+)', Path(f).read_text(errors="ignore"))
        if l_hits:
            return int(l_hits[-1])
    return 258_400  # last measured value (gpt-6-astra, 2026-10-11)


CODEX_WINDOW = codex_window()


def tokens(chars: int) -> int:
    return round(chars / CHARS_PER_TOKEN)


def cell(tok: int | None, claude: bool, codex: bool) -> str:
    # "tokens · Claude% · Codex%", a dash where that agent does not load it
    if not tok:
        return "—"
    pc = f"{100 * tok / CLAUDE_WINDOW:.2f}%" if claude else "—"
    px = f"{100 * tok / CODEX_WINDOW:.2f}%" if codex else "—"
    return f"{tok:,} · {pc} · {px}"


def skill_description(path: Path) -> str:
    # Front matter "description:", single line, quoted, or folded (>, |) over several indented lines
    text = path.read_text(errors="ignore")
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return ""
    l_lines, desc, inside = m.group(1).splitlines(), [], False
    for line in l_lines:
        if line.startswith("description:"):
            inside = True
            first = line[len("description:"):].strip().lstrip(">|-").strip()
            if first:
                desc.append(first)
        elif inside and (line.startswith(" ") or line.startswith("\t")):
            desc.append(line.strip())
        elif inside:
            break
    return " ".join(desc).strip("\"'")


def skill_dirs() -> dict:
    # skill name -> (SKILL.md path, loaded by Claude, loaded by Codex)
    d_skills = {}
    def add(pattern, prefix, claude, codex):
        for f in sorted(glob.glob(str(pattern))):
            name = prefix + Path(f).parent.name
            _, c0, x0 = d_skills.get(name, (None, False, False))
            d_skills[name] = (Path(f), c0 or claude, x0 or codex)
    add(HOME / ".claude/skills/*/SKILL.md", "", True, False)
    add(HOME / ".agents/skills/*/SKILL.md", "", False, True)
    add(HOME / ".codex/skills/*/SKILL.md", "", False, True)
    add(HOME / ".claude/skills/synced/*/*/SKILL.md", "anthropic-skills:", True, False)
    # enabled plugins' skills (Claude only)
    d_settings = json.loads((HOME / ".claude/settings.json").read_text())
    d_installed = json.loads((HOME / ".claude/plugins/installed_plugins.json").read_text()).get("plugins", {})
    for plugin, on in (d_settings.get("enabledPlugins") or {}).items():
        if on and plugin in d_installed:
            root = d_installed[plugin][0]["installPath"]
            add(Path(root) / "skills/*/SKILL.md", plugin.split("@")[0] + ":", True, False)
    d_skills.pop("synced", None)
    return d_skills


l_rows = []  # (item, init tokens, on-use tokens, claude, codex, description)
SHOW_DESC = "--descriptions" in sys.argv

# Instructions: ~/.claude/CLAUDE.md for Claude, ~/.codex/AGENTS.md for Codex (both symlinks to ~/opt/my-setup/context/AGENTS.md: files/AGENTS_LOCAL.md + the Drive's AGENTS_SHARED.md)
claude_md, codex_md = HOME / ".claude/CLAUDE.md", HOME / ".codex/AGENTS.md"
same = claude_md.exists() and codex_md.exists() and claude_md.resolve() == codex_md.resolve()
if same:
    l_rows.append((f"instructions {claude_md.resolve()}", tokens(len(claude_md.read_text())), None, True, True, ""))
else:
    for f, c, x in [(claude_md, True, False), (codex_md, False, True)]:
        if f.exists():
            l_rows.append((f"instructions {f}", tokens(len(f.read_text())), None, c, x, ""))
mem = HOME / ".claude/projects/-Users-jeanlescut/memory/MEMORY.md"
if mem.exists():
    l_rows.append(("MEMORY.md (sessions started in ~)", tokens(len(mem.read_text())), None, True, False, ""))

# skillOverrides (Claude only): "off" / "user-invocable-only" = not listed, "name-only" = no description
d_over = json.loads((HOME / ".claude/settings.json").read_text()).get("skillOverrides") or {}
for name, (f, c, x) in sorted(skill_dirs().items()):
    mode = d_over.get(name) or d_over.get(name.split(":")[-1]) or "on"
    if mode in ("off", "user-invocable-only") and not x:
        l_rows.append((f"skill {name} (hidden: {mode})", 0, tokens(len(f.read_text(errors="ignore"))), c, x, skill_description(f)))
        continue
    init = tokens(len(name) + (0 if mode == "name-only" else len(skill_description(f))) + SKILL_FRAMING)
    l_rows.append((f"skill {name}", init, tokens(len(f.read_text(errors="ignore"))), c, x, skill_description(f)))

print(f"Windows: Claude {CLAUDE_WINDOW:,} · Codex {CODEX_WINDOW:,}   cells = tokens · Claude % · Codex %\n")
print("| Item | At init (every session) | On use |" + (" Description |" if SHOW_DESC else ""))
print("|---|---|---|" + ("---|" if SHOW_DESC else ""))
for item, init, use, c, x, desc in l_rows:
    print(f"| {item} | {cell(init, c, x)} | {cell(use, c, x)} |" + (f" {desc.replace('|', '/')} |" if SHOW_DESC else ""))
tot_c = sum(r[1] for r in l_rows if r[3])
tot_x = sum(r[1] for r in l_rows if r[4])
print(f"| **Total at init (files)** | Claude {tot_c:,} · {100 * tot_c / CLAUDE_WINDOW:.2f}% · Codex {tot_x:,} · {100 * tot_x / CODEX_WINDOW:.2f}% | |")
print("\nNot measured here (Claude only): Claude Code built-in skills, MCP servers (tool names + instructions; `/mcp`), Chrome (`/chrome`).")
