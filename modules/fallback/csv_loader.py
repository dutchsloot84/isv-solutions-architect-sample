"""Utilities for loading Jira issue exports from CSV during OAuth fallback."""

from __future__ import annotations

import csv
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, List, Sequence

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
    "Deployment notes",
}


@dataclass(slots=True)
class CsvLoadResult:
    """Structured result describing a CSV import operation."""

    path: Path
    issues: list[dict[str, object]]
    fieldnames: Sequence[str]
    row_count: int
    checksum: str
    duration_seconds: float


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


def _calculate_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as raw:
        for chunk in iter(lambda: raw.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_csv(csv_path: str) -> CsvLoadResult:
    """Load Jira issues from a CSV export and capture ingestion metadata."""

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV fallback file not found: {path}")

    LOGGER.info("Loading fallback CSV from %s", path)
    checksum = _calculate_checksum(path)
    start = perf_counter()
    issues: list[dict[str, object]] = []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = tuple(reader.fieldnames or [])
            _warn_if_headers_missing(headers)
            for row in reader:
                issue = {
                    "key": row.get("Issue key") or row.get("Key"),
                    "summary": row.get("Summary"),
                    "status": row.get("Status"),
                    "assignee": row.get("Assignee"),
                    "fixVersions": _normalise_fix_versions(row.get("Fix Version/s")),
                    "deployment_notes": row.get("Deployment notes"),
                    "updated": row.get("Updated"),
                    "created": row.get("Created"),
                }
                issues.append(issue)
    except UnicodeDecodeError as error:
        raise UnicodeDecodeError(
            error.encoding or "utf-8",
            error.object,
            error.start,
            error.end,
            f"Unable to decode CSV at {path}: {error.reason}",
        ) from error

    duration = perf_counter() - start
    LOGGER.info(
        "✅ Loaded %s issues from CSV fallback.",
        len(issues),
        extra={
            "csv_path": str(path),
            "csv_rows": len(issues),
            "csv_checksum": checksum,
            "duration_seconds": round(duration, 4),
        },
    )
    return CsvLoadResult(
        path=path,
        issues=issues,
        fieldnames=headers,
        row_count=len(issues),
        checksum=checksum,
        duration_seconds=duration,
    )


def load_csv_as_issues(csv_path: str) -> list[dict[str, object]]:
    """Compatibility wrapper returning only the issue list for legacy callers."""

    return load_csv(csv_path).issues


__all__ = ["CsvLoadResult", "load_csv", "load_csv_as_issues"]
