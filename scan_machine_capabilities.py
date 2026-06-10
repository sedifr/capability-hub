#!/usr/bin/env python3
"""Build a bounded whole-machine capability inventory for AI agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "03_最终结果"
CAPABILITY_INDEX_DIR = RESULTS_DIR / "capability-index"
SOURCES_PATH = RESULTS_DIR / "capability-sources.json"
CAPABILITIES_PATH = RESULTS_DIR / "capabilities.json"
INVENTORY_PATH = RESULTS_DIR / "machine-capability-inventory.json"
SUMMARY_PATH = RESULTS_DIR / "machine-capability-summary.md"
BOOTSTRAP_PATH = RESULTS_DIR / "agent-bootstrap.md"
MAP_PATH = RESULTS_DIR / "agent-capability-map.md"
INBOX_PATH = RESULTS_DIR / "machine-capability-inbox.md"
REPORT_PATH = RESULTS_DIR / "machine-capability-report.md"
LIST_PATH = RESULTS_DIR / "capability-list.md"
CHANGE_LOG_PATH = RESULTS_DIR / "capability-change-log.jsonl"

CATEGORY_ZH = {
    "runtime": "语言运行环境",
    "developer_tools": "开发与版本控制工具",
    "agent_runtime_layer": "Agent 运行时增强层",
    "media_tools": "多媒体处理工具",
    "desktop_apps": "本机应用",
    "codex_environment": "Codex 与技能配置",
    "workspace": "用户 AI 工作区",
    "live_services": "本机后台服务",
    "codex_capability_registry": "Codex 技能 / 插件 / MCP 清单",
    "codex_skills": "Codex / Agent 技能",
    "package_tools": "包管理器发现工具",
    "local_models": "本地模型",
    "background_agents": "后台任务",
}

DOMAIN_DEFS = {
    "agent": {
        "title": "Agent / 自动化",
        "categories": {"agent_runtime_layer", "background_agents", "codex_capability_registry"},
        "keywords": {"agent", "codex", "mcp", "browser", "github", "notion", "gmail", "openai", "linear", "sentry"},
    },
    "media": {
        "title": "媒体 / 图片 / 音视频",
        "categories": {"media_tools", "local_models"},
        "keywords": {"audio", "image", "media", "rembg", "tts", "video", "whisper", "yt-dlp", "seedance", "sora", "ffmpeg"},
    },
    "dev": {
        "title": "开发 / 环境 / 代码",
        "categories": {"developer_tools", "runtime", "package_tools"},
        "keywords": {"code", "deploy", "github", "node", "python", "rust", "web", "frontend", "security", "review", "mcp"},
    },
    "docs": {
        "title": "文档 / PDF / 表格",
        "categories": set(),
        "keywords": {"document", "drive", "excel", "pdf", "sheet", "slides", "notion", "文档"},
    },
    "design": {
        "title": "设计 / UI / 前端视觉",
        "categories": {"desktop_apps"},
        "keywords": {"canvas", "design", "figma", "frontend", "impeccable", "ui", "ux", "visual"},
    },
    "writing": {
        "title": "写作 / 内容 / 企划",
        "categories": set(),
        "keywords": {"copy", "content", "idea", "marketing", "planning", "script", "writing", "文案", "企划"},
    },
}

AI_VISIBLE_KINDS = {
    "app",
    "cli",
    "mcp",
    "plugin",
    "registry",
    "service",
    "skill",
    "model",
    "background_agent",
}

AI_VISIBLE_CATEGORIES = {
    "agent_runtime_layer",
    "background_agents",
    "codex_capability_registry",
    "codex_skills",
    "developer_tools",
    "desktop_apps",
    "live_services",
    "local_models",
    "media_tools",
    "package_tools",
    "runtime",
}

DIRECT_CAPABILITY_NAMES = {
    "codexbar": "CodexBar 菜单栏工具",
    "edge-tts": "生成语音和配音",
    "ffmpeg": "处理音视频转码、剪切、合并和抽帧",
    "img2pdf": "图片转 PDF",
    "ffprobe": "读取音视频元数据",
    "imagemagick": "处理图片格式转换和批量图像操作",
    "magick": "处理图片格式转换和批量图像操作",
    "mcp-server-browsermcp": "MCP 浏览器自动化服务",
    "mcporter": "MCP 工具集成管理",
    "ocrmypdf": "PDF OCR 识别",
    "ollama": "调用本地大模型",
    "pipx": "管理独立 Python CLI 工具",
    "rembg": "图片去背景",
    "uv": "Python 项目和环境管理",
    "whisper": "音频转写",
    "yt-dlp": "下载和解析在线视频",
}

NOISE_PATH_PATTERNS = [
    "convertfilestopdf", "convertsegfilestopdf", "converttopdf",
    "dvipdf", "pdf2dsc", "pdf2ps", "pdfattach", "pdfdetach",
    "pdffonts", "pdfinfo", "pdfseparate", "pdfsig", "pdftocairo",
    "pdftohtml", "pdftoppm", "pdftops", "pdftotext", "pdfunite",
    "ps2pdf", "ps2pdf12", "ps2pdf13", "ps2pdf14", "ps2pdfwr",
    "qpdf", "tiff2pdf", "xpdfimport", "imagetops", "pdfimages",
    "text2image", "img2pdf-gui", "jbig2topdf.py",
]

HIGH_VALUE_COMMANDS = sorted(DIRECT_CAPABILITY_NAMES)

DIRECT_CAPABILITY_KEYWORDS = [
    "audio",
    "background",
    "browser",
    "codex",
    "download",
    "image",
    "llm",
    "mcp",
    "model",
    "ocr",
    "speech",
    "transcribe",
    "tts",
    "video",
    "whisper",
]

PATH_CAPABILITY_KEYWORDS = [
    "audio",
    "browser",
    "codex",
    "download",
    "ffmpeg",
    "ffprobe",
    "image",
    "magick",
    "mcp",
    "ocr",
    "ollama",
    "pdf",
    "rembg",
    "screenshot",
    "speech",
    "transcribe",
    "tts",
    "video",
    "whisper",
    "yt-dlp",
    "ytdlp",
]

FULL_ONLY_SOURCE_IDS = {"auto:pip", "auto:cli-auth"}

UNIVERSAL_TOOLS = {
    "git", "Git",
    "python3", "Python 3",
    "node", "Node.js",
    "npm", "npx",
    "brew", "Homebrew",
    "codex", "Codex CLI",
    "rustc", "Rust",
    "cargo", "Cargo",
}

UNIVERSAL_CATEGORIES = {"runtime", "codex_environment", "workspace"}

HIGH_CONFIDENCE_SOURCE_PREFIXES = (
    "auto:brew", "auto:pip", "auto:pipx", "auto:ollama", "auto:codex-capabilities",
    "auto:high-value-path",
)

HIDDEN_PATH_PATTERNS = (
    "/tmp/", "/build/", "/dist/", "node_modules/.bin", "__pycache__",
    ".venv/bin/python", ".venv/bin/pip", ".venv/bin/python3",
)

FINGERPRINT_DIR = RESULTS_DIR / ".fingerprint"

DEFAULT_SOURCE_REGISTRY = {
    "schema_version": "0.1",
    "purpose": "Default read-only capability sources. Users can edit 03_最终结果/capability-sources.json after first install.",
    "scan_policy": {
        "mode": "read_only",
        "do_not_full_disk_scan": True,
        "missing_items_are_not_capabilities": True,
        "live_status_must_be_verified_at_task_time": True,
    },
    "sources": [
        {
            "id": "runtime_cli",
            "type": "cli",
            "category": "runtime",
            "title": "Language runtimes",
            "commands": [
                {"name": "python3", "label": "Python 3", "description": "Run Python scripts and automation.", "version_args": ["--version"]},
                {"name": "node", "label": "Node.js", "description": "Run JavaScript and Node tooling.", "version_args": ["--version"]},
                {"name": "npm", "label": "npm", "description": "Manage Node packages.", "version_args": ["--version"]},
                {"name": "npx", "label": "npx", "description": "Run Node package commands.", "version_args": ["--version"]},
                {"name": "cargo", "label": "Cargo", "description": "Build and manage Rust projects.", "version_args": ["--version"]},
                {"name": "rustc", "label": "Rust", "description": "Rust compiler.", "version_args": ["--version"]},
            ],
        },
        {
            "id": "developer_cli",
            "type": "cli",
            "category": "developer_tools",
            "title": "Developer tools",
            "commands": [
                {"name": "git", "label": "Git", "description": "Version control.", "version_args": ["--version"]},
                {"name": "gh", "label": "GitHub CLI", "description": "GitHub repositories, PRs, issues, and auth status.", "version_args": ["--version"]},
                {"name": "brew", "label": "Homebrew", "description": "macOS package manager.", "version_args": ["--version"]},
                {"name": "codex", "label": "Codex CLI", "description": "Codex local command line entry.", "version_args": ["--version"]},
            ],
        },
        {
            "id": "agent_runtime_cli",
            "type": "cli",
            "category": "agent_runtime_layer",
            "title": "Agent runtime helpers",
            "commands": [
                {"name": "headroom", "label": "Headroom", "description": "Compress long context, logs, and large outputs.", "version_args": ["--version"], "live_check": "http://127.0.0.1:8787/readyz"},
                {"name": "openclaw", "label": "OpenClaw", "description": "Local AI coding / agent tool.", "version_args": ["--version"]},
                {"name": "opencode", "label": "OpenCode", "description": "Local AI coding / agent tool.", "version_args": ["--version"]},
            ],
        },
        {
            "id": "media_cli",
            "type": "cli",
            "category": "media_tools",
            "title": "Media tools",
            "commands": [
                {"name": "ffmpeg", "label": "ffmpeg", "description": "Audio/video processing.", "version_args": ["-version"]},
                {"name": "ffprobe", "label": "ffprobe", "description": "Read audio/video metadata.", "version_args": ["-version"]},
            ],
        },
        {
            "id": "desktop_apps",
            "type": "app",
            "category": "desktop_apps",
            "title": "AI and productivity apps",
            "apps": [
                {"name": "Codex", "description": "Codex desktop app."},
                {"name": "Claude", "description": "Claude desktop app."},
                {"name": "Cursor", "description": "Cursor editor."},
                {"name": "OpenClaw", "description": "Local AI coding / agent app."},
                {"name": "OpenCode", "description": "Local AI coding / agent app."},
            ],
        },
        {
            "id": "codex_paths",
            "type": "path",
            "category": "codex_environment",
            "title": "Codex and skill paths",
            "paths": [
                {"path": "~/.codex/AGENTS.md", "label": "Codex global rules", "description": "Codex global instruction file."},
                {"path": "~/.codex/config.toml", "label": "Codex config", "description": "Codex plugin, MCP, and runtime config."},
                {"path": "~/.codex/skills", "label": "Codex skills", "description": "Local Codex skill directory."},
                {"path": "~/.agents/skills", "label": "Agents skills", "description": "Shared or compatible skill directory."},
                {"path": "~/.skillshub", "label": "Skillshub skills", "description": "Local skillhub directory."},
            ],
        },
        {
            "id": "local_services",
            "type": "service",
            "category": "live_services",
            "title": "Local services",
            "services": [
                {"name": "Headroom Proxy", "url": "http://127.0.0.1:8787/readyz", "description": "Headroom local proxy health check."}
            ],
        },
    ],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_registry() -> dict[str, Any]:
    if SOURCES_PATH.exists():
        return load_json(SOURCES_PATH)
    write_json(SOURCES_PATH, DEFAULT_SOURCE_REGISTRY)
    return DEFAULT_SOURCE_REGISTRY


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def expand_path(value: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(value)))


def command_version(command: str, args: list[str]) -> str:
    try:
        proc = subprocess.run(
            [command, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=4,
            check=False,
        )
        return proc.stdout.splitlines()[0][:180] if proc.stdout else ""
    except Exception:
        return ""


def run_command(args: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout
    except Exception as exc:
        return 1, str(exc)


def http_health(url: str) -> tuple[str, str]:
    try:
        with urlopen(url, timeout=2) as resp:
            body = resp.read(300).decode("utf-8", errors="replace").strip()
            status = "ok" if 200 <= resp.status < 300 else "warning"
            return status, body[:240]
    except (URLError, TimeoutError, socket.timeout) as exc:
        return "warning", str(exc)[:240]
    except Exception as exc:
        return "warning", str(exc)[:240]


def make_item(
    *,
    item_id: str,
    kind: str,
    category: str,
    label: str,
    description: str,
    status: str,
    evidence: str,
    path: str | None = None,
    version: str = "",
    live_check: str | None = None,
    source_id: str = "",
    ai_visible: bool = True,
    call_entry: str = "",
    privacy_level: str = "low",
    scan_scope: str = "global",
) -> dict[str, Any]:
    call_entry = call_entry or default_call_entry(kind, label, path, live_check)
    return {
        "id": item_id,
        "kind": kind,
        "category": category,
        "label": label,
        "description": description,
        "status": status,
        "path": path,
        "version": version,
        "evidence": evidence,
        "live_check": live_check,
        "source_id": source_id,
        "call_entry": call_entry,
        "privacy_level": privacy_level,
        "scan_scope": scan_scope,
        "ai_visible": ai_visible,
        "confidence": "high",
        "verify_at_task_time": kind == "service" or bool(live_check),
    }


def default_call_entry(kind: str, label: str, path: str | None, live_check: str | None) -> str:
    if kind == "cli":
        return f"命令行调用：{label}"
    if kind == "service":
        return f"HTTP 服务：{live_check or path or label}"
    if kind == "app":
        return f"桌面应用：{label}；需插件、URL Scheme、AppleScript 或 Computer Use"
    if kind == "path":
        return f"文件/目录入口：{path or label}"
    if kind == "model":
        return f"本地模型调用：{label}"
    if kind == "skill":
        return f"Codex/Agent 技能：{label}"
    if kind == "plugin":
        return f"Codex 插件：{label}"
    if kind == "mcp":
        return f"MCP 工具：{label}"
    if kind == "registry":
        return f"能力注册表：{path or label}"
    if kind == "background_agent":
        return f"后台任务：{label}；执行前验证运行状态"
    return f"按详细清单确认入口：{label}"


def pip_entry_points() -> dict[str, list[str]]:
    """Return {package_name: [entry_point_strings]} for installed pip packages.
    Only captures console_scripts group — real user-facing CLI tools.
    Executed once per full scan via importlib.metadata — no per-package subprocess."""
    code, output = run_command(
        ["python3", "-c", (
            "import importlib.metadata,json;"
            "pkgs={};"
            "[pkgs.update({d.metadata['Name'].lower():"
            "[f'{ep.name}={ep.value}' for ep in d.entry_points"
            "if ep.group == 'console_scripts']})"
            "for d in importlib.metadata.distributions()"
            "if d.metadata.get('Name') and any(ep.group == 'console_scripts' for ep in d.entry_points)];"
            "print(json.dumps(pkgs))"
        )],
        timeout=15,
    )
    if code != 0:
        return {}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {}


def package_description(name: str) -> str:
    normalized = name.lower()
    if normalized in DIRECT_CAPABILITY_NAMES:
        return DIRECT_CAPABILITY_NAMES[normalized]
    if any(keyword in normalized for keyword in DIRECT_CAPABILITY_KEYWORDS):
        return "可调用工具或 AI 相关本机能力"
    return "系统工具（用途待确认）"


def package_ai_visible(name: str, entry_points_map: dict[str, list[str]] | None = None) -> bool:
    """Return True if the pip package should appear in the AI-visible map.
    Priority: known name > has matching console_script > fallback keyword (for brew/npm).
    Matching rule: at least one console_script name matches the package name (de-hyphened)."""
    normalized = name.lower()
    if normalized in DIRECT_CAPABILITY_NAMES:
        return True
    if entry_points_map is not None:
        if normalized not in entry_points_map:
            return False
        normalized_dehyphen = normalized.replace('-', '').replace('_', '')
        for ep_str in entry_points_map[normalized]:
            ep_name = ep_str.split('=')[0].lower().replace('-', '').replace('_', '')
            if ep_name == normalized_dehyphen:
                return True
        return False
    return any(keyword in normalized for keyword in DIRECT_CAPABILITY_KEYWORDS)


def assign_confidence(item: dict[str, Any]) -> str:
    """Assign confidence tier based purely on static signals (zero subprocess).
    Returns: high | medium | low | hidden"""
    source_id = str(item.get("source_id", ""))
    path = str(item.get("path", ""))
    label = str(item.get("label", "")).lower()
    if source_id.startswith(HIGH_CONFIDENCE_SOURCE_PREFIXES):
        return "high"
    if source_id and not source_id.startswith("auto:"):
        return "high"
    if any(pattern in path for pattern in HIDDEN_PATH_PATTERNS):
        return "hidden"
    if label.startswith("test_") or label.endswith("_test"):
        return "hidden"
    if source_id in {"auto:dynamic-path", "auto:high-value-path"}:
        return "medium"
    return "low"


def compute_fingerprint() -> str:
    """Compute a hash of key data sources. Unchanged hash = no scan needed."""
    hasher = hashlib.sha256()
    for cmd, args in [
        ("brew", ["list", "--formula", "-1"]),
        ("ollama", ["list"]),
        ("npm", ["list", "-g", "--depth=0"]),
        ("python3", ["-m", "pip", "list", "--format=json"]),
    ]:
        if not shutil.which(cmd):
            continue
        code, output = run_command([cmd, *args], timeout=12)
        if code == 0:
            hasher.update(output.encode("utf-8", errors="replace"))
    for skills_dir in [Path.home() / ".codex" / "skills", Path.home() / ".agents" / "skills", Path.home() / ".skillshub"]:
        if not skills_dir.is_dir():
            continue
        try:
            mtimes = sorted(str(skills_dir / d.name) + str(d.stat().st_mtime_ns)
                          for d in skills_dir.iterdir() if d.is_dir())
            hasher.update("".join(mtimes).encode())
        except OSError:
            pass
    return hasher.hexdigest()


def truncate_text(text: str, limit: int = 72) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def scan_cli(source: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in source.get("commands", []):
        name = command["name"]
        resolved = shutil.which(name)
        version = command_version(name, command.get("version_args", ["--version"])) if resolved else ""
        live_check = command.get("live_check")
        if live_check and resolved:
            live_status, live_detail = http_health(live_check)
            evidence = f"command found; live check {live_status}: {live_detail}"
            status = "ok" if live_status == "ok" else "warning"
        else:
            evidence = "command found in PATH" if resolved else "command not found in PATH"
            status = "ok" if resolved else "missing"
        results.append(
            make_item(
                item_id=f"cli:{name}",
                kind="cli",
                category=source["category"],
                label=command.get("label", name),
                description=command.get("description", ""),
                status=status,
                evidence=evidence,
                path=resolved,
                version=version,
                live_check=live_check,
                source_id=source["id"],
            )
        )
    return results


def scan_apps(source: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    app_root = Path("/Applications")
    for app in source.get("apps", []):
        name = app["name"]
        app_path = app_root / f"{name}.app"
        exists = app_path.exists()
        results.append(
            make_item(
                item_id=f"app:{name.lower().replace(' ', '-')}",
                kind="app",
                category=source["category"],
                label=name,
                description=app.get("description", ""),
                status="ok" if exists else "missing",
                evidence="app exists under /Applications" if exists else "app not found under /Applications",
                path=str(app_path),
                source_id=source["id"],
            )
        )
    return results


def scan_paths(source: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path_info in source.get("paths", []):
        raw_path = path_info["path"]
        path = expand_path(raw_path)
        exists = path.exists()
        detail = "directory exists" if path.is_dir() else "file exists" if path.is_file() else "path not found"
        results.append(
            make_item(
                item_id=f"path:{raw_path}",
                kind="path",
                category=source["category"],
                label=path_info.get("label", raw_path),
                description=path_info.get("description", ""),
                status="ok" if exists else "missing",
                evidence=detail,
                path=str(path),
                source_id=source["id"],
            )
        )
    return results


def scan_services(source: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for service in source.get("services", []):
        status, detail = http_health(service["url"])
        results.append(
            make_item(
                item_id=f"service:{service['name'].lower().replace(' ', '-')}",
                kind="service",
                category=source["category"],
                label=service["name"],
                description=service.get("description", ""),
                status=status,
                evidence=detail,
                path=service["url"],
                live_check=service["url"],
                source_id=source["id"],
            )
        )
    return results


def scan_high_value_commands(existing_ids: set[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in HIGH_VALUE_COMMANDS:
        if f"cli:{command}" in existing_ids:
            continue
        resolved = shutil.which(command)
        if not resolved:
            continue
        results.append(
            make_item(
                item_id=f"cli:{command}",
                kind="cli",
                category="media_tools" if command not in {"ollama", "pipx", "uv"} else "developer_tools",
                label=command,
                description=DIRECT_CAPABILITY_NAMES[command],
                status="ok",
                evidence="high-value command found in PATH",
                path=resolved,
                version=command_version(command, ["--version"]),
                source_id="auto:high-value-path",
                ai_visible=True,
            )
        )
    return results


def is_user_tool_dir(path: Path) -> bool:
    text = str(path.resolve())
    home_text = str(Path.home())
    return (
        text.startswith(home_text)
        or text.startswith("/opt/homebrew/")
        or text.startswith("/usr/local/")
    )


def dynamic_command_category(name: str) -> str:
    normalized = name.lower()
    if any(token in normalized for token in ["audio", "ffmpeg", "ffprobe", "image", "magick", "rembg", "speech", "tts", "video", "whisper", "yt-dlp"]):
        return "media_tools"
    if any(token in normalized for token in ["codex", "mcp", "browser"]):
        return "agent_runtime_layer"
    if "pdf" in normalized or "ocr" in normalized:
        return "developer_tools"
    return "developer_tools"


def scan_dynamic_path_commands(existing_ids: set[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        path = Path(directory).expanduser()
        if not path.is_dir() or not is_user_tool_dir(path):
            continue
        try:
            entries = sorted(path.iterdir(), key=lambda value: value.name.lower())
        except OSError:
            continue
        for entry in entries:
            if not entry.is_file() or not os.access(entry, os.X_OK):
                continue
            name = entry.name
            item_id = f"cli:{name}"
            if item_id in existing_ids or item_id in seen:
                continue
            normalized = name.lower().replace("-", "").replace("_", "")
            if not any(keyword.replace("-", "") in normalized for keyword in PATH_CAPABILITY_KEYWORDS):
                continue
            seen.add(item_id)
            description = package_description(name)
            if "用途待确认" in description:
                description = "用户安装区可执行工具，执行前验证用途"
            results.append(
                make_item(
                    item_id=item_id,
                    kind="cli",
                    category=dynamic_command_category(name),
                    label=name,
                    description=description,
                    status="ok",
                    evidence="dynamic PATH scan",
                    path=str(entry),
                    version="",
                    source_id="auto:dynamic-path",
                    ai_visible=True,
                )
            )
    return results


def scan_brew_packages() -> list[dict[str, Any]]:
    if not shutil.which("brew"):
        return []
    code, output = run_command(["brew", "list", "--formula", "-1"], timeout=12)
    if code != 0:
        return []
    results: list[dict[str, Any]] = []
    for name in sorted({line.strip() for line in output.splitlines() if line.strip()}):
        visible = package_ai_visible(name)
        results.append(
            make_item(
                item_id=f"brew:{name}",
                kind="package",
                category="package_tools",
                label=name,
                description=package_description(name),
                status="ok",
                evidence="brew formula installed",
                path=None,
                source_id="auto:brew",
                ai_visible=visible,
            )
        )
    return results


def scan_npm_globals() -> list[dict[str, Any]]:
    if not shutil.which("npm"):
        return []
    code, output = run_command(["npm", "list", "-g", "--depth=0", "--json"], timeout=12)
    if code != 0 and not output.strip():
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []
    dependencies = payload.get("dependencies", {})
    if not isinstance(dependencies, dict):
        return []
    results: list[dict[str, Any]] = []
    for name, info in sorted(dependencies.items()):
        version = info.get("version", "") if isinstance(info, dict) else ""
        visible = package_ai_visible(name)
        results.append(
            make_item(
                item_id=f"npm-global:{name}",
                kind="package",
                category="package_tools",
                label=name,
                description=package_description(name),
                status="ok",
                evidence="npm global package installed",
                version=version,
                source_id="auto:npm-global",
                ai_visible=visible,
            )
        )
    return results


def scan_pipx_packages() -> list[dict[str, Any]]:
    if not shutil.which("pipx"):
        return []
    code, output = run_command(["pipx", "list", "--json"], timeout=12)
    if code != 0:
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []
    venvs = payload.get("venvs", {})
    if not isinstance(venvs, dict):
        return []
    results: list[dict[str, Any]] = []
    for name, info in sorted(venvs.items()):
        metadata = info.get("metadata", {}) if isinstance(info, dict) else {}
        main_package = metadata.get("main_package", {}) if isinstance(metadata, dict) else {}
        apps = main_package.get("apps", []) if isinstance(main_package, dict) else []
        app_label = ", ".join(apps[:3]) if apps else name
        visible = package_ai_visible(name) or any(package_ai_visible(app) for app in apps)
        results.append(
            make_item(
                item_id=f"pipx:{name}",
                kind="package",
                category="package_tools",
                label=app_label,
                description=package_description(name),
                status="ok",
                evidence="pipx package installed",
                source_id="auto:pipx",
                ai_visible=visible,
            )
        )
    return results


def scan_python_cli_packages() -> list[dict[str, Any]]:
    """Register pip packages that have CLI entry points (real tools, not just libraries)."""
    if not shutil.which("python3"):
        return []
    entry_points_map = pip_entry_points()
    code, output = run_command(["python3", "-m", "pip", "list", "--format=json"], timeout=12)
    if code != 0:
        return []
    try:
        packages = json.loads(output)
    except json.JSONDecodeError:
        return []
    results: list[dict[str, Any]] = []
    for pkg in packages:
        name = str(pkg.get("name", ""))
        if not name:
            continue
        has_entry_point = package_ai_visible(name, entry_points_map)
        is_known = name.lower() in DIRECT_CAPABILITY_NAMES
        if not has_entry_point and not is_known:
            continue
        results.append(
            make_item(
                item_id=f"pip:{name.lower()}",
                kind="package",
                category="package_tools",
                label=name,
                description=package_description(name),
                status="ok",
                evidence="python package installed",
                version=str(pkg.get("version", "")),
                source_id="auto:pip",
                ai_visible=True,
            )
        )
    return results


def scan_ollama_models() -> list[dict[str, Any]]:
    if not shutil.which("ollama"):
        return []
    code, output = run_command(["ollama", "list"], timeout=8)
    if code != 0:
        return []
    results: list[dict[str, Any]] = []
    for index, line in enumerate(output.splitlines()):
        if index == 0 or not line.strip():
            continue
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        results.append(
            make_item(
                item_id=f"ollama:{name}",
                kind="model",
                category="local_models",
                label=name,
                description="本地 Ollama 模型",
                status="ok",
                evidence="ollama model installed",
                source_id="auto:ollama",
                ai_visible=True,
            )
        )
    return results


def scan_launch_agents() -> list[dict[str, Any]]:
    roots = [Path.home() / "Library" / "LaunchAgents", Path("/Library/LaunchAgents")]
    results: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for plist_path in sorted(root.glob("*.plist")):
            name = plist_path.stem
            visible = package_ai_visible(name)
            if not visible:
                continue
            results.append(
                make_item(
                    item_id=f"launchagent:{name}",
                    kind="background_agent",
                    category="background_agents",
                    label=name,
                    description="本机后台任务或 agent",
                    status="ok",
                    evidence="LaunchAgent plist exists",
                    path=str(plist_path),
                    source_id="auto:launchagents",
                    ai_visible=True,
                )
            )
    return results


def scan_docker_runtime() -> list[dict[str, Any]]:
    if not shutil.which("docker"):
        return []
    results = [
        make_item(
            item_id="cli:docker",
            kind="cli",
            category="developer_tools",
            label="Docker",
            description="容器、镜像和本地开发服务管理入口",
            status="ok",
            evidence="docker command found in PATH",
            path=shutil.which("docker"),
            source_id="auto:docker",
            ai_visible=True,
            privacy_level="medium",
        )
    ]
    code, output = run_command(["docker", "ps", "--format", "{{json .}}"], timeout=6)
    if code != 0:
        results.append(
            make_item(
                item_id="service:docker-daemon",
                kind="service",
                category="live_services",
                label="Docker daemon",
                description="Docker 后台服务；当前可能未运行或无权限",
                status="warning",
                evidence=truncate_text(output, 160),
                source_id="auto:docker",
                ai_visible=True,
                privacy_level="medium",
            )
        )
        return results
    for line in output.splitlines()[:20]:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = str(payload.get("Names") or payload.get("ID") or "").strip()
        image = str(payload.get("Image") or "").strip()
        ports = str(payload.get("Ports") or "").strip()
        if not name:
            continue
        results.append(
            make_item(
                item_id=f"docker-container:{name}",
                kind="service",
                category="live_services",
                label=f"Docker: {name}",
                description=f"运行中的容器服务：{image}",
                status="ok",
                evidence=f"docker ps; ports={ports or '-'}",
                source_id="auto:docker",
                ai_visible=True,
                privacy_level="medium",
                call_entry=f"Docker 容器：docker exec / docker logs / 端口访问；{name}",
            )
        )
    return results


def scan_cli_auth_states() -> list[dict[str, Any]]:
    checks = [
        ("gh", ["auth", "status"], "GitHub CLI 登录状态", "GitHub 仓库、Issue、PR 和发布能力入口"),
        ("vercel", ["whoami"], "Vercel CLI 登录状态", "Vercel 部署能力入口"),
        ("netlify", ["status"], "Netlify CLI 登录状态", "Netlify 部署能力入口"),
        ("wrangler", ["whoami"], "Cloudflare Wrangler 登录状态", "Cloudflare Workers/Pages 部署能力入口"),
    ]
    results: list[dict[str, Any]] = []
    for command, args, label, description in checks:
        if not shutil.which(command):
            continue
        code, _output = run_command([command, *args], timeout=5)
        status = "ok" if code == 0 else "warning"
        results.append(
            make_item(
                item_id=f"auth:{command}",
                kind="service",
                category="live_services",
                label=label,
                description=description,
                status=status,
                evidence="auth command succeeded" if code == 0 else "auth command failed or requires login",
                source_id="auto:cli-auth",
                ai_visible=True,
                privacy_level="medium",
                call_entry=f"通过 `{command}` CLI 调用；只记录登录状态，不记录 token",
            )
        )
    return results


def scan_codex_registry() -> list[dict[str, Any]]:
    if not CAPABILITIES_PATH.exists():
        return []
    registry = load_json(CAPABILITIES_PATH)
    counts = registry.get("counts", {})
    total = sum(counts.values()) if isinstance(counts, dict) else 0
    detail = ", ".join(f"{key}: {value}" for key, value in sorted(counts.items()))
    return [
        make_item(
            item_id="registry:codex-capabilities",
            kind="registry",
            category="codex_capability_registry",
            label="Codex 能力扫描结果",
            description="已由 Capability Hub 扫描到的 Codex 技能、插件、MCP、CLI、App 和本地服务。",
            status="ok" if total else "warning",
            evidence=f"total {total}; {detail}" if detail else "empty registry",
            path=str(CAPABILITIES_PATH),
        )
    ]


def scan_codex_skill_index() -> list[dict[str, Any]]:
    if not CAPABILITIES_PATH.exists():
        return []
    registry = load_json(CAPABILITIES_PATH)
    results: list[dict[str, Any]] = []
    for cap in registry.get("capabilities", []):
        cap_type = cap.get("type")
        if cap_type not in {"skill", "plugin", "mcp"}:
            continue
        cap_id = str(cap.get("id", ""))
        item_id = cap_id if cap_id.startswith(f"{cap_type}:") else f"{cap_type}:{cap_id}"
        label = str(cap.get("name") or cap_id)
        description = str(cap.get("description") or "Codex/Agent 可用能力")
        results.append(
            make_item(
                item_id=item_id,
                kind=cap_type,
                category="codex_skills" if cap_type == "skill" else "codex_capability_registry",
                label=label,
                description=truncate_text(description, 72),
                status=str(cap.get("health", {}).get("status", "ok")),
                evidence="from capabilities.json",
                path=cap.get("path"),
                source_id="auto:codex-capabilities",
                ai_visible=True,
            )
        )
    return results


def scan_sources(source_registry: dict[str, Any], mode: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for source in source_registry.get("sources", []):
        source_type = source.get("type")
        if source_type == "cli":
            results.extend(scan_cli(source))
        elif source_type == "app":
            results.extend(scan_apps(source))
        elif source_type == "path":
            results.extend(scan_paths(source))
        elif source_type == "service":
            results.extend(scan_services(source))
    existing_ids = {str(item.get("id", "")) for item in results}
    high_value_items = scan_high_value_commands(existing_ids)
    results.extend(high_value_items)
    existing_ids.update(str(item.get("id", "")) for item in high_value_items)
    results.extend(scan_dynamic_path_commands(existing_ids))
    results.extend(scan_codex_registry())
    results.extend(scan_codex_skill_index())
    results.extend(scan_brew_packages())
    results.extend(scan_npm_globals())
    results.extend(scan_pipx_packages())
    results.extend(scan_ollama_models())
    results.extend(scan_launch_agents())
    results.extend(scan_docker_runtime())
    if mode == "full":
        results.extend(scan_python_cli_packages())
        results.extend(scan_cli_auth_states())
    results.sort(key=lambda value: (value["category"], value["kind"], value["id"]))
    return results


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in items:
        value = entry[key]
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def merge_refresh_with_baseline(scanned_items: list[dict[str, Any]], previous_inventory: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not previous_inventory:
        return scanned_items
    current_ids = {item_key(item) for item in scanned_items}
    merged = list(scanned_items)
    for item in previous_inventory.get("items", []):
        if item_key(item) in current_ids:
            continue
        if item.get("source_id") not in FULL_ONLY_SOURCE_IDS:
            continue
        preserved = dict(item)
        preserved["preserved_from_full_scan"] = True
        preserved["verify_at_task_time"] = True
        merged.append(preserved)
    merged.sort(key=lambda value: (value["category"], value["kind"], value["id"]))
    return merged


def build_inventory(source_registry: dict[str, Any], mode: str, previous_inventory: dict[str, Any] | None) -> dict[str, Any]:
    scanned_items = scan_sources(source_registry, mode)
    if mode == "refresh":
        scanned_items = merge_refresh_with_baseline(scanned_items, previous_inventory)
    for item in scanned_items:
        item["confidence"] = assign_confidence(item)
    items = [entry for entry in scanned_items if entry["status"] != "missing"]
    missing_items = [entry for entry in scanned_items if entry["status"] == "missing"]
    return {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "host": socket.gethostname(),
        "project": "Codex Capability Hub",
        "positioning": "Agent runtime capability awareness layer. It is not a forced skill router.",
        "source_file": str(SOURCES_PATH),
        "bootstrap_file": str(BOOTSTRAP_PATH),
        "map_file": str(MAP_PATH),
        "index_dir": str(CAPABILITY_INDEX_DIR),
        "summary_file": str(SUMMARY_PATH),
        "inbox_file": str(INBOX_PATH),
        "change_log_file": str(CHANGE_LOG_PATH),
        "scan_policy": source_registry.get("scan_policy", {}),
        "scan_mode": mode,
        "scan_diagnostics": {
            "scanned_total": len(scanned_items),
            "dropped_missing": len(missing_items),
            "rule": "Missing scan candidates are not registered as capabilities. Refresh mode preserves full-scan-only items from the previous baseline.",
        },
        "counts": {
            "total": len(items),
            "by_status": count_by(items, "status"),
            "by_category": count_by(items, "category"),
        },
        "items": items,
    }


def item_key(item: dict[str, Any]) -> str:
    return str(item.get("id", ""))


def compare_items(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, Any]:
    previous_by_id = {item_key(item): item for item in previous if item_key(item)}
    current_by_id = {item_key(item): item for item in current if item_key(item)}
    added = sorted(set(current_by_id) - set(previous_by_id))
    removed = sorted(set(previous_by_id) - set(current_by_id))
    changed: list[dict[str, Any]] = []
    watched_fields = ["status", "path", "version", "live_check", "label", "kind", "category", "call_entry", "privacy_level", "scan_scope"]
    for cap_id in sorted(set(previous_by_id) & set(current_by_id)):
        before = previous_by_id[cap_id]
        after = current_by_id[cap_id]
        diff = {
            field: {"before": before.get(field), "after": after.get(field)}
            for field in watched_fields
            if before.get(field) != after.get(field)
        }
        if diff:
            changed.append({"id": cap_id, "fields": diff})
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
        },
    }


def write_change_log(previous_inventory: dict[str, Any] | None, current_inventory: dict[str, Any]) -> None:
    previous_items = previous_inventory.get("items", []) if previous_inventory else []
    changes = compare_items(previous_items, current_inventory.get("items", []))
    entry = {
        "generated_at": current_inventory["generated_at"],
        "previous_generated_at": previous_inventory.get("generated_at") if previous_inventory else None,
        "changes": changes,
    }
    append_jsonl(CHANGE_LOG_PATH, entry)


def grouped_active(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in items:
        if entry["status"] == "missing":
            continue
        grouped.setdefault(entry["category"], []).append(entry)
    return grouped


def ai_map_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        item
        for item in items
        if item.get("status") != "missing"
        and item.get("ai_visible", True)
        and item.get("kind") in AI_VISIBLE_KINDS
        and item.get("confidence", "low") in {"high", "medium"}
        and not is_noise_tool(item)
        and not is_universal(item)
    ]
    selected.sort(key=lambda value: (value.get("confidence", "") != "high", value.get("category", ""), value.get("kind", ""), value.get("label", "")))
    return selected


def is_universal(item: dict[str, Any]) -> bool:
    """过滤 AI 训练数据已知且所有机器都有的东西（git、python、node 等）。"""
    label = str(item.get("label", ""))
    if label in UNIVERSAL_TOOLS:
        return True
    cat = str(item.get("category", ""))
    if cat in UNIVERSAL_CATEGORIES:
        return True
    return False


def is_noise_tool(item: dict[str, Any]) -> bool:
    """Filter out system utilities that aren't useful to AI."""
    label = str(item.get("label", "")).lower()
    if label in (n.lower() for n in NOISE_PATH_PATTERNS):
        return True
    if item.get("source_id") == "auto:dynamic-path" and item.get("confidence") != "high":
        desc = str(item.get("description", ""))
        if "系统工具" in desc or "用途待确认" in desc:
            return True
    return False


def domain_for_item(item: dict[str, Any]) -> str:
    category = str(item.get("category", ""))
    haystack = " ".join(
        [
            str(item.get("id", "")),
            str(item.get("label", "")),
            str(item.get("description", "")),
            str(item.get("kind", "")),
            category,
        ]
    ).lower()
    scores: dict[str, int] = {}
    for domain, definition in DOMAIN_DEFS.items():
        score = 0
        if category in definition["categories"]:
            score += 3
        score += sum(1 for keyword in definition["keywords"] if keyword in haystack)
        if score:
            scores[domain] = score
    if not scores:
        return "agent" if category.startswith("codex") else "dev"
    return max(scores, key=lambda key: (scores[key], key))


def group_by_domain(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {domain: [] for domain in DOMAIN_DEFS}
    for item in items:
        grouped.setdefault(domain_for_item(item), []).append(item)
    for entries in grouped.values():
        entries.sort(key=lambda value: (value.get("kind", ""), value.get("label", "")))
    return grouped


def render_status(status: str) -> str:
    return {"ok": "可用", "warning": "需现场确认", "missing": "未发现"}.get(status, status)


def render_summary(inventory: dict[str, Any]) -> str:
    counts = inventory["counts"]
    lines = [
        "# 本机能力总览",
        "",
        "这是给 Codex 和其他 AI agent 按需查看的短版入口。",
        "",
        "定位：本机能力感知层，不是强制技能路由器。",
        "",
        "## 使用规则",
        "",
        "1. 普通聊天、简单问答、小改动不要读取完整清单。",
        "2. 代码、文件、设计、自动化、部署、多媒体、环境排查等复杂任务，可先看本文件。",
        "3. 本文件只说明“本机可能有什么能力”；版本、端口、登录态、后台服务运行状态，执行前必须现场验证。",
        f"4. 需要详细路径、检测方式和完整状态时，读取 `{INVENTORY_PATH.name}`。",
        f"5. 新发现但解释不清的能力先看 `{INBOX_PATH.name}`，不要直接当成正式能力使用。",
        "",
        "## 扫描摘要",
        "",
        f"- 更新时间：`{inventory['generated_at']}`",
        f"- 主机：`{inventory['host']}`",
        f"- 已登记真实能力条目：`{counts['total']}`",
        f"- 扫描模式：`{inventory.get('scan_mode', 'unknown')}`",
        f"- 扫描中丢弃的缺失候选：`{inventory.get('scan_diagnostics', {}).get('dropped_missing', 0)}`",
        f"- 状态统计：{', '.join(f'{render_status(k)} {v}' for k, v in counts['by_status'].items())}",
        "",
        "## 可用能力分组",
        "",
    ]
    for category, entries in sorted(grouped_active(inventory["items"]).items()):
        lines.extend([f"### {CATEGORY_ZH.get(category, category)}", ""])
        for entry in entries[:12]:
            verify = "；需现场验证" if entry.get("verify_at_task_time") else ""
            version = f"；{entry['version']}" if entry.get("version") else ""
            lines.append(f"- {entry['label']}：{entry['description']}（{render_status(entry['status'])}{version}{verify}）")
        if len(entries) > 12:
            lines.append(f"- 另有 {len(entries) - 12} 项，见详细清单。")
        lines.append("")
    live_items = [entry for entry in inventory["items"] if entry.get("verify_at_task_time")]
    if live_items:
        lines.extend(["## 需要现场验证的能力", ""])
        for entry in live_items:
            target = entry.get("live_check") or entry.get("path") or "-"
            lines.append(f"- {entry['label']}：{target}")
        lines.append("")
    lines.extend(
        [
            "## 给其他 Agent 的接入句",
            "",
            "复杂任务前，如果可能受益于本机已有工具、技能、插件、MCP 或环境配置，先查看本机能力总览；简单任务不要查。版本、端口和运行状态必须执行前现场验证。",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def safe_cell(value: Any) -> str:
    text = str(value or "-")
    return text.replace("|", "/").replace("\n", " ").strip()


def render_agent_map(inventory: dict[str, Any]) -> str:
    items = ai_map_items(inventory["items"])
    grouped = group_by_domain(items)
    lines = [
        "# Agent Capability Map",
        "",
        f"generated_at: `{inventory['generated_at']}`",
        f"items: `{len(items)}`",
        f"inventory: `{INVENTORY_PATH.name}`",
        f"inbox: `{INBOX_PATH.name}`",
        "",
        "| domain | count | read when | index |",
        "| --- | ---: | --- | --- |",
    ]
    for domain, definition in DOMAIN_DEFS.items():
        entries = grouped.get(domain, [])
        if not entries:
            continue
        examples = "、".join(safe_cell(item["label"]) for item in entries[:5])
        lines.append(
            "| {domain} | {count} | {examples} | {path} |".format(
                domain=safe_cell(definition["title"]),
                count=len(entries),
                examples=examples,
                path=f"capability-index/{domain}.md",
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def render_capability_list(inventory: dict[str, Any]) -> str:
    """B 版本：纯清单，按置信度 🟢/🟡 两段，一行一项。名称 + 用途，无冗余。"""
    items = ai_map_items(inventory["items"])
    high = [i for i in items if i.get("confidence") == "high"]
    medium = [i for i in items if i.get("confidence") == "medium"]
    lines = [
        "# 本机能力清单",
        "",
        f"updated: `{inventory['generated_at']}`",
        f"total: {len(items)} 项（🟢 {len(high)} + 🟡 {len(medium)}）",
        "",
    ]
    if high:
        lines.append("## 🟢 可直接使用")
        lines.append("")
        for item in high:
            desc = item.get("description", "") or item["label"]
            desc_clean = desc.replace("Codex/Agent 技能：", "").replace("Codex 插件：", "").replace("Codex plugin ", "").replace("MCP 工具：", "").replace("MCP server ", "").replace("命令行调用：", "").replace("桌面应用：", "").replace("本地模型调用：", "").replace("HTTP 服务：", "")
            desc_clean = desc_clean.replace(item["label"], "").strip()
            if desc_clean and desc_clean != item["label"]:
                lines.append(f"- **{safe_cell(item['label'])}** — {truncate_text(desc_clean, 72)}")
            else:
                lines.append(f"- **{safe_cell(item['label'])}**")
        lines.append("")
    if medium:
        lines.append("## 🟡 使用前验证")
        lines.append("")
        for item in medium:
            desc = item.get("description", "") or "用途待确认"
            desc_clean = desc.replace("Codex/Agent 技能：", "").replace("命令行调用：", "").replace(item["label"], "").strip()
            if not desc_clean or desc_clean == item["label"]:
                desc_clean = "用途待确认"
            lines.append(f"- **{safe_cell(item['label'])}** — {truncate_text(desc_clean, 64)} — ⚠️ 使用前验证")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_bootstrap(inventory: dict[str, Any], fmt: str = "flat") -> str:
    if fmt == "flat":
        map_line = f"- 能力清单：`{LIST_PATH}`"
        extra_lines = [
            "当你认为本机已有工具、技能、模型或服务可能帮助当前任务时，先查看能力清单。",
            "简单任务不要查看。需要路径、版本或健康状态时再读完整清单。",
        ]
    else:
        map_line = (
            f"- 一级能力地图：`{MAP_PATH}`\n"
            f"- 领域索引目录：`{CAPABILITY_INDEX_DIR}`"
        )
        extra_lines = [
            "当你认为本机已有工具、技能、模型或服务可能帮助当前任务时，先查看一级能力地图。",
            "简单任务不要查看。需要具体能力时再读对应领域索引；需要路径、版本或健康状态时再读完整清单。",
        ]
    return "\n".join(
        [
            "# Capability Hub Bootstrap",
            "",
            "本机已安装 Capability Hub。",
            "",
            map_line,
            f"- 完整清单：`{INVENTORY_PATH}`",
            "",
            *extra_lines,
            f"处理具体项目时，如果需要识别项目脚本、测试、构建、服务或本项目工具，可运行：`python3 {PROJECT_ROOT / '02_研发产物' / 'capability_hub.py'} project-scan --path <项目路径>`。",
            "如果你因为本地图选择了某个能力，执行前用一句话说明：我在本机能力地图找到了「能力名」。",
            f"更新时间：`{inventory['generated_at']}`",
            "",
        ]
    )
    return "\n".join(
        [
            "# Capability Hub Bootstrap",
            "",
            "本机已安装 Capability Hub。",
            "",
            f"- 一级能力地图：`{MAP_PATH}`",
            f"- 领域索引目录：`{CAPABILITY_INDEX_DIR}`",
            f"- 详细清单：`{INVENTORY_PATH}`",
            "",
            "当你认为本机已有工具、技能、模型或服务可能帮助当前任务时，先查看一级能力地图。",
            "简单任务不要查看。需要具体能力时再读对应领域索引；需要路径、版本或健康状态时再读详细清单。",
            f"处理具体项目时，如果需要识别项目脚本、测试、构建、服务或本项目工具，可运行：`python3 {PROJECT_ROOT / '02_研发产物' / 'capability_hub.py'} project-scan --path <项目路径>`。",
            "如果你因为本地图选择了某个能力，执行前用一句话说明：我在本机能力地图找到了「能力名」。",
            f"更新时间：`{inventory['generated_at']}`",
            "",
        ]
    )


def render_domain_index(domain: str, entries: list[dict[str, Any]]) -> str:
    definition = DOMAIN_DEFS[domain]
    high_entries = [e for e in entries if e.get("confidence") == "high"]
    medium_entries = [e for e in entries if e.get("confidence") == "medium"]
    lines = [
        f"# {definition['title']}",
        "",
        f"count: `{len(entries)}` (🟢 {len(high_entries)} 直接可用 + 🟡 {len(medium_entries)} 使用前验证)",
        f"inventory: `../{INVENTORY_PATH.name}`",
        "",
    ]
    if high_entries:
        lines.append("## 🟢 可直接使用")
        lines.append("")
        lines.append("| name | use | entry |")
        lines.append("| --- | --- | --- |")
        for entry in high_entries:
            lines.append(
                "| {name} | {use} | {entry} |".format(
                    name=safe_cell(entry["label"]),
                    use=safe_cell(truncate_text(entry.get("description"), 64)),
                    entry=safe_cell(truncate_text(entry.get("call_entry"), 40)),
                )
            )
        lines.append("")
    if medium_entries:
        lines.append("## 🟡 使用前验证")
        lines.append("")
        lines.append("| name | use | entry | verify |")
        lines.append("| --- | --- | --- | --- |")
        for entry in medium_entries:
            verify = "执行前测试可用性" if entry.get("verify_at_task_time") else "检查 --help 或运行测试"
            lines.append(
                "| {name} | {use} | {entry} | {verify} |".format(
                    name=safe_cell(entry["label"]),
                    use=safe_cell(truncate_text(entry.get("description"), 56)),
                    entry=safe_cell(truncate_text(entry.get("call_entry"), 36)),
                    verify=safe_cell(verify),
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_domain_indexes(inventory: dict[str, Any]) -> None:
    CAPABILITY_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    grouped = group_by_domain(ai_map_items(inventory["items"]))
    for domain, entries in grouped.items():
        path = CAPABILITY_INDEX_DIR / f"{domain}.md"
        path.write_text(render_domain_index(domain, entries), encoding="utf-8")


def render_inbox(inventory: dict[str, Any]) -> str:
    warnings = [entry for entry in inventory["items"] if entry["status"] == "warning"]
    lines = [
        "# 本机能力待确认区",
        "",
        "这里不是正式能力库。用途是记录扫描器知道要关注、但当前没有确认可用或需要现场确认的能力。",
        "",
        "处理规则：",
        "",
        "1. 不存在的候选不会登记为能力，也不会进入正式总览。",
        "2. warning 项通常是后台服务、端口、登录态或命令版本需要现场验证。",
        "3. 新发现但无法解释用途的真实对象，后续才进入这里等待归类。",
        "",
        "## 需要现场确认",
        "",
    ]
    if warnings:
        lines.extend(["| 能力 | 类型 | 证据 |", "| --- | --- | --- |"])
        for entry in warnings:
            evidence = entry["evidence"].replace("|", "/")
            lines.append(f"| {entry['label']} | {CATEGORY_ZH.get(entry['category'], entry['category'])} | {evidence} |")
    else:
        lines.append("- 暂无。")
    return "\n".join(lines).rstrip() + "\n"


def render_user_report(inventory: dict[str, Any]) -> str:
    """Generate a human-readable installation report for first-time users."""
    items = inventory["items"]
    counts = inventory["counts"]
    by_cat = counts["by_category"]
    by_source: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        src = item.get("source_id", "manual")
        by_source.setdefault(src, []).append(item)

    lines = [
        "# 🖥️ Capability Hub 安装报告",
        "",
        f"> 扫描时间：{inventory['generated_at']}",
        f"> 主机：{inventory['host']}",
        f"> 扫描模式：{inventory.get('scan_mode', '?')}",
        "",
        "---",
        "",
        "## 📊 扫描概况",
        "",
        f"- **总登记能力**：{counts['total']} 项",
        f"- 🟢 高信可直接使用：{sum(1 for i in items if i.get('confidence') == 'high')} 项",
        f"- 🟡 使用前建议验证：{sum(1 for i in items if i.get('confidence') == 'medium')} 项",
        f"- 🔴 已隐藏（测试/临时/构建产物）：{sum(1 for i in items if i.get('confidence') == 'hidden')} 项",
        "",
        "---",
        "",
        "## 📦 按来源",
        "",
        "| 来源 | 数量 | 说明 |",
        "| --- | ---: | --- |",
    ]
    source_labels = {
        "auto:codex-capabilities": ("Codex 技能 + 插件 + MCP", "Agent 内置能力"),
        "auto:brew": ("Homebrew 安装", "brew install 的工具"),
        "auto:dynamic-path": ("PATH 发现的 CLI", "用户目录下可执行文件"),
        "auto:high-value-path": ("高价值 CLI", "手动精选的命令行工具"),
        "auto:pip": ("pip 安装", "有 CLI 入口的 Python 工具"),
        "auto:pipx": ("pipx 安装", "独立 Python 应用"),
        "auto:ollama": ("本地模型", "已下载的 Ollama 模型"),
        "auto:npm-global": ("npm 全局包", "全局安装的 Node 工具"),
        "auto:launchagents": ("后台任务", "macOS LaunchAgent"),
        "auto:docker": ("Docker", "容器运行时"),
        "auto:cli-auth": ("CLI 认证", "GitHub / npm 登录状态"),
    }
    manual_source_labels = {
        "desktop_apps": ("桌面应用", "本机安装的桌面 App"),
        "codex_paths": ("Codex 配置路径", "技能目录、规则文件"),
        "developer_cli": ("开发 CLI", "git、gh、brew 等"),
        "runtime_cli": ("语言运行时 CLI", "Python、Node、Rust"),
        "media_cli": ("媒体 CLI", "ffmpeg、ffprobe"),
        "workspace_paths": ("工作区路径", "AI 工作区"),
        "agent_runtime_cli": ("Agent 运行时 CLI", "Headroom、OpenCode"),
        "local_services": ("本地服务", "本地 HTTP 服务等"),
        "": ("其他", "能力注册表"),
    }
    for src_id in sorted(by_source, key=lambda s: -len(by_source[s])):
        if src_id.startswith("auto:"):
            label, desc = source_labels.get(src_id, (src_id.replace("auto:", ""), ""))
        elif src_id in manual_source_labels:
            label, desc = manual_source_labels[src_id]
        else:
            label, desc = src_id, "手动登记"
        if len(by_source[src_id]) == 0:
            continue
        lines.append(f"| {label} | {len(by_source[src_id])} | {desc} |")

    lines.extend([
        "",
        "---",
        "",
        "## 📂 按分类",
        "",
        "| 分类 | 数量 | 说明 |",
        "| --- | ---: | --- |",
    ])
    cat_labels = {
        "codex_skills": ("Codex 技能", "Agent 可调用的专用能力"),
        "package_tools": ("包管理器工具", "brew / pip / npm 安装的工具"),
        "developer_tools": ("开发工具", "git、gh、ripgrep 等"),
        "media_tools": ("媒体工具", "ffmpeg、图片处理等"),
        "codex_capability_registry": ("Codex 能力注册", "插件与 MCP"),
        "agent_runtime_layer": ("Agent 运行时", "Headroom、OpenClaw 等"),
        "runtime": ("语言运行时", "Python、Node、Rust 等"),
        "desktop_apps": ("桌面应用", "Claude、Codex、VS Code"),
        "local_models": ("本地模型", "Ollama 模型"),
        "live_services": ("后台服务", "本地 HTTP 端点"),
        "background_agents": ("后台任务", "LaunchAgent 任务"),
        "codex_environment": ("Codex 配置", "技能目录、规则文件"),
        "workspace": ("工作区", "AI 工作区路径"),
    }
    for cat in sorted(by_cat, key=lambda c: -by_cat[c]):
        label, desc = cat_labels.get(cat, (cat, ""))
        lines.append(f"| {label} | {by_cat[cat]} | {desc} |")

    lines.extend([
        "",
        "---",
        "",
        "## 🔍 已发现的关键能力",
        "",
    ])
    high_value_cats = {"media_tools", "codex_skills", "local_models", "agent_runtime_layer", "package_tools", "live_services"}
    for cat in ("codex_skills", "media_tools", "package_tools", "local_models", "agent_runtime_layer", "live_services"):
        cat_items = [i for i in items if i.get("category") == cat and i.get("confidence") == "high"]
        if not cat_items:
            continue
        label = cat_labels.get(cat, (cat,))[0]
        names = "、".join(i["label"] for i in cat_items[:12])
        if len(cat_items) > 12:
            names += f" …等 {len(cat_items)} 项"
        lines.append(f"- **{label}**（{len(cat_items)} 项）：{names}")

    lines.extend([
        "",
        "---",
        "",
        "## ⚠️ 未扫描内容",
        "",
        "以下内容不在本次扫描范围内，但 AI 可以直接使用：",
        "",
        "- **pip 纯库**（无 CLI 入口，如 numpy、pillow、scikit-learn）— AI 可通过 `import` 直接调用",
        "- **系统应用**（Safari、Mail、计算器等）— 已自动排除，避免噪音",
        "- **Node 项目级依赖**（node_modules）— 仅登记全局包",
        "- **Python 虚拟环境**（.venv）— 仅登记 capability-sources.json 中手动指定的",
        "",
        "---",
        "",
        "## ✏️ 如何登记自定义环境",
        "",
        f"编辑 `{SOURCES_PATH}` 中的 `custom_environments` 段，添加你的 venv 或自定义工具路径。",
        f"添加后运行 `python3 {(PROJECT_ROOT / '02_研发产物' / 'capability_hub.py')} sync` 刷新地图。",
        "",
        "---",
        "",
        "## 📖 AI 如何读取",
        "",
        f"- 会话入口：`{BOOTSTRAP_PATH}`",
        f"- 领域索引：`{CAPABILITY_INDEX_DIR}/`（按任务领域分类）",
        f"- 完整清单：`{INVENTORY_PATH}`",
        "",
        f"> 💡 Capability Hub 已在后台运行，AI 复杂任务时会自动查看能力地图。",
        "",
    ])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Capability Hub machine inventory")
    parser.add_argument(
        "--mode",
        choices=["full", "refresh"],
        default=os.environ.get("CAPABILITY_HUB_SCAN_MODE", "refresh"),
        help="full builds the first baseline; refresh updates lightweight changing sources",
    )
    parser.add_argument(
        "--format",
        choices=["flat", "domain"],
        default="flat",
        help="flat: single capability list (B版); domain: 6-category index (A版)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    fmt = args.format
    if args.mode == "refresh":
        current_fp = compute_fingerprint()
        FP_PATH = FINGERPRINT_DIR / "last-fingerprint.txt"
        if FP_PATH.exists() and FP_PATH.read_text().strip() == current_fp:
            print("fingerprint=same;no_changes_skipped")
            return 0
    source_registry = load_source_registry()
    previous_inventory = load_json(INVENTORY_PATH) if INVENTORY_PATH.exists() else None
    inventory = build_inventory(source_registry, args.mode, previous_inventory)
    write_change_log(previous_inventory, inventory)
    write_json(INVENTORY_PATH, inventory)
    BOOTSTRAP_PATH.write_text(render_bootstrap(inventory, fmt), encoding="utf-8")
    if fmt == "domain":
        MAP_PATH.write_text(render_agent_map(inventory), encoding="utf-8")
        write_domain_indexes(inventory)
    else:
        LIST_PATH.write_text(render_capability_list(inventory), encoding="utf-8")
    SUMMARY_PATH.write_text(render_summary(inventory), encoding="utf-8")
    INBOX_PATH.write_text(render_inbox(inventory), encoding="utf-8")
    if args.mode == "full":
        REPORT_PATH.write_text(render_user_report(inventory), encoding="utf-8")
    if args.mode == "refresh":
        FINGERPRINT_DIR.mkdir(parents=True, exist_ok=True)
        FP_PATH = FINGERPRINT_DIR / "last-fingerprint.txt"
        FP_PATH.write_text(compute_fingerprint())
    print(str(INVENTORY_PATH))
    print(str(BOOTSTRAP_PATH))
    if fmt == "domain":
        print(str(MAP_PATH))
        print(str(CAPABILITY_INDEX_DIR))
    else:
        print(str(LIST_PATH))
    print(str(SUMMARY_PATH))
    print(str(INBOX_PATH))
    print(str(CHANGE_LOG_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
