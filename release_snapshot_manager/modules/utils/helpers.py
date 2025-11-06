"""Utility helpers for configuration loading, timestamps, and serialization."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    import json as _json

    class _SimpleYAML:  # type: ignore[misc]
        """Minimal YAML parser fallback that supports JSON-formatted content."""

        @staticmethod
        def safe_load(stream):  # type: ignore[override]
            if hasattr(stream, "read"):
                return _json.loads(stream.read())
            return _json.loads(stream)

    yaml = _SimpleYAML()


def project_root() -> Path:
    """Return the root directory for the release snapshot manager project."""
    return Path(__file__).resolve().parents[3]


def module_root() -> Path:
    """Return the module root directory inside the repository."""
    return Path(__file__).resolve().parents[2]


def config_path() -> Path:
    """Return the default configuration file path."""
    return module_root() / "configs" / "config.yaml"


def load_config(override_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load YAML configuration and override with environment variables when present."""
    config_file = Path(override_path) if override_path else config_path()
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found at {config_file}")

    with config_file.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream) or {}

    overrides = {
        "jira": {
            "base_url": os.getenv("JIRA_BASE_URL"),
            "auth_url": os.getenv("JIRA_AUTH_URL"),
            "token_url": os.getenv("JIRA_TOKEN_URL"),
            "api_scope": os.getenv("JIRA_API_SCOPE"),
            "token_path": os.getenv("JIRA_TOKEN_PATH"),
            "redirect_uri": os.getenv("JIRA_REDIRECT_URI"),
        },
        "paths": {
            "snapshot_dir": os.getenv("SNAPSHOT_DIR"),
            "logs_dir": os.getenv("LOGS_DIR"),
            "reports_dir": os.getenv("REPORTS_DIR"),
            "prompts_dir": os.getenv("PROMPTS_DIR"),
        },
    }

    for section, values in overrides.items():
        if section not in config:
            config[section] = {}
        for key, value in values.items():
            if value:
                config[section][key] = value

    return config


def ensure_directory(path: Path | str) -> Path:
    """Create a directory if it does not exist and return the path."""
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def current_timestamp(tz: Optional[str] = None) -> datetime:
    """Return a timezone-aware timestamp."""
    if tz:
        try:
            from zoneinfo import ZoneInfo

            return datetime.now(tz=ZoneInfo(tz))
        except Exception:  # pragma: no cover
            pass
    return datetime.now(timezone.utc)


def timestamp_for_filename(tz: Optional[str] = None) -> str:
    """Return a timestamp string safe for filenames."""
    return current_timestamp(tz).strftime("%Y%m%dT%H%M%SZ")


def write_json_safe(data: Any, path: Path | str) -> Path:
    """Write JSON data to disk using UTF-8 encoding."""
    file_path = Path(path)
    ensure_directory(file_path.parent)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
    return file_path


def read_json(path: Path | str) -> Dict[str, Any]:
    """Read JSON content from disk."""
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def latest_snapshot_files(snapshot_dir: Path | str, limit: int = 2) -> list[Path]:
    """Return the most recent snapshot files sorted newest-first."""
    directory = Path(snapshot_dir)
    snapshots = sorted(directory.glob("snapshot_*.json"), reverse=True)
    return snapshots[:limit]


def resolve_path(path: Path | str) -> Path:
    """Expand user paths and return an absolute Path."""
    return Path(path).expanduser().resolve()


def append_csv_row(path: Path | str, row: Dict[str, Any]) -> None:
    """Append a CSV row to the provided file path."""
    import csv

    file_path = Path(path)
    ensure_directory(file_path.parent)
    exists = file_path.exists()

    with file_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=row.keys())
        if not exists:
            writer.writeheader()
        writer.writerow(row)
