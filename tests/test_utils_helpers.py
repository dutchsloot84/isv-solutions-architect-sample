"""Tests for utility helper functions used across the project."""

from __future__ import annotations

import importlib
import os
import sys
from datetime import timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from modules.utils import helpers


def test_project_and_module_root_are_directories():
    module = importlib.reload(helpers)
    globals()["helpers"] = module
    root = module.project_root()
    module_root = module.module_root()

    assert root.exists()
    assert module_root.exists()
    assert module_root.name == "modules"


def test_artifact_root_uses_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    path = helpers.artifact_root()

    assert path == (tmp_path / "artifacts")
    assert path.exists()


def test_artifact_root_defaults_to_project_data(tmp_path, monkeypatch):
    monkeypatch.delenv("ARTIFACT_ROOT", raising=False)
    monkeypatch.setattr(helpers, "project_root", lambda: tmp_path)
    path = helpers.artifact_root()

    assert path == tmp_path / "data"
    assert path.exists()


def test_artifact_path_builds_from_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path))
    result = helpers.artifact_path("reports", "sample.txt")

    assert result == tmp_path / "reports" / "sample.txt"


def test_ssl_verify_path_prefers_ssl_cert_path(tmp_path, monkeypatch):
    cert = tmp_path / "cert.pem"
    cert.write_text("certificate", encoding="utf-8")
    monkeypatch.setenv("SSL_CERT_PATH", str(cert))
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)

    resolved = helpers.ssl_verify_path()

    assert resolved == cert.resolve()
    assert os.environ["REQUESTS_CA_BUNDLE"] == str(cert.resolve())


def test_ensure_directory_is_idempotent(tmp_path):
    target = tmp_path / "nested" / "dir"
    first = helpers.ensure_directory(target)
    second = helpers.ensure_directory(target)

    assert first == target
    assert second == target
    assert target.exists()


def test_ssl_verify_path_uses_requests_bundle(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle.pem"
    bundle.write_text("bundle", encoding="utf-8")
    monkeypatch.delenv("SSL_CERT_PATH", raising=False)
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(bundle))

    resolved = helpers.ssl_verify_path()

    assert resolved == bundle.resolve()


def test_timestamp_helpers():
    timestamp = helpers.current_timestamp("UTC")
    assert timestamp.tzinfo is not None

    filename = helpers.timestamp_for_filename("UTC")
    assert filename.endswith("Z")

    fallback = helpers.current_timestamp("Invalid/Timezone")
    assert fallback.tzinfo == timezone.utc


def test_write_and_read_json(tmp_path):
    path = tmp_path / "data.json"
    helpers.write_json_safe({"value": 1}, path)
    loaded = helpers.read_json(path)

    assert loaded == {"value": 1}


def test_config_path_uses_project_root(tmp_path, monkeypatch):
    monkeypatch.setattr(helpers, "project_root", lambda: tmp_path)

    path = helpers.config_path()

    assert path == tmp_path / "configs" / "config.yaml"


def test_load_config_delegates(monkeypatch):
    captured: dict[str, object] = {}

    def fake_loader(path):
        captured["path"] = path
        return {"loaded": True}

    monkeypatch.setitem(
        sys.modules,
        "modules.config.loader",
        type("Loader", (), {"load_config": staticmethod(fake_loader)}),
    )

    result = helpers.load_config(Path("override.yaml"))

    assert result == {"loaded": True}
    assert captured["path"] == Path("override.yaml")


def test_latest_snapshot_files_returns_sorted(tmp_path):
    first = tmp_path / "snapshot_20240101T000000Z.json"
    second = tmp_path / "snapshot_20240201T000000Z.json"
    third = tmp_path / "snapshot_20240301T000000Z.json"
    for file_path in (first, second, third):
        file_path.write_text("{}", encoding="utf-8")

    latest = helpers.latest_snapshot_files(tmp_path, limit=2)

    assert latest == [third, second]


def test_resolve_path_expands_user(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    home_file = Path("~/file.txt")

    resolved = helpers.resolve_path(home_file)

    assert resolved == tmp_path / "file.txt"


def test_append_csv_row_writes_header(tmp_path):
    path = tmp_path / "data.csv"
    helpers.append_csv_row(path, {"name": "slice", "value": "10"})
    helpers.append_csv_row(path, {"name": "slice", "value": "10"})

    content = path.read_text(encoding="utf-8").strip().splitlines()
    assert content[0] == "name,value"
    assert content[1] == "slice,10"
    assert content[2] == "slice,10"
