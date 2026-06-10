#!/usr/bin/env python3
"""Refresh Capability Hub scan data and the layered AI capability map."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PROJECT_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = PROJECT_ROOT
RESULTS_DIR = PROJECT_ROOT / "output"

STEPS = [
    ("扫描本机能力", SCRIPTS_DIR / "scan_capabilities.py", []),
]

RETIRED_AI_OUTPUTS = [
    RESULTS_DIR / "ai-capability-map.md",
    RESULTS_DIR / "ai-capability-inbox.md",
    RESULTS_DIR / "capability-reading-index.json",
    RESULTS_DIR / "skill-name-map.md",
]


def run_step(label: str, script: Path, extra_args: list[str]) -> None:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    print(f"==> {label}")
    subprocess.run([sys.executable, str(script), *extra_args], cwd=PROJECT_ROOT, env=env, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh Capability Hub outputs")
    parser.add_argument(
        "--mode",
        choices=["full", "refresh"],
        default="refresh",
        help="full builds the baseline; refresh updates lightweight changing sources",
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
    steps = [
        *STEPS,
        ("扫描整机能力感知层", SCRIPTS_DIR / "scan_machine_capabilities.py", ["--mode", args.mode, "--format", args.format]),
    ]
    for label, script, extra_args in steps:
        run_step(label, script, extra_args)
    for path in RETIRED_AI_OUTPUTS:
        if path.exists():
            path.unlink()
    print("OK: Capability Hub synced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
