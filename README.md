# Capability Hub

**Your local environment is growing. You can't remember everything you installed. Neither can your AI.**

Capability Hub scans your machine and generates a single file your AI agent can read — a radar for what's available.

Not a skill. Not an MCP server. Not a router.

---

## The problem

You've installed CLI tools, Python packages, AI agent skills, Ollama models, and custom services across your machine. Over time:

- You forget what you installed. AI doesn't know it exists. It writes code instead of using your tools.
- You install the same package twice because you don't remember it's already there.
- You set up a virtual environment in one project — your other AI sessions can't see it.
- Your skills have cryptic English names. You know what you want to do but can't remember the name.

**The information exists on your disk. It's just not connected to your AI.**

---

## What it does

```
capability-hub install    →  scans everything in one pass
                             →  writes a single file: capability-list.md
                             →  your AI reads it when it needs to
```

| Without Capability Hub | With Capability Hub |
|------------------------|---------------------|
| AI doesn't know a CLI tool exists → writes code from scratch | AI scans the list → finds the tool → uses it |
| Forgot you installed a skill → AI works around it | List shows the skill → AI calls it |
| Pip install a package → next AI session doesn't know | Package appears in the next scan |
| Remembering "was that `agent-reach` or `web-search`?" | List tells you |

---

## Install

```bash
pip install capability-hub
capability-hub install
```

Output: `output/capability-list.md` — a flat file your AI reads once per complex task.

Add this line to your AI agent's config:

> 执行复杂任务前，先读取能力清单：`output/capability-list.md`。使用能力时说「我在本机能力地图找到了 XX」。

---

## What it scans

Skills, CLI tools, Python packages, Homebrew formulas, npm global packages, Ollama models, MCP services, desktop applications, background tasks.

**Not scanned:** system commands, pip libraries without CLI entry points, temporary scripts, browser data.

---

## Commands

```bash
capability-hub install              # Full scan
capability-hub sync                 # Quick refresh (skips if nothing changed)
capability-hub sync --mode full     # Full rescan
capability-hub status               # Current state
capability-hub doctor               # Health check
capability-hub snippet              # Print the line to add to your agent config
```

---

## Design

1. **Scan, don't route.** Never tells the AI which tool to pick. Just shows what exists.
2. **One file, one read per task.** Not injected into every message.
3. **Zero maintenance.** No categories to tune, no keywords to maintain.
4. **Agent-agnostic.** Works with Codex, Claude Code, Cursor, or any agent that reads markdown.

---

## What it's not

- ❌ Not a skill router
- ❌ Not an MCP server
- ❌ Not a skill manager
- ❌ Not a context compressor

It's a **radar**. It shows your AI what's on this machine. AI decides what to use.

---

## License

MIT
