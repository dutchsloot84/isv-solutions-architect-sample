"""Tests for the centralized configuration loader."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from modules.config.loader import ConfigLoader, ConfigValidationError, load_config


def _write_yaml(path: Path, data: dict) -> None:
    import yaml

    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(json.loads(json.dumps(data)), handle)


def test_load_config_applies_defaults_and_env(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yaml"
    _write_yaml(
        config_path,
        {
            "jira": {
                "base_url": "https://example.atlassian.net",
                "auth_url": "https://auth.example.com/authorize",
                "token_url": "https://auth.example.com/token",
                "api_scope": "read:jira",
            },
            "paths": {"snapshot_dir": "snapshots_custom"},
        },
    )
    monkeypatch.setenv("LOGS_DIR", "custom_logs")

    loader = ConfigLoader(config_path=config_path)
    config = loader.load()

    assert config["paths"]["logs_dir"] == "custom_logs"
    assert config["paths"]["reports_dir"] == "reports"
    assert config["jira"]["token_url"] == "https://auth.example.com/token"


def test_load_config_reads_dotenv(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_yaml(
        config_path,
        {
            "jira": {
                "base_url": "https://example.atlassian.net",
                "auth_url": "https://auth.example.com/authorize",
                "token_url": "https://auth.example.com/token",
                "api_scope": "read:jira",
            }
        },
    )
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("REPORTS_DIR=artifact_reports\n", encoding="utf-8")

    loader = ConfigLoader(config_path=config_path, dotenv_path=dotenv_path)
    config = loader.load()

    assert config["paths"]["reports_dir"] == "artifact_reports"


def test_load_config_missing_file_returns_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_AUTH_URL", raising=False)
    monkeypatch.delenv("JIRA_TOKEN_URL", raising=False)
    monkeypatch.delenv("JIRA_API_SCOPE", raising=False)

    defaults = {
        "jira": {
            "base_url": "https://example",
            "auth_url": "https://auth",
            "token_url": "https://token",
            "api_scope": "scope",
        },
        "paths": {
            "snapshot_dir": "snapshots",
            "logs_dir": "logs",
            "reports_dir": "reports",
        },
    }

    config = load_config(override_path=tmp_path / "missing.yaml", defaults=defaults)
    assert config["paths"]["logs_dir"] == "logs"
    assert config["jira"]["base_url"] == "https://example"


def test_load_config_validation_error(tmp_path):
    config_path = tmp_path / "config.yaml"
    _write_yaml(config_path, {"jira": {}, "paths": {}})

    loader = ConfigLoader(config_path=config_path)
    with pytest.raises(ConfigValidationError) as exc:
        loader.load()

    error_message = str(exc.value)
    assert "Missing required setting 'jira.base_url'" in error_message
    assert "paths.snapshot_dir" not in error_message
