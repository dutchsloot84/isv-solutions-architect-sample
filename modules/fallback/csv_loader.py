"""Utilities for loading Jira issue exports from CSV during OAuth fallback."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, Iterable, List

LOGGER = logging.getLogger(__name__)


EXPECTED_HEADERS = {
    "Issue key",
    "Key",
    "Summary",
    "Status",
    "Assignee",
    "Fix Version/s",
    "Updated",
    "Created",
}


def _normalise_fix_versions(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [segment.strip() for segment in raw.split(",") if segment.strip()]


def _warn_if_headers_missing(fieldnames: Iterable[str]) -> None:
    missing = sorted(EXPECTED_HEADERS - set(fieldnames or []))
    if missing:
        LOGGER.warning(
            "CSV fallback import missing expected columns: %s",
            ", ".join(missing),
        )


def load_csv_as_issues(csv_path: str) -> List[Dict[str, object]]:
    """Load Jira issues from a CSV export for fallback snapshot generation."""

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV fallback file not found: {path}")

    LOGGER.info("Loading fallback CSV from %s", path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        _warn_if_headers_missing(reader.fieldnames or [])
        issues: List[Dict[str, object]] = []
        for row in reader:
            issue = {
                "key": row.get("Issue key") or row.get("Key"),
                "summary": row.get("Summary"),
                "status": row.get("Status"),
                "assignee": row.get("Assignee"),
                "fixVersions": _normalise_fix_versions(row.get("Fix Version/s")),
                "deployment_notes": None,
                "updated": row.get("Updated"),
                "created": row.get("Created"),
            }
            issues.append(issue)

    LOGGER.info("✅ Loaded %s issues from CSV fallback.", len(issues))
    return issues
