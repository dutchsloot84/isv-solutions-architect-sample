"""Tests for the reusable log masking helpers."""

from __future__ import annotations

import re

import pytest

from src.logger import mask_sensitive, sanitize_logs


def test_mask_sensitive_handles_strings_and_patterns(monkeypatch):
    monkeypatch.setenv("JIRA_SECRET", "secret-token")
    payload = {
        "authorization": "Bearer secret-token",
        "details": "client_secret=secret-token",
    }

    masked = mask_sensitive(payload)

    assert masked["authorization"].endswith("***")
    assert masked["details"].endswith("***")
    assert "secret-token" not in masked["authorization"]


def test_mask_sensitive_handles_nested_sequences(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghs_example")
    data = ["ghs_example", {"token": "ghs_example"}, ("token=ghs_example",)]

    masked = mask_sensitive(data)

    assert masked[0] == "***"
    assert masked[1]["token"] == "***"
    assert masked[2][0].endswith("***")


def test_sanitize_logs_overwrites_files(tmp_path, monkeypatch):
    monkeypatch.setenv("API_TOKEN", "abc123")
    log_path = tmp_path / "auth.log"
    log_path.write_text("token=abc123", encoding="utf-8")

    sanitized_paths = sanitize_logs(log_path)

    assert sanitized_paths == [log_path.resolve()]
    assert log_path.read_text(encoding="utf-8") == "token=***"


def test_sanitize_logs_accepts_iterables(tmp_path, monkeypatch):
    monkeypatch.setenv("JIRA_CLIENT_ID", "client-id")
    first = tmp_path / "one.log"
    second = tmp_path / "two.log"
    first.write_text("Bearer client-id", encoding="utf-8")
    second.write_text("token=client-id", encoding="utf-8")

    sanitize_logs([first, second])

    assert first.read_text(encoding="utf-8").endswith("***")
    assert second.read_text(encoding="utf-8").endswith("***")


def test_mask_sensitive_respects_explicit_secrets():
    masked = mask_sensitive("api-key=visible", secrets=["visible"])
    assert masked == "api-key=***"


def test_mask_sensitive_handles_bytes_input(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "ghs_bytes")
    masked = mask_sensitive(b"token=ghs_bytes")
    assert masked == b"token=***"


def test_sanitize_logs_raises_for_missing_file(tmp_path):
    missing = tmp_path / "missing.log"
    try:
        sanitize_logs(missing)
    except FileNotFoundError:
        pass
    else:  # pragma: no cover - defensive fallback
        raise AssertionError("Expected FileNotFoundError")


def test_mask_sensitive_handles_sets_and_tuples():
    masked = mask_sensitive({"values": {"secret"}, "more": ("secret",)}, secrets=["secret"])
    assert masked["values"] == {"***"}
    assert masked["more"] == ("***",)


def test_mask_sensitive_supports_custom_patterns():
    pattern = re.compile(r"(api=)(\w+)")
    masked = mask_sensitive("api=token", patterns=[pattern], secrets=[])
    assert masked == "api=***"


def test_sanitize_logs_rejects_directory(tmp_path):
    directory = tmp_path / "logs"
    directory.mkdir()

    with pytest.raises(IsADirectoryError):
        sanitize_logs(directory)
