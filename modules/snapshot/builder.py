"""Snapshot builder utilities for Jira API and CSV fallback inputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from modules.utils import helpers
from modules.utils.logger import get_logger

LOGGER = get_logger(__name__)


@dataclass
class SnapshotResult:
    """Represents the outcome of building a snapshot artifact."""

    issues: list[Dict[str, Any]]
    path: Path
    metadata: Dict[str, Any]


def normalise_issues(issues: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    """Return a list of issues filtered through schema validation."""

    from src.validation import filter_valid_issues  # Local import to avoid cycles

    return filter_valid_issues(list(issues))


def build_snapshot(
    *,
    fix_version: str,
    issues: Iterable[Mapping[str, Any]],
    mode: str,
    csv_file: str | None,
    tz: str | None,
    metadata: Dict[str, Any] | None = None,
) -> SnapshotResult:
    """Persist a snapshot to disk and return rich metadata about the run."""

    config = helpers.load_config()
    snapshot_dir_setting = config["paths"].get("snapshot_dir", "snapshots")
    snapshot_dir = Path(snapshot_dir_setting)
    if not snapshot_dir.is_absolute():
        snapshot_dir = helpers.artifact_path(snapshot_dir_setting)
    helpers.ensure_directory(snapshot_dir)

    timestamp = helpers.timestamp_for_filename(tz)
    snapshot_path = snapshot_dir / f"snapshot_{timestamp}.json"

    validated_issues = normalise_issues(issues)

    run_metadata = metadata.copy() if metadata else {}
    run_metadata.update(
        {
            "source": mode,
            "csv_file": csv_file,
            "timestamp": helpers.current_timestamp(tz).isoformat(),
            "total_issues": len(validated_issues),
        }
    )

    payload = {
        "fixVersion": fix_version,
        "issues": validated_issues,
        "metadata": run_metadata,
    }
    helpers.write_json_safe(payload, snapshot_path)
    LOGGER.info(
        "Snapshot saved to %s (mode=%s, issues=%s)",
        snapshot_path,
        mode,
        len(validated_issues),
        extra={"mode": mode},
    )
    return SnapshotResult(validated_issues, snapshot_path, run_metadata)
