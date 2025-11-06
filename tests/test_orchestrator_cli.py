"""Tests for the Slice 05 CLI orchestrator."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import pytest

from modules.orchestrator.cli import Orchestrator
from modules.orchestrator.versioning import VersionManager
from modules.utils import helpers


@pytest.fixture()
def orchestrator_env(tmp_path, monkeypatch):
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("JIRA_CLIENT_ID", "client")
    monkeypatch.setenv("JIRA_SECRET", "super-secret")
    monkeypatch.setenv("SSL_CERT_PATH", "/tmp/cert.pem")
    monkeypatch.setenv("FIX_VERSION", "1.2.3")
    return {
        "ARTIFACT_ROOT": str(artifact_root),
        "JIRA_CLIENT_ID": "client",
        "JIRA_SECRET": "super-secret",
        "SSL_CERT_PATH": "/tmp/cert.pem",
        "FIX_VERSION": "1.2.3",
    }


def test_analyze_creates_usage_artifact_and_progress(orchestrator_env):
    orchestrator = Orchestrator(env=orchestrator_env)
    usage_path = orchestrator.analyze()

    assert usage_path.exists()
    content = usage_path.read_text(encoding="utf-8")
    assert "CLI Orchestrator Usage" in content

    progress_data = helpers.read_json(orchestrator._progress_path)  # noqa: SLF001 - test scope
    stages = [event["stage"] for event in progress_data["events"]]
    assert "analyze" in stages


def test_execute_records_progress_and_release_notes(tmp_path, orchestrator_env):
    delta_path = tmp_path / "delta.json"
    delta_path.write_text("{}", encoding="utf-8")

    def fake_snapshot(fix_version: str):
        return [{"id": 1, "fixVersion": fix_version}]

    def fake_delta():
        return delta_path, {"new": [1], "still_open": []}

    def fake_report(path: Path) -> Path:
        report = tmp_path / "report.md"
        report.write_text("# report", encoding="utf-8")
        return report

    version_manager = VersionManager(artifact_root=helpers.artifact_path("05"))
    orchestrator = Orchestrator(
        fix_version="1.2.3",
        env=orchestrator_env,
        snapshot_fetcher=fake_snapshot,
        delta_generator=fake_delta,
        report_builder=fake_report,
        version_manager=version_manager,
    )

    plan = orchestrator.execute()
    assert plan.version == "0.0.1"
    assert plan.notes_path.exists()

    progress_data = helpers.read_json(orchestrator._progress_path)  # noqa: SLF001 - test scope
    stages = [event["stage"] for event in progress_data["events"]]
    assert stages[0] == "execute:start"
    assert "execute:complete" in stages


def test_release_notes_mask_secrets(monkeypatch, tmp_path):
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("JIRA_SECRET", "super-secret")
    monkeypatch.setenv("SSL_CERT_PATH", "/tmp/cert.pem")

    manager = VersionManager(artifact_root=helpers.artifact_path("05"))
    plan = manager.plan_release(
        release_type="minor",
        current_tag="1.2.3",
        fix_version="1.2.3",
        highlights=["super-secret leaked"],
        metadata={"credential": "super-secret"},
        timestamp="20240101T010101Z",
    )

    notes = plan.notes
    assert "super-secret" not in notes
    assert "***" in notes
    assert plan.notes_path.name == "version_tag_notes_20240101T010101Z.md"

def test_analyze_requires_core_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    env = {"ARTIFACT_ROOT": str(tmp_path / "artifacts")}
    orchestrator = Orchestrator(env=env, fix_version="2.0.0")

    with pytest.raises(EnvironmentError) as exc_info:
        orchestrator.analyze()

    message = str(exc_info.value)
    assert "JIRA_CLIENT_ID" in message
    assert "JIRA_SECRET" in message
