#!/usr/bin/env python3
"""Scan project-local callable entry points for AI agents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / "output"
PROJECT_CAPABILITIES_DIR = RESULTS_DIR / "project-capabilities"

TEXT_LIMIT = 300_000


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path, limit: int = TEXT_LIMIT) -> str:
    data = path.read_bytes()[:limit]
    return data.decode("utf-8", errors="replace")


def safe_slug(path: Path) -> str:
    resolved = str(path.resolve())
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", path.name).strip("-") or "project"
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:10]
    return f"{name}-{digest}"


def make_item(
    *,
    item_id: str,
    kind: str,
    label: str,
    description: str,
    call_entry: str,
    evidence: str,
    privacy_level: str = "low",
    path: str = "",
    verify_at_task_time: bool = True,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "kind": kind,
        "label": label,
        "description": description,
        "call_entry": call_entry,
        "evidence": evidence,
        "path": path,
        "privacy_level": privacy_level,
        "scan_scope": "project",
        "verify_at_task_time": verify_at_task_time,
        "ai_visible": True,
    }


def truncate(text: str, limit: int = 96) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def command_from_package_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        return "bun"
    return "npm"


def scan_package_json(root: Path) -> list[dict[str, Any]]:
    path = root / "package.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(read_text(path))
    except json.JSONDecodeError:
        return [
            make_item(
                item_id="project:package-json-invalid",
                kind="project_warning",
                label="package.json",
                description="package.json 存在但无法解析",
                call_entry="先修复 package.json，再调用项目脚本",
                evidence="invalid package.json",
                path=str(path),
            )
        ]
    scripts = payload.get("scripts", {})
    if not isinstance(scripts, dict):
        return []
    manager = command_from_package_manager(root)
    results: list[dict[str, Any]] = []
    for name, command in sorted(scripts.items()):
        if not isinstance(command, str):
            continue
        results.append(
            make_item(
                item_id=f"project:npm-script:{name}",
                kind="project_script",
                label=f"{manager} run {name}",
                description=script_description(name, command),
                call_entry=f"{manager} run {name}",
                evidence=truncate(command, 140),
                path=str(path),
            )
        )
    return results


def script_description(name: str, command: str) -> str:
    haystack = f"{name} {command}".lower()
    if any(token in haystack for token in ["test", "vitest", "jest", "playwright", "cypress"]):
        return "项目测试入口"
    if any(token in haystack for token in ["build", "compile"]):
        return "项目构建入口"
    if any(token in haystack for token in ["dev", "serve", "start"]):
        return "本地开发服务入口"
    if any(token in haystack for token in ["lint", "eslint", "ruff", "check"]):
        return "项目检查或格式规范入口"
    if any(token in haystack for token in ["deploy", "publish"]):
        return "项目部署或发布入口"
    return "项目脚本入口"


def scan_makefile(root: Path) -> list[dict[str, Any]]:
    for filename in ["Makefile", "makefile"]:
        path = root / filename
        if path.exists():
            break
    else:
        return []
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in read_text(path).splitlines():
        if line.startswith("\t") or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?![=])", line)
        if not match:
            continue
        target = match.group(1)
        if target.startswith(".") or target in seen:
            continue
        seen.add(target)
        results.append(
            make_item(
                item_id=f"project:make:{target}",
                kind="project_script",
                label=f"make {target}",
                description="Makefile 项目入口",
                call_entry=f"make {target}",
                evidence="Makefile target",
                path=str(path),
            )
        )
    return results


def scan_justfile(root: Path) -> list[dict[str, Any]]:
    for filename in ["justfile", "Justfile"]:
        path = root / filename
        if path.exists():
            break
    else:
        return []
    results: list[dict[str, Any]] = []
    for line in read_text(path).splitlines():
        if line.startswith((" ", "\t", "#")):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\s+[^:]*)?:", line)
        if not match:
            continue
        name = match.group(1)
        results.append(
            make_item(
                item_id=f"project:just:{name}",
                kind="project_script",
                label=f"just {name}",
                description="justfile 项目入口",
                call_entry=f"just {name}",
                evidence="just recipe",
                path=str(path),
            )
        )
    return results


def scan_taskfile(root: Path) -> list[dict[str, Any]]:
    for filename in ["Taskfile.yml", "Taskfile.yaml"]:
        path = root / filename
        if path.exists():
            break
    else:
        return []
    lines = read_text(path).splitlines()
    in_tasks = False
    results: list[dict[str, Any]] = []
    for line in lines:
        if re.match(r"^tasks:\s*$", line):
            in_tasks = True
            continue
        if in_tasks and re.match(r"^\S", line) and not line.startswith("tasks:"):
            break
        match = re.match(r"^\s{2}([A-Za-z0-9_.-]+):\s*$", line)
        if not in_tasks or not match:
            continue
        name = match.group(1)
        results.append(
            make_item(
                item_id=f"project:task:{name}",
                kind="project_script",
                label=f"task {name}",
                description="Taskfile 项目入口",
                call_entry=f"task {name}",
                evidence="Taskfile task",
                path=str(path),
            )
        )
    return results


def scan_pyproject(root: Path) -> list[dict[str, Any]]:
    path = root / "pyproject.toml"
    if not path.exists():
        return []
    text = read_text(path)
    results = [
        make_item(
            item_id="project:python-env",
            kind="project_environment",
            label="Python project",
            description="Python 项目环境入口",
            call_entry="优先检查 pyproject.toml；按项目工具使用 uv / python -m pip / poetry",
            evidence="pyproject.toml exists",
            path=str(path),
        )
    ]
    section = ""
    for line in text.splitlines():
        section_match = re.match(r"^\[([^\]]+)\]\s*$", line.strip())
        if section_match:
            section = section_match.group(1)
            continue
        if section in {"project.scripts", "tool.poetry.scripts"}:
            match = re.match(r"^([A-Za-z0-9_.-]+)\s*=", line.strip())
            if match:
                name = match.group(1)
                results.append(
                    make_item(
                        item_id=f"project:python-script:{name}",
                        kind="project_script",
                        label=name,
                        description="Python 项目脚本入口",
                        call_entry=f"python/uv/poetry 调用脚本：{name}",
                        evidence=f"[{section}]",
                        path=str(path),
                    )
                )
    tool_hints = {
        "tool.pytest": ("pytest", "项目测试入口"),
        "tool.ruff": ("ruff check .", "Python lint/格式检查入口"),
        "tool.mypy": ("mypy .", "Python 类型检查入口"),
        "tool.black": ("black .", "Python 格式化入口"),
    }
    for section_name, (entry, description) in tool_hints.items():
        if f"[{section_name}" in text:
            results.append(
                make_item(
                    item_id=f"project:tool:{section_name}",
                    kind="project_script",
                    label=entry,
                    description=description,
                    call_entry=entry,
                    evidence=f"{section_name} config exists",
                    path=str(path),
                )
            )
    return results


def scan_compose(root: Path) -> list[dict[str, Any]]:
    candidates = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
    path = next((root / name for name in candidates if (root / name).exists()), None)
    if not path:
        return []
    results = [
        make_item(
            item_id="project:compose",
            kind="project_service",
            label="Docker Compose",
            description="项目容器服务入口",
            call_entry=f"docker compose -f {path.name} up",
            evidence="compose file exists",
            path=str(path),
            privacy_level="medium",
        )
    ]
    text = read_text(path)
    in_services = False
    for line in text.splitlines():
        if re.match(r"^services:\s*$", line):
            in_services = True
            continue
        if in_services and re.match(r"^\S", line) and not line.startswith("services:"):
            break
        match = re.match(r"^\s{2}([A-Za-z0-9_.-]+):\s*$", line)
        if not in_services or not match:
            continue
        name = match.group(1)
        results.append(
            make_item(
                item_id=f"project:compose-service:{name}",
                kind="project_service",
                label=f"compose service: {name}",
                description="项目 Docker Compose 服务",
                call_entry=f"docker compose -f {path.name} up {name}",
                evidence="compose service",
                path=str(path),
                privacy_level="medium",
            )
        )
    return results


def scan_tool_dirs(root: Path, max_items: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    allowed_suffixes = {".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".rb"}
    for dirname in ["scripts", "tools", "bin"]:
        folder = root / dirname
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if len(results) >= max_items:
                return results
            if not path.is_file() or path.name.startswith("."):
                continue
            relative = path.relative_to(root)
            executable = os.access(path, os.X_OK)
            if not executable and path.suffix not in allowed_suffixes:
                continue
            call_entry = str(relative)
            if path.suffix == ".py":
                call_entry = f"python {relative}"
            elif path.suffix in {".js", ".mjs", ".cjs"}:
                call_entry = f"node {relative}"
            elif path.suffix in {".sh", ""}:
                call_entry = f"./{relative}"
            results.append(
                make_item(
                    item_id=f"project:file-tool:{relative}",
                    kind="project_tool",
                    label=str(relative),
                    description="项目内可调用脚本或工具",
                    call_entry=call_entry,
                    evidence="project tool file",
                    path=str(path),
                )
            )
    return results


def scan_environment_files(root: Path) -> list[dict[str, Any]]:
    files = {
        "requirements.txt": ("Python requirements", "python -m pip install -r requirements.txt"),
        "uv.lock": ("uv Python lockfile", "uv sync"),
        "poetry.lock": ("Poetry lockfile", "poetry install"),
        "Cargo.toml": ("Rust project", "cargo build / cargo test"),
        "go.mod": ("Go project", "go test ./... / go run ."),
        "Gemfile": ("Ruby project", "bundle install"),
        "Dockerfile": ("Docker image build", "docker build ."),
    }
    results: list[dict[str, Any]] = []
    for filename, (label, entry) in files.items():
        path = root / filename
        if not path.exists():
            continue
        results.append(
            make_item(
                item_id=f"project:env-file:{filename}",
                kind="project_environment",
                label=label,
                description="项目环境或运行入口",
                call_entry=entry,
                evidence=f"{filename} exists",
                path=str(path),
            )
        )
    for filename in [".env", ".env.local"]:
        path = root / filename
        if not path.exists():
            continue
        results.append(
            make_item(
                item_id=f"project:secret-env:{filename}",
                kind="project_guardrail",
                label=f"{filename} exists",
                description="项目可能需要环境变量；不要读取或输出密钥内容",
                call_entry="只确认文件存在；需要变量名时优先看 .env.example 或项目文档",
                evidence="secret env file exists; content not read",
                path=str(path),
                privacy_level="high",
            )
        )
    for filename in [".env.example", ".env.sample"]:
        path = root / filename
        if path.exists():
            results.append(
                make_item(
                    item_id=f"project:env-template:{filename}",
                    kind="project_environment",
                    label=f"{filename}",
                    description="环境变量模板，可用于判断项目需要哪些配置",
                    call_entry=f"读取 {filename} 的变量名；不要填充真实密钥",
                    evidence="env template exists",
                    path=str(path),
                    privacy_level="medium",
                )
            )
    return results


def scan_project(root: Path, max_tools: int) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"project path is not a directory: {root}")
    items: list[dict[str, Any]] = []
    for scanner in [
        scan_package_json,
        scan_makefile,
        scan_justfile,
        scan_taskfile,
        scan_pyproject,
        scan_compose,
        scan_environment_files,
    ]:
        items.extend(scanner(root))
    items.extend(scan_tool_dirs(root, max_tools))
    items.sort(key=lambda item: (item["kind"], item["label"], item["id"]))
    return {
        "schema_version": "0.1",
        "generated_at": now_iso(),
        "project_path": str(root),
        "project_name": root.name,
        "positioning": "Project-local callable entry points for AI agents. It records entry points and status, not project content.",
        "counts": {
            "total": len(items),
            "by_kind": count_by(items, "kind"),
            "by_privacy": count_by(items, "privacy_level"),
        },
        "privacy_policy": "Only entry points and file existence are recorded. Secret file contents, browser data, tokens and business data are not scanned.",
        "items": items,
    }


def count_by(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key, ""))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def safe_cell(value: Any) -> str:
    return str(value or "-").replace("|", "/").replace("\n", " ").strip()


def render_markdown(payload: dict[str, Any], json_path: Path) -> str:
    lines = [
        f"# Project Capability Map: {payload['project_name']}",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"project_path: `{payload['project_path']}`",
        f"items: `{payload['counts']['total']}`",
        f"details: `{json_path.name}`",
        "",
        "这份地图只记录 AI 可调用的项目入口，不记录业务内容、密钥内容或浏览器数据。",
        "",
        "| name | type | use | entry | privacy | evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in payload["items"]:
        lines.append(
            "| {name} | {kind} | {use} | {entry} | {privacy} | {evidence} |".format(
                name=safe_cell(item["label"]),
                kind=safe_cell(item["kind"]),
                use=safe_cell(truncate(item["description"], 64)),
                entry=safe_cell(truncate(item["call_entry"], 72)),
                privacy=safe_cell(item["privacy_level"]),
                evidence=safe_cell(truncate(item["evidence"], 72)),
            )
        )
    if not payload["items"]:
        lines.append("| - | - | 未发现明确项目级可调用入口 | - | - | - |")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(payload: dict[str, Any], slug: str) -> tuple[Path, Path]:
    PROJECT_CAPABILITIES_DIR.mkdir(parents=True, exist_ok=True)
    json_path = PROJECT_CAPABILITIES_DIR / f"{slug}.json"
    md_path = PROJECT_CAPABILITIES_DIR / f"{slug}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload, json_path), encoding="utf-8")
    return md_path, json_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan project-local AI-callable capabilities")
    parser.add_argument("--path", default=os.getcwd(), help="project directory to scan")
    parser.add_argument("--max-tools", type=int, default=80, help="maximum files from scripts/tools/bin")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.path)
    payload = scan_project(root, args.max_tools)
    md_path, json_path = write_outputs(payload, safe_slug(root))
    print(f"project_map={md_path}")
    print(f"project_inventory={json_path}")
    print(f"items={payload['counts']['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
