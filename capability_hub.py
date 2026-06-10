#!/usr/bin/env python3
"""Capability Hub CLI — Agent 能力感知中间件。扫描本机 → 生成地图 → AI 自己读取。"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = PROJECT_ROOT
RESULTS_DIR = PROJECT_ROOT / "output"

SYNC_SCRIPT = SCRIPTS_DIR / "sync_capability_hub.py"
PROJECT_SCAN_SCRIPT = SCRIPTS_DIR / "scan_project_capabilities.py"
INVENTORY_PATH = RESULTS_DIR / "machine-capability-inventory.json"
BOOTSTRAP_PATH = RESULTS_DIR / "agent-bootstrap.md"
LIST_PATH = RESULTS_DIR / "capability-list.md"
SUMMARY_PATH = RESULTS_DIR / "machine-capability-summary.md"
INBOX_PATH = RESULTS_DIR / "machine-capability-inbox.md"
REPORT_PATH = RESULTS_DIR / "machine-capability-report.md"
SOURCES_PATH = RESULTS_DIR / "capability-sources.json"
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / "com.capability-hub.sync.plist"
LAUNCH_LABEL = "com.capability-hub.sync"
DEFAULT_MAX_AGE_HOURS = 24

SNIPPET_LINE = (
    f"本机已安装 Capability Hub。执行复杂任务前，先读取本机能力清单："
    f"`{LIST_PATH}`。简单任务不要读取。"
    f"使用能力时说「我在本机能力地图找到了 XX」。"
)


def run_python(script: Path, extra_args: list[str] | None = None) -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run([sys.executable, str(script), *(extra_args or [])], cwd=PROJECT_ROOT, env=env, check=True)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def inventory_freshness(inventory: dict[str, Any], max_age_hours: int) -> str:
    generated_at = inventory.get("generated_at")
    if not generated_at:
        return "unknown"
    try:
        generated = datetime.fromisoformat(generated_at)
    except ValueError:
        return "invalid_timestamp"
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - generated).total_seconds() / 3600
    if age_hours <= max_age_hours:
        return "fresh"
    return f"stale:{age_hours:.1f}h"


def launchctl_target() -> str:
    return f"gui/{os.getuid()}"


def load_schedule() -> str:
    proc = subprocess.run(
        ["launchctl", "bootstrap", launchctl_target(), str(LAUNCH_AGENT_PATH)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if proc.returncode != 0 and "already bootstrapped" not in proc.stdout.lower():
        return f"no: {proc.stdout.strip()[:160]}"
    subprocess.run(
        ["launchctl", "kickstart", "-k", f"{launchctl_target()}/{LAUNCH_LABEL}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return "yes"


def enable_schedule(interval_seconds: int) -> str:
    LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": LAUNCH_LABEL,
        "ProgramArguments": [sys.executable, str(SYNC_SCRIPT)],
        "StartInterval": interval_seconds,
        "RunAtLoad": True,
        "WorkingDirectory": str(PROJECT_ROOT),
        "StandardOutPath": str(RESULTS_DIR / "capability-hub.launchd.out.log"),
        "StandardErrorPath": str(RESULTS_DIR / "capability-hub.launchd.err.log"),
        "EnvironmentVariables": {"PYTHONDONTWRITEBYTECODE": "1"},
    }
    LAUNCH_AGENT_PATH.write_bytes(plistlib.dumps(plist))
    return load_schedule()


def unload_schedule() -> str:
    proc = subprocess.run(
        ["launchctl", "bootout", launchctl_target(), str(LAUNCH_AGENT_PATH)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False,
    )
    if proc.returncode != 0:
        return f"no: {proc.stdout.strip()[:160]}"
    return "yes"


def disable_schedule() -> str:
    if not LAUNCH_AGENT_PATH.exists():
        return "not_present"
    unload_schedule()
    LAUNCH_AGENT_PATH.unlink()
    return "removed"


def is_schedule_loaded() -> bool:
    proc = subprocess.run(
        ["launchctl", "print", f"{launchctl_target()}/{LAUNCH_LABEL}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return proc.returncode == 0


# ── commands ──────────────────────────────────────────────


def command_install(args: argparse.Namespace) -> int:
    """全量扫描 + 生成地图。"""
    command_sync(argparse.Namespace(mode="full", format="flat"))
    schedule_state = enable_schedule(args.interval_seconds) if args.schedule else "not_requested"
    print(f"schedule={schedule_state}")
    print(f"list={LIST_PATH}")
    print(f"bootstrap={BOOTSTRAP_PATH}")
    print(f"report={REPORT_PATH}")
    print()
    print("要让 AI 使用本机能力清单，将下面这行加入 Agent 配置：")
    print(f"  {SNIPPET_LINE}")
    return 0


def command_sync(args: argparse.Namespace) -> int:
    """刷新能力地图。"""
    mode = getattr(args, "mode", "refresh")
    fmt = getattr(args, "format", "flat")
    run_python(SYNC_SCRIPT, ["--mode", mode, "--format", fmt])
    return 0


def command_project_scan(args: argparse.Namespace) -> int:
    """扫描项目目录。"""
    run_python(PROJECT_SCAN_SCRIPT, ["--path", args.path, "--max-tools", str(args.max_tools)])
    return 0


def command_status(_: argparse.Namespace) -> int:
    """查看当前状态。"""
    if not INVENTORY_PATH.exists():
        print("status=not_synced")
        return 1
    inventory = load_json(INVENTORY_PATH)
    counts = inventory.get("counts", {})
    freshness = inventory_freshness(inventory, DEFAULT_MAX_AGE_HOURS)
    schedule_file = LAUNCH_AGENT_PATH.exists()
    schedule_loaded = is_schedule_loaded()
    print("status=ok")
    print(f"generated_at={inventory.get('generated_at')}")
    print(f"freshness={freshness}")
    print(f"items={counts.get('total')}")
    print(f"by_category={counts.get('by_category')}")
    print(f"schedule_file={'present' if schedule_file else 'missing'}")
    print(f"schedule_loaded={'yes' if schedule_loaded else 'no'}")
    print(f"list={LIST_PATH}")
    print(f"bootstrap={BOOTSTRAP_PATH}")
    print(f"inventory={INVENTORY_PATH}")
    return 0


def command_doctor(_: argparse.Namespace) -> int:
    """健康检查。"""
    errors: list[str] = []
    for path in [SOURCES_PATH, INVENTORY_PATH, BOOTSTRAP_PATH, LIST_PATH, SUMMARY_PATH, INBOX_PATH]:
        if not path.exists():
            errors.append(f"missing: {path}")
    for path in [SOURCES_PATH, INVENTORY_PATH]:
        if path.exists():
            try:
                load_json(path)
            except Exception as exc:
                errors.append(f"invalid json: {path}: {exc}")
    pycache = list(PROJECT_ROOT.rglob("__pycache__")) + list(PROJECT_ROOT.rglob("*.pyc"))
    if pycache:
        errors.append(f"python cache files: {len(pycache)}")
    if errors:
        print("doctor=failed")
        for e in errors:
            print(f"- {e}")
        return 1
    print("doctor=ok")
    return 0


def command_uninstall(args: argparse.Namespace) -> int:
    """清理定时任务。注意：不删除已生成的地图文件，你需要手动清理。"""
    schedule_state = disable_schedule() if args.schedule else "not_requested"
    print(f"schedule={schedule_state}")
    print("地图文件保留在 output 目录中，手动删除即可。")
    return 0


def command_snippet(_: argparse.Namespace) -> int:
    """打印接入文本。"""
    print(SNIPPET_LINE)
    return 0


def command_shell_hook(_: argparse.Namespace) -> int:
    """打印 shell hook。"""
    sync_cmd = (
        f"{shutil.which('python3') or sys.executable} "
        f"{Path(__file__).resolve()} sync --mode refresh >/dev/null 2>&1 &"
    )
    print(
        "# 将以下内容加入 ~/.zshrc，实现 pip/brew 安装后自动刷新地图\n"
        "# (可选，不影响正常使用)\n"
        f"capability_hub_sync() {{ {sync_cmd} }}\n"
    )
    return 0


# ── parser ────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capability Hub — Agent 能力感知中间件")
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install", help="全盘扫描 + 生成地图")
    install.add_argument("--schedule", action="store_true", help="同时安装 macOS 定时同步")
    install.add_argument("--interval-seconds", type=int, default=21600, help="定时间隔（秒），默认 6 小时")
    install.set_defaults(func=command_install)

    sync = sub.add_parser("sync", help="刷新能力地图")
    sync.add_argument("--mode", choices=["full", "refresh"], default="refresh")
    sync.add_argument("--format", choices=["flat", "domain"], default="flat", help="flat 纯清单 / domain 领域索引")
    sync.set_defaults(func=command_sync)

    project_scan = sub.add_parser("project-scan", help="扫描项目可调用入口")
    project_scan.add_argument("--path", default=os.getcwd())
    project_scan.add_argument("--max-tools", type=int, default=80)
    project_scan.set_defaults(func=command_project_scan)

    sub.add_parser("status", help="查看状态").set_defaults(func=command_status)
    sub.add_parser("doctor", help="健康检查").set_defaults(func=command_doctor)

    uninstall = sub.add_parser("uninstall", help="移除定时任务")
    uninstall.add_argument("--schedule", action="store_true", help="同时移除 LaunchAgent")
    uninstall.set_defaults(func=command_uninstall)

    sub.add_parser("snippet", help="打印接入文本").set_defaults(func=command_snippet)
    sub.add_parser("hook", help="打印 shell hook").set_defaults(func=command_shell_hook)

    return parser


def main() -> int:
    try:
        args = build_parser().parse_args()
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
