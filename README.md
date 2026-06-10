# Capability Hub

**Agent capability awareness middleware.**  
Scan your machine → generate a capability list → your AI agent reads it.

Not a skill. Not an MCP tool. Not a router.  
Just a radar: what tools, models, skills, and services exist on this machine.

---

## Why

You installed tools, models, and skills on your machine. **Your AI agent doesn't know they exist.**

Without Capability Hub:
- You manually update a list in `AGENTS.md` (and forget to update it)
- Your AI writes 30 lines of code to do something a CLI tool could do in one command
- You repeat "I have X installed" to every new AI session

With Capability Hub:

```
Before:  AI: "Let me write a script to remove the background from this image..."
After:   AI reads capability list → "Found a background removal tool, using it."

Before:  AI: "I'll use a Python library to transcribe this audio..."
After:   AI reads capability list → "Found a local speech-to-text tool, using it."

Before:  AI: "Let me download this video with a generic HTTP library..."
After:   AI reads capability list → "Found a video downloader, using it."
```

---

## How it works

```
capability-hub install
  └─ Scans: skills, pip, brew, npm, ollama, apps, services
  └─ Generates: output/capability-list.md (~150 items, ~12KB)
  └─ Your AI reads it once per complex task
```

Add this line to your AI agent's config (`~/.codex/AGENTS.md`, `~/.claude/CLAUDE.md`, `.cursorrules`, or system prompt):

```
执行复杂任务前，先读取本机能力清单：`~/path/to/output/capability-list.md`。使用能力时说「我在本机能力地图找到了 XX」。
```

---

## What it scans

| Source | Examples |
|--------|---------|
| AI agent skills | frontend-design, pdf, code-review, browser-automation, video-downloader |
| pip packages (CLI tools) | background removal, text-to-speech, video download, OCR |
| Homebrew | ffmpeg, ripgrep, imagemagick, pngquant |
| npm global packages | dev tools, automation scripts |
| Ollama models | Any locally downloaded LLM |
| Desktop apps | Photoshop, DaVinci Resolve, VS Code |
| MCP services | headroom, custom endpoints |
| LaunchAgents | background tasks |

**Not scanned:** system commands (ls, cd), pip libraries without CLI, system apps (Safari, Mail), temporary scripts.

---

## Install

```bash
pip install capability-hub
capability-hub install
```

Or from source:

```bash
git clone https://github.com/sedifr/capability-hub
cd capability-hub
pip install .
capability-hub install
```

Output files (in `output/`):
- `capability-list.md` — AI reads this (12KB)
- `agent-bootstrap.md` — Entry instructions for AI
- `machine-capability-report.md` — Human-readable scan report

---

## Commands

```bash
capability-hub install              # Full scan + generate map
capability-hub sync                 # Quick refresh (skips if no changes)
capability-hub sync --mode full     # Full baseline rescan
capability-hub status               # Show scan state
capability-hub doctor               # Health check
capability-hub snippet              # Print the line to add to agent config
capability-hub uninstall            # Clean up
```

---

## Design

1. **Scan, don't route.** Capability Hub never tells AI which tool to use. It just says what's available.
2. **One file, one read.** AI reads the list once per complex task — not every turn.
3. **Zero maintenance.** No manual classification, no keyword tuning. Install and forget.
4. **Agent-agnostic.** Works with Codex, Claude Code, Cursor, or any agent that reads markdown.

---

## Architecture

```
capability-hub install
  ├── scan_capabilities.py          → Agent skills/plugins/MCP
  ├── scan_machine_capabilities.py  → CLI, brew, pip, npm, ollama, apps, services
  └── output/
       ├── capability-list.md       ← AI reads (🟢 high + 🟡 medium confidence)
       └── inventory.json           ← Full detail (paths, versions, health)
```

Confidence tiers:
- 🟢 **High** — from package managers or manually registered. Use directly.
- 🟡 **Medium** — found in PATH. Verify before use.
- 🔴 **Hidden** — temporary scripts, test files, build artifacts. Not shown.

---

## What it's not

- ❌ Not a skill router — doesn't force AI to use specific tools
- ❌ Not an MCP server — doesn't expose tool-calling interfaces
- ❌ Not a skill manager — doesn't install or update your skills
- ❌ Not a context compressor — use Headroom for that

It's a **radar**. It tells AI what's available. AI decides what to use.

---

## License

MIT
