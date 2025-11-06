#!/usr/bin/env python3
"""Utility for adding slice definitions to a GitHub Project board via gh CLI."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Set

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "github_project.yml"
SLICES_DIR = REPO_ROOT / "slices"
LOG_DIR = REPO_ROOT / "logs"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Missing configuration file: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh) or {}
    missing = [key for key in ("project_owner", "project_number") if key not in config]
    if missing:
        raise KeyError(f"Missing required config keys: {', '.join(missing)}")
    return config


def resolve_labels(raw_labels: Iterable) -> List[str]:
    labels: List[str] = []
    for item in raw_labels or []:
        if isinstance(item, str):
            labels.append(item)
        elif isinstance(item, dict):
            for key, value in item.items():
                labels.append(f"{key}:{value}")
        else:
            labels.append(str(item))
    return labels


def fetch_existing_titles(owner: str, project_number: int) -> Set[str]:
    cmd = [
        "gh",
        "project",
        "item-list",
        str(project_number),
        "--owner",
        owner,
        "--format",
        "json",
    ]
    try:
        logging.debug("Fetching existing project items with command: %s", " ".join(cmd))
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        logging.warning("gh CLI not found: %s", exc)
        return set()
    except subprocess.CalledProcessError as exc:
        logging.warning("Unable to list existing project items (return code %s): %s", exc.returncode, exc.stderr.strip())
        return set()

    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        logging.warning("Failed to parse project item list: %s", exc)
        return set()

    titles = {
        item.get("title")
        for item in data
        if isinstance(item, dict) and item.get("title")
    }
    return titles


def build_body(branch: str, labels: List[str]) -> str:
    lines = [
        "Phase: Build",
        f"Branch: {branch}",
        "Status: Ready",
    ]
    if labels:
        lines.append("Labels: " + ", ".join(labels))
    return "\n".join(lines)


def add_slice(owner: str, project_number: int, slice_path: Path, labels: List[str], existing_titles: Set[str]) -> str:
    with slice_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    slice_id = str(data.get("id", "")).zfill(2)
    title = data.get("title", "Unnamed Slice")
    branch = data.get("branch", "")
    project_title = f"Slice {slice_id} – {title}"

    if project_title in existing_titles:
        message = f"⚠️  Skipping {project_title}: already exists on project board."
        logging.info(message)
        return message

    body = build_body(branch, labels)
    cmd = [
        "gh",
        "project",
        "item-add",
        str(project_number),
        "--owner",
        owner,
        "--title",
        project_title,
        "--body",
        body,
    ]

    logging.debug("Running command: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
        message = f"✅ Added {project_title}"
        existing_titles.add(project_title)
        logging.info(message)
        return message
    except FileNotFoundError:
        message = "❌ gh CLI not found; unable to add project items."
        logging.error(message)
        return message
    except subprocess.CalledProcessError as exc:
        message = f"⚠️ Failed to add {project_title}: {exc}"
        logging.warning(message)
        return message


def discover_slice_files(selection: List[str] | None) -> List[Path]:
    all_paths = sorted(SLICES_DIR.glob("slice_*.yml"))
    if not selection:
        return all_paths

    resolved: List[Path] = []
    for key in selection:
        clean = key.strip().lower()
        clean = clean.replace("slice_", "").replace("slice", "")
        clean = clean.replace("-", "_")
        clean = clean.strip("_")
        if not clean:
            continue
        slice_id = clean.zfill(2)
        pattern = f"slice_{slice_id}_*.yml"
        matches = [path for path in all_paths if path.name.startswith(f"slice_{slice_id}_")]
        if matches:
            resolved.extend(matches)
        else:
            logging.warning("No slice definition found for identifier '%s'", key)
    # Deduplicate while preserving order based on all_paths order
    ordered: List[Path] = []
    seen = set()
    for path in all_paths:
        if selection and path not in resolved:
            continue
        if path in seen:
            continue
        ordered.append(path)
        seen.add(path)
    return ordered


def configure_logging() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    log_path = LOG_DIR / f"add_to_project_{timestamp}.log"

    handlers = [logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, mode="a", encoding="utf-8")]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )
    logging.debug("Logging configured. Output file: %s", log_path)
    return log_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add slice definitions to GitHub Project board")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Process all slice definitions (default)")
    group.add_argument("--slice", action="append", dest="slices", help="Process a specific slice id (e.g., 03). Can be repeated.")
    return parser.parse_args()


def main() -> int:
    log_path = configure_logging()
    try:
        config = load_config()
    except (FileNotFoundError, KeyError) as exc:
        logging.error("Configuration error: %s", exc)
        return 1

    owner = str(config["project_owner"]).strip()
    project_number = int(config["project_number"])
    labels = resolve_labels(config.get("default_labels", []))

    args = parse_args()
    slice_paths = discover_slice_files(args.slices if getattr(args, "slices", None) else None)
    if not slice_paths:
        logging.warning("No slice files found to process.")
        print("⚠️ No slices processed.")
        return 0

    existing_titles = fetch_existing_titles(owner, project_number)

    for path in slice_paths:
        add_slice(owner, project_number, path, labels, existing_titles)

    print("✅ All slices processed.")
    logging.info("Completed slice processing. Log file: %s", log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
