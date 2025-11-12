from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

import main
from modules import snapshot


def _snapshot_result(csv_path: Path) -> snapshot.SnapshotResult:
    metadata: Dict[str, Any] = {
        "source": "csv_fallback",
        "csv_file": str(csv_path),
        "csv_row_count": 1,
        "csv_checksum": "checksum",
        "csv_fieldnames": ["Issue key", "Summary"],
        "csv_duration_seconds": 0.25,
    }
    return snapshot.SnapshotResult(
        issues=[{"key": "ABC-1", "summary": "Example"}],
        path=csv_path.parent / "snapshot.json",
        metadata=metadata,
    )


@pytest.fixture()
def fixed_now() -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_capture_snapshot_records_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
) -> None:
    csv_path = tmp_path / "fallback.csv"
    csv_path.write_text("Issue key,Summary\nABC-1,Example\n", encoding="utf-8")

    config = {
        "paths": {
            "logs_dir": tmp_path / "logs",
            "reports_dir": tmp_path / "reports",
        }
    }
    logger = main.get_logger("test_capture_snapshot_records_diagnostics")

    csv_path_obj = csv_path

    def fake_capture(fix_version: str, *, tz=None, csv_path: str | None = None):
        if csv_path is None:
            raise snapshot.OAuthUnavailableError("denied", reason="AccessDenied")
        assert csv_path == str(csv_path_obj)
        return _snapshot_result(csv_path_obj)

    monkeypatch.setattr(main, "_prompt_for_csv", lambda *_: csv_path_obj)
    monkeypatch.setattr(main.snapshot, "capture_snapshot", fake_capture)
    monkeypatch.setattr(main.helpers, "current_timestamp", lambda tz=None: fixed_now)

    result = main._capture_snapshot(
        fix_version="1.0.0",
        tz="UTC",
        logger=logger,
        config=config,
        csv_override=None,
    )

    diagnostics_path = Path(result.metadata["oauth_diagnostics"])
    audit_path = Path(result.metadata["audit_report"])

    assert diagnostics_path.exists()
    assert audit_path.exists()

    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert diagnostics["trigger"] == "oauth_unavailable"
    assert diagnostics["csv_row_count"] == 1

    audit = audit_path.read_text(encoding="utf-8")
    assert "CSV file" in audit
    assert "AccessDenied" in audit


def test_capture_snapshot_manual_override_records_trigger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixed_now: datetime
) -> None:
    csv_path = tmp_path / "manual.csv"
    csv_path.write_text("Issue key,Summary\nABC-2,Manual\n", encoding="utf-8")

    config = {
        "paths": {
            "logs_dir": tmp_path / "logs",
            "reports_dir": tmp_path / "reports",
        }
    }
    logger = main.get_logger("test_capture_snapshot_manual_override")

    def fake_capture(fix_version: str, *, tz=None, csv_path: str | None = None):
        assert csv_path == str(csv_path_param)
        return _snapshot_result(Path(csv_path_param))

    csv_path_param = csv_path
    monkeypatch.setattr(main.snapshot, "capture_snapshot", fake_capture)
    monkeypatch.setattr(main.helpers, "current_timestamp", lambda tz=None: fixed_now)

    result = main._capture_snapshot(
        fix_version="2.0.0",
        tz="UTC",
        logger=logger,
        config=config,
        csv_override=csv_path,
    )

    diagnostics_path = Path(result.metadata["oauth_diagnostics"])
    diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    assert diagnostics["trigger"] == "manual_override"
