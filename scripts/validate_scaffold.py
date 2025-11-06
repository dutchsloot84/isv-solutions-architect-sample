#!/usr/bin/env python3
"""Validate Guard Phase scaffold files for basic structural integrity."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> None:
    with path.open("r", encoding="utf-8") as fh:
        json.load(fh)


def load_yaml(path: Path) -> None:
    with path.open("r", encoding="utf-8") as fh:
        yaml.safe_load(fh)


def expect_files(paths: Iterable[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required files:\n" + "\n".join(missing))


def validate_guard_phase() -> None:
    guard_json = REPO_ROOT / "prompts" / "MOP_guard_phase.json"
    active_json = REPO_ROOT / "prompts" / "MOP_active.json"

    load_json(guard_json)
    load_json(active_json)

    slice_paths = sorted((REPO_ROOT / "slices").glob("slice_*.yml"))
    for path in slice_paths:
        load_yaml(path)

    prompt_paths = sorted((REPO_ROOT / "prompts" / "slices").glob("[0-9][0-9]_*.md"))
    expect_files(prompt_paths)


def main() -> int:
    try:
        validate_guard_phase()
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Validation failed: {exc}", file=sys.stderr)
        return 1
    print("✅ Guard Phase scaffold validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
