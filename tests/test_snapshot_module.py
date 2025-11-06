from __future__ import annotations

import json
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

    def raise_for_status(self) -> None:  # pragma: no cover - status_code controls behaviour
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP error {self.status_code}")


@pytest.fixture()
def snapshot_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
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
    monkeypatch.setattr(snapshot.helpers, "load_config", lambda: config)
    monkeypatch.setattr(snapshot.helpers, "timestamp_for_filename", lambda tz=None: "20240101T000000Z")

    return {"ARTIFACT_ROOT": str(artifact_root)}


def test_fetch_jql_results_persists_snapshot(snapshot_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
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
    monkeypatch.setattr(snapshot, "request_with_retry", lambda *a, **k: _DummyResponse(payload))

    issues = snapshot.fetch_jql_results("1.0.0")

    assert len(issues) == 1
    assert issues[0]["key"] == "ABC-1"

    snapshot_path = snapshot.helpers.artifact_path("snapshots", "snapshot_20240101T000000Z.json")
    assert snapshot_path.exists()
    written = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert written["fixVersion"] == "1.0.0"
    assert written["issues"][0]["deployment_notes"] == "Notes"


def test_fetch_jql_results_uses_mock_data_on_failure(snapshot_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snapshot, "get_jira_session", lambda: object())
    def failing_request(*_: object, **__: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(snapshot, "request_with_retry", failing_request)

    issues = snapshot.fetch_jql_results("9.9.9")

    assert issues  # falls back to bundled mock payload
    assert all(issue["fixVersions"] == ["9.9.9"] for issue in issues)

    snapshot_path = snapshot.helpers.artifact_path("snapshots", "snapshot_20240101T000000Z.json")
    assert snapshot_path.exists()
