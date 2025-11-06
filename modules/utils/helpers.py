"""Utility helpers for configuration loading, timestamps, and serialization."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def project_root() -> Path:
    """Return the root directory for the release snapshot manager project."""
    return Path(__file__).resolve().parents[2]


def module_root() -> Path:
    """Return the module root directory inside the repository."""
    return Path(__file__).resolve().parents[1]


def config_path() -> Path:
    """Return the default configuration file path."""
    return project_root() / "configs" / "config.yaml"


def artifact_root() -> Path:
    """Return the base artifact directory, defaulting to the project data folder."""

    root = os.getenv("ARTIFACT_ROOT")
    if root:
        path = Path(root).expanduser().resolve()
    else:
        path = project_root() / "data"
    ensure_directory(path)
    return path


def artifact_path(*parts: str | os.PathLike[str]) -> Path:
    """Construct a path rooted at the artifact directory."""

    return artifact_root().joinpath(*parts)


def ssl_verify_path() -> Optional[Path]:
    """Return the SSL certificate bundle path from environment variables."""

    cert_path = os.getenv("SSL_CERT_PATH") or os.getenv("REQUESTS_CA_BUNDLE")
    if not cert_path:
        return None

    resolved = resolve_path(cert_path)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(resolved))
    return resolved


def load_config(override_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load configuration using the centralized loader module."""

    from modules.config.loader import load_config as _load_config

    return _load_config(override_path)


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


def latest_snapshot_files(
    snapshot_dir: Path | str, limit: int = 2
) -> list[Path]:
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
