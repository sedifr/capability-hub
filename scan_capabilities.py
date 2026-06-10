#!/usr/bin/env python3
"""Scan local Codex-related capabilities and write a first registry draft.

This script is intentionally read-only for the Codex environment. It reads
local skill folders, Codex config, common command paths, selected apps, and
known local service endpoints, then writes project-local reports.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "03_最终结果" / "capabilities.json"
DEFAULT_SUMMARY = PROJECT_ROOT / "03_最终结果" / "capability-scan-summary.md"

SKILL_ROOTS = [
    Path.home() / ".codex" / "skills",
    Path.home() / ".agents" / "skills",
]

COMMON_CLI = [
    "codex",
    "node",
    "npm",
    "npx",
    "python3",
    "git",
    "gh",
    "brew",
    "cargo",
    "runai",
    "toolkit-ai",
    "skillfish",
    "oag",
    "headroom",
]

APP_NAME_PATTERNS = [
    "Codex",
    "Codex Chrome",
    "CodexBar",
    "Claude",
    "Cursor",
    "OpenCode",
    "OpenClaw",
    "MCP Dock",
]

KNOWN_PROXIES = [
    {
        "id": "headroom-proxy",
        "name": "Headroom Proxy",
        "url": "http://127.0.0.1:8787/readyz",
        "best_for": ["context_compression", "long_output", "large_logs"],
    }
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_.@+-]+", "-", value)
    return value.strip("-") or "unknown"


def read_text(path: Path, limit: int = 20000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    raw = text[3:end]
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            data[key] = value
    return data


def health(status: str, detail: str = "") -> dict[str, str]:
    return {"status": status, "detail": detail}


def capability(
    *,
    cap_id: str,
    cap_type: str,
    name: str,
    source: str,
    path: str | None = None,
    description: str = "",
    best_for: list[str] | None = None,
    risk: str = "low",
    check: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": cap_id,
        "type": cap_type,
        "name": name,
        "zh_name": "",
        "aliases": [],
        "description": description,
        "best_for": best_for or [],
        "source": source,
        "path": path,
        "risk": risk,
        "health": check or health("unknown"),
        "metadata": metadata or {},
    }


def scan_skills() -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    for root in SKILL_ROOTS:
        if not root.exists():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            skill_dir = skill_md.parent
            if is_ignored_skill_dir(skill_dir):
                continue
            text = read_text(skill_md)
            fm = parse_frontmatter(text)
            name = fm.get("name") or skill_dir.name
            description = fm.get("description") or first_nonempty_body_line(text)
            source = "codex" if ".codex" in str(root) else "agents"
            caps.append(
                capability(
                    cap_id=slug(name),
                    cap_type="skill",
                    name=name,
                    description=description,
                    source=source,
                    path=str(skill_dir),
                    best_for=infer_best_for(name, description),
                    risk="low" if source == "codex" else "medium",
                    check=health("ok", "SKILL.md exists"),
                    metadata={"skill_root": str(root)},
                )
            )
    return caps


def is_ignored_skill_dir(skill_dir: Path) -> bool:
    name = skill_dir.name.lower()
    ignored_markers = [
        ".backup",
        "backup-",
        ".bak",
        "-bak",
        "_bak",
        "old-",
        "_old",
        ".old",
        "archive",
    ]
    return any(marker in name for marker in ignored_markers)


def first_nonempty_body_line(text: str) -> str:
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4 :]
    for line in body.splitlines():
        stripped = line.strip("# ").strip()
        if stripped:
            return stripped[:240]
    return ""


def infer_best_for(name: str, description: str) -> list[str]:
    text = f"{name} {description}".lower()
    hints: list[tuple[str, str]] = [
        ("pdf", "pdf"),
        ("doc", "documents"),
        ("sheet", "spreadsheets"),
        ("excel", "spreadsheets"),
        ("figma", "design"),
        ("design", "design"),
        ("frontend", "frontend_ui"),
        ("ui", "frontend_ui"),
        ("github", "github"),
        ("browser", "browser_control"),
        ("security", "security"),
        ("deploy", "deployment"),
        ("video", "video"),
        ("audio", "audio"),
        ("router", "routing"),
        ("mcp", "mcp"),
        ("impeccable", "frontend_ui"),
    ]
    result: list[str] = []
    for needle, value in hints:
        if needle in text and value not in result:
            result.append(value)
    return result


def load_codex_config() -> dict[str, Any]:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists() or tomllib is None:
        return {}
    try:
        with config_path.open("rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def scan_plugins(config: dict[str, Any]) -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    plugins = config.get("plugins", {})
    if not isinstance(plugins, dict):
        return caps
    for name, info in sorted(plugins.items()):
        enabled = bool(info.get("enabled")) if isinstance(info, dict) else False
        plugin_name = name.split("@", 1)[0]
        caps.append(
            capability(
                cap_id=f"plugin:{slug(name)}",
                cap_type="plugin",
                name=name,
                description=f"Codex plugin {name}",
                source="codex-config",
                path=str(Path.home() / ".codex" / "config.toml"),
                best_for=infer_plugin_best_for(plugin_name),
                risk="medium",
                check=health("ok" if enabled else "disabled", "registered in config.toml"),
                metadata={"enabled": enabled, "plugin_name": plugin_name},
            )
        )
    return caps


def infer_plugin_best_for(name: str) -> list[str]:
    mapping = {
        "browser": ["browser_control", "local_web_testing"],
        "chrome": ["browser_control", "logged_in_browser"],
        "github": ["github"],
        "google-drive": ["documents", "drive"],
        "gmail": ["email"],
        "outlook-email": ["email"],
        "outlook-calendar": ["calendar"],
        "computer-use": ["desktop_control"],
        "notion": ["notion"],
        "openai-developers": ["openai_api"],
        "build-web-apps": ["frontend_ui"],
        "remotion": ["video"],
        "hyperframes": ["video"],
        "hugging-face": ["ml"],
        "heygen": ["video"],
    }
    return mapping.get(name, [])


def scan_mcp(config: dict[str, Any]) -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    servers = config.get("mcp_servers", {})
    if not isinstance(servers, dict):
        return caps
    for name, info in sorted(servers.items()):
        command = info.get("command") if isinstance(info, dict) else None
        command_ok = command_exists(command)
        caps.append(
            capability(
                cap_id=f"mcp:{slug(name)}",
                cap_type="mcp",
                name=name,
                description=f"MCP server {name}",
                source="codex-config",
                path=str(Path.home() / ".codex" / "config.toml"),
                best_for=infer_mcp_best_for(name),
                risk="medium",
                check=health(
                    "ok" if command_ok else "warning",
                    f"command {'exists' if command_ok else 'not found'}: {command}",
                ),
                metadata={"command": command, "args": info.get("args", []) if isinstance(info, dict) else []},
            )
        )
    return caps


def infer_mcp_best_for(name: str) -> list[str]:
    mapping = {
        "headroom": ["context_compression", "long_output", "large_logs"],
        "node_repl": ["javascript_runtime", "browser_automation"],
    }
    return mapping.get(name, ["mcp"])


def command_exists(command: str | None) -> bool:
    if not command:
        return False
    if os.path.isabs(command):
        return Path(command).exists()
    return shutil.which(command) is not None


def scan_cli() -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    for cmd in COMMON_CLI:
        resolved = shutil.which(cmd)
        if not resolved:
            continue
        version = get_command_version(cmd)
        caps.append(
            capability(
                cap_id=f"cli:{slug(cmd)}",
                cap_type="cli",
                name=cmd,
                description=f"Local CLI command {cmd}",
                source="PATH",
                path=resolved,
                best_for=infer_cli_best_for(cmd),
                risk="low",
                check=health("ok", "command found in PATH"),
                metadata={"version": version},
            )
        )
    return caps


def get_command_version(cmd: str) -> str:
    version_args = {
        "codex": ["--version"],
        "node": ["--version"],
        "npm": ["--version"],
        "npx": ["--version"],
        "python3": ["--version"],
        "git": ["--version"],
        "gh": ["--version"],
        "brew": ["--version"],
        "cargo": ["--version"],
        "headroom": ["--version"],
    }
    args = version_args.get(cmd, ["--version"])
    try:
        proc = subprocess.run(
            [cmd, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3,
            check=False,
        )
        return proc.stdout.splitlines()[0][:160] if proc.stdout else ""
    except Exception:
        return ""


def infer_cli_best_for(cmd: str) -> list[str]:
    mapping = {
        "codex": ["codex_runtime"],
        "node": ["javascript_runtime"],
        "npm": ["javascript_packages"],
        "npx": ["javascript_packages"],
        "python3": ["python_runtime"],
        "git": ["version_control"],
        "gh": ["github"],
        "brew": ["mac_package_management"],
        "cargo": ["rust_builds"],
        "runai": ["capability_management"],
        "toolkit-ai": ["capability_management"],
        "skillfish": ["skill_management"],
        "oag": ["capability_registry"],
        "headroom": ["context_compression"],
    }
    return mapping.get(cmd, [])


def scan_apps() -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    app_root = Path("/Applications")
    for pattern in APP_NAME_PATTERNS:
        app_path = app_root / f"{pattern}.app"
        if not app_path.exists():
            continue
        caps.append(
            capability(
                cap_id=f"app:{slug(pattern)}",
                cap_type="app",
                name=pattern,
                description=f"macOS application {pattern}",
                source="/Applications",
                path=str(app_path),
                best_for=infer_app_best_for(pattern),
                risk="medium",
                check=health("ok", "app exists"),
            )
        )
    return caps


def infer_app_best_for(name: str) -> list[str]:
    mapping = {
        "Codex": ["codex_runtime"],
        "Codex Chrome": ["browser_control"],
        "CodexBar": ["usage_monitoring"],
        "Claude": ["ai_assistant"],
        "Cursor": ["code_editor"],
        "OpenCode": ["ai_coding_cli"],
        "OpenClaw": ["ai_coding_cli"],
        "MCP Dock": ["mcp_management"],
    }
    return mapping.get(name, [])


def scan_proxies() -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    for proxy in KNOWN_PROXIES:
        status, detail = http_health(proxy["url"])
        caps.append(
            capability(
                cap_id=f"proxy:{slug(proxy['id'])}",
                cap_type="proxy",
                name=proxy["name"],
                description=f"Local service endpoint {proxy['url']}",
                source="localhost",
                path=proxy["url"],
                best_for=proxy["best_for"],
                risk="medium",
                check=health(status, detail),
            )
        )
    return caps


def http_health(url: str) -> tuple[str, str]:
    try:
        with urlopen(url, timeout=2) as resp:
            body = resp.read(300).decode("utf-8", errors="replace")
            return ("ok" if 200 <= resp.status < 300 else "warning", body.strip()[:240])
    except (URLError, TimeoutError, socket.timeout) as exc:
        return "warning", str(exc)[:240]
    except Exception as exc:
        return "warning", str(exc)[:240]


def build_registry() -> dict[str, Any]:
    config = load_codex_config()
    capabilities: list[dict[str, Any]] = []
    capabilities.extend(scan_skills())
    capabilities.extend(scan_plugins(config))
    capabilities.extend(scan_mcp(config))
    capabilities.extend(scan_cli())
    capabilities.extend(scan_apps())
    capabilities.extend(scan_proxies())
    capabilities.sort(key=lambda item: (item["type"], item["id"]))
    return {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "host": socket.gethostname(),
        "project": "Codex Capability Hub",
        "scan_policy": {
            "mode": "read_only",
            "writes_only_under_project": True,
            "config_modified": False,
        },
        "capabilities": capabilities,
        "counts": count_by_type(capabilities),
    }


def count_by_type(capabilities: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for cap in capabilities:
        counts[cap["type"]] = counts.get(cap["type"], 0) + 1
    return dict(sorted(counts.items()))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_summary(path: Path, registry: dict[str, Any]) -> None:
    caps = registry["capabilities"]
    lines = [
        "# Capability Scan Summary",
        "",
        f"- Generated at: `{registry['generated_at']}`",
        f"- Host: `{registry['host']}`",
        f"- Total capabilities: `{len(caps)}`",
        "",
        "## Counts",
        "",
        "| Type | Count |",
        "|---|---:|",
    ]
    for cap_type, count in registry["counts"].items():
        lines.append(f"| `{cap_type}` | {count} |")
    lines.extend(["", "## Warnings", ""])
    warnings = [cap for cap in caps if cap["health"]["status"] != "ok"]
    if warnings:
        for cap in warnings:
            lines.append(f"- `{cap['id']}`: {cap['health']['detail']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Sample Capabilities", ""])
    lines.extend(["| ID | Type | Health | Best For |", "|---|---|---|---|"])
    for cap in caps[:30]:
        lines.append(
            f"| `{cap['id']}` | `{cap['type']}` | `{cap['health']['status']}` | {', '.join(cap['best_for'])} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan local Codex capabilities.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="JSON output path")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY, help="Markdown summary output path")
    args = parser.parse_args()

    registry = build_registry()
    write_json(args.out, registry)
    write_summary(args.summary, registry)
    print(json.dumps({"out": str(args.out), "summary": str(args.summary), "counts": registry["counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
