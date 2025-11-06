"""Tests for the JSON logging factory."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from modules.logging import LoggerFactory, get_logger


def test_get_logger_emits_json(monkeypatch, capsys):
    monkeypatch.setenv("ACTIVE_SLICE_ID", "04")
    monkeypatch.setenv("MOP_PHASE", "build")
    logger = get_logger("release.test")

    logger.info("hello %s", "world", extra={"event": "config"})
    captured = capsys.readouterr().out.strip()
    data = json.loads(captured)

    assert data["message"] == "hello world"
    assert data["slice_id"] == "04"
    assert data["phase"] == "build"
    assert data["event"] == "config"


def test_logger_writes_to_artifact_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path))
    factory = LoggerFactory()
    logger = factory.get_logger("release.file", log_file=Path("logs") / "slice.log")
    logger.info("persist message")

    log_path = tmp_path / "logs" / "slice.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8").strip()
    assert json.loads(content)["message"] == "persist message"


def test_masking_applies_to_sensitive_values(monkeypatch, capsys):
    monkeypatch.setenv("JIRA_SECRET", "super-secret")
    factory = LoggerFactory()
    logger = factory.get_logger("release.masking")

    logger.warning("token=%s", "super-secret")
    output = capsys.readouterr().out.strip()
    assert "super-secret" not in output
    assert "***" in output
