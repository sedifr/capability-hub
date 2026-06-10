# Capability Hub

**Agent capability awareness middleware.**  
Scan your machine → generate a capability list → your AI agent reads it.

Not a skill. Not an MCP tool. Not a router.  
Just a radar: what tools, models, skills, and services exist on this machine.

---

## Why

You installed 100+ AI agent skills. You `pip install`'d rembg, edge-tts, and yt-dlp. You downloaded 5 Ollama models. You set up custom services and environments.

**Your AI agent doesn't know about any of them.**

Without Capability Hub, you either:
- Manually maintain a list in `AGENTS.md`/`CLAUDE.md` (and forget to update it)
- Hope your AI guesses correctly (it won't)
- Repeatedly tell each AI session "I have rembg installed"

With Capability Hub:

```
Before:  AI writes 20 lines of pillow code to remove a background
After:   AI reads the capability list → "Found rembg, using it."
```

---

## How it works

```
pip install capability-hub
capability-hub install
  └─ Scans your machine: skills, pip, brew, npm, ollama, apps, services
  └─ Generates output/capability-list.md (~150 items, ~12KB)
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
| AI agent skills | frontend-design, pdf, agent-reach, browser-automation |
| pip packages (CLI tools only) | rembg, edge-tts, yt-dlp |
| Homebrew | ffmpeg, ripgrep, ocrmypdf |
| npm global packages | mcporter |
| Ollama models | qwen2.5:7b, gemma4:e4b |
| Desktop apps | Photoshop, DaVinci Resolve |
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
python3 capability_hub.py install
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
