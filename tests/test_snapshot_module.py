from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from modules import snapshot


class _DummyResponse:
    def __init__(self, payload: Dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Dict[str, Any]:
        return self._payload

    def raise_for_status(
        self,
    ) -> None:  # pragma: no cover - status_code controls behaviour
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP error {self.status_code}")


@pytest.fixture()
def snapshot_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("SSL_CERT_PATH", str(tmp_path / "corp.pem"))

    config: Dict[str, Any] = {
        "paths": {"snapshot_dir": "snapshots"},
        "jira": {
            "base_url": "https://example.atlassian.net",
            "jql_fields": [
                "key",
                "summary",
                "status",
                "fixVersions",
                "customfield_12345",
            ],
        },
        "project": {"deployment_notes_field": "customfield_12345"},
        "reporting": {"timezone": "UTC"},
    }
    fixed_now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(snapshot.helpers, "load_config", lambda: config)
    monkeypatch.setattr(snapshot.builder.helpers, "load_config", lambda: config)
    monkeypatch.setattr(
        snapshot.helpers, "timestamp_for_filename", lambda tz=None: "20240101T000000Z"
    )
    monkeypatch.setattr(
        snapshot.builder.helpers,
        "timestamp_for_filename",
        lambda tz=None: "20240101T000000Z",
    )
    monkeypatch.setattr(
        snapshot.helpers,
        "current_timestamp",
        lambda tz=None: fixed_now,
    )
    monkeypatch.setattr(
        snapshot.builder.helpers,
        "current_timestamp",
        lambda tz=None: fixed_now,
    )

    return {"ARTIFACT_ROOT": str(artifact_root)}


def test_fetch_jql_results_persists_snapshot(
    snapshot_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {
        "issues": [
            {
                "key": "ABC-1",
                "fields": {
                    "summary": "Demo",
                    "status": {"name": "In Progress"},
                    "fixVersions": [{"name": "1.0.0"}],
                    "customfield_12345": "Notes",
                },
            }
        ]
    }
    monkeypatch.setattr(snapshot, "get_jira_session", lambda: object())
    monkeypatch.setattr(
        snapshot, "request_with_retry", lambda *a, **k: _DummyResponse(payload)
    )

    result = snapshot.capture_snapshot("1.0.0")
    issues = result.issues

    assert len(issues) == 1
    assert issues[0]["key"] == "ABC-1"

    snapshot_path = snapshot.helpers.artifact_path(
        "snapshots", "snapshot_20240101T000000Z.json"
    )
    assert snapshot_path.exists()
    written = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert written["fixVersion"] == "1.0.0"
    assert written["issues"][0]["deployment_notes"] == "Notes"
    assert written["metadata"]["source"] == "jira_api"


def test_fetch_jql_results_uses_mock_data_on_failure(
    snapshot_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(snapshot, "get_jira_session", lambda: object())

    def failing_request(*_: object, **__: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(snapshot, "request_with_retry", failing_request)

    result = snapshot.capture_snapshot("9.9.9")
    issues = result.issues

    assert issues  # falls back to bundled mock payload
    assert all(issue["fixVersions"] == ["9.9.9"] for issue in issues)

    snapshot_path = snapshot.helpers.artifact_path(
        "snapshots", "snapshot_20240101T000000Z.json"
    )
    assert snapshot_path.exists()
    written = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert written["metadata"]["source"] == "jira_api"


def test_capture_snapshot_csv_fallback(
    snapshot_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csv_path = tmp_path / "export.csv"
    csv_path.write_text(
        "Issue key,Summary,Status,Assignee,Fix Version/s,Updated,Created\n"
        "ABC-3,CSV issue,In Progress,Ada Lovelace,1.0.0,,\n",
        encoding="utf-8",
    )

    result = snapshot.capture_snapshot("1.0.0", csv_path=str(csv_path))

    assert result.metadata["source"] == "csv_fallback"
    assert Path(result.metadata["csv_file"]).name == "export.csv"
    assert result.issues[0]["key"] == "ABC-3"

    snapshot_path = snapshot.helpers.artifact_path(
        "snapshots", "snapshot_20240101T000000Z.json"
    )
    written = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert written["metadata"]["source"] == "csv_fallback"
    assert written["metadata"]["csv_file"].endswith("export.csv")


def test_capture_snapshot_raises_when_oauth_unavailable(
    snapshot_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_runtime_error() -> None:
        raise RuntimeError("No OAuth token found. Run the authorize_jira flow first.")

    monkeypatch.setattr(snapshot, "get_jira_session", _raise_runtime_error)

    with pytest.raises(snapshot.OAuthUnavailableError):
        snapshot.capture_snapshot("1.0.0")
