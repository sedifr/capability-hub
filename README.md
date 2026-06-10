# Capability Hub

**Agent capability awareness middleware.** Scan your machine → generate a capability list → your AI agent reads it.

Not a skill. Not an MCP tool. Not a router. Just a radar: what tools, models, skills, and services exist on this machine.

> 🖥️ 中文用户：本工具由中文开发者维护，[中文说明见下方](#chinese)。

---

## What it does

```
pip install capability-hub
capability_hub install

→ Scans your machine
→ Generates capability-list.md (157 items, 12KB)
→ Your AI reads it once per complex task
→ AI says: "Found rembg in the capability map, using it."
```

---

## Install

```bash
git clone https://github.com/yourname/capability-hub
cd capability-hub
python3 02_研发产物/capability_hub.py install
```

Output:
```
capability-list.md        ← AI reads this (12KB)
agent-bootstrap.md        ← Entry point for AI
machine-capability-report.md ← Human-readable scan report
```

---

## How AIs use it

**Any AI agent** (Codex, Claude Code, Cursor, etc.) can use this.

Add this line to your agent's config:

```
本机已安装 Capability Hub。执行复杂任务前，先读取本机能力清单：`~/path/to/capability-list.md`。简单任务不要读取。使用能力时说「我在本机能力地图找到了 XX」。
```

Config files by agent:
- **Codex**: `~/.codex/AGENTS.md`
- **Claude Code**: `~/.claude/CLAUDE.md`
- **Cursor**: `.cursorrules` in project root
- **Any agent**: add to system prompt

Or run `capability_hub snippet` to print this line.

---

## Commands

```
capability_hub install              # Full scan + generate map
capability_hub sync                 # Refresh (fingerprint-skipped if no changes)
capability_hub sync --mode full     # Full baseline rescan
capability_hub status               # Show current state
capability_hub doctor               # Health check
capability_hub snippet              # Print agent integration line
capability_hub uninstall            # Clean up
```

---

## What it scans

| Source | Examples |
|--------|---------|
| Codex/Agent skills | frontend-design, pdf, agent-reach |
| pip packages (CLI entry points) | rembg, edge-tts, yt-dlp |
| Homebrew formulas | ffmpeg, ripgrep, ocrmypdf |
| Ollama models | qwen2.5:7b, gemma4:e4b |
| Desktop apps | Photoshop, DaVinci Resolve |
| MCP services | headroom, custom endpoints |
| npm global packages | mcporter |
| LaunchAgents | background tasks |

**It does NOT scan:** system commands (ls, cd), pip libraries without CLI, system apps (Safari, Mail), temporary scripts.

---

## Design principles

1. **Scan, don't route.** Capability Hub never tells AI which tool to use. It just provides the list.
2. **One file, one read.** AI reads `capability-list.md` once per complex task — not every turn.
3. **Zero maintenance.** No manual classification. No keyword tuning. Install and forget.
4. **Agent-agnostic.** Works with Codex, Claude Code, Cursor, or any agent that reads markdown.

---

## Architecture

```
capability_hub install
  ├── scan_capabilities.py         → Codex skills/plugins/MCP (114 items)
  ├── scan_machine_capabilities.py → CLI, brew, pip, npm, ollama, apps, services
  └── outputs
       ├── capability-list.md      ← AI reads (157 items, 🟢 high + 🟡 medium confidence)
       ├── agent-bootstrap.md      ← Entry instruction for AI
       └── inventory.json          ← Full detail (paths, versions, health)
```

---

## Version history

- **B (current)**: Flat list — AI reads once. Default.
- **A (backup)**: Domain-indexed — 6 categories. Use `--format domain`.

Switch: `capability_hub sync --format domain`

---

## <a name="chinese"></a>中文说明

Capability Hub 是一个 Agent 能力感知中间件。扫描本机 → 生成能力清单 → AI 读取。

- **不是技能路由器**：不强制 AI 使用某个工具
- **不是 MCP 工具**：不提供工具调用接口
- **只是雷达**：告诉 AI 本机有什么能用的

安装后生成 `capability-list.md`，AI 在复杂任务前读一次即可。命令见上方 Commands 部分。

---

## License

MIT
