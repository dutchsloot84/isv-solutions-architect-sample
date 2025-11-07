from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from scripts import run_tests


def test_build_pytest_args_generates_artifact_path(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        run_tests.helpers, "load_config", lambda: {"reporting": {"timezone": "UTC"}}
    )
    fake_now = datetime(2024, 7, 15, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        run_tests.helpers, "current_timestamp", lambda tz=None: fake_now
    )

    args, report_path = run_tests.build_pytest_args(["-k", "snapshot"])

    expected_path = run_tests.helpers.artifact_path(
        "reports", "coverage_summary_20240715.txt"
    )
    assert report_path == expected_path
    assert expected_path.parent.exists()
    assert "--cov=modules" in args
    assert "--cov=src" in args
    assert f"--cov-report=term-missing:{expected_path}" in args
    assert args[-2:] == ["-k", "snapshot"]


def test_run_pytest_with_coverage_invokes_pytest(tmp_path, monkeypatch):
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setattr(
        run_tests.helpers, "load_config", lambda: {"reporting": {"timezone": "UTC"}}
    )
    fake_now = datetime(2024, 7, 16, 9, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(
        run_tests.helpers, "current_timestamp", lambda tz=None: fake_now
    )

    captured_args: list[list[str]] = []

    def fake_pytest_main(args: list[str]) -> int:
        captured_args.append(args)
        return 0

    monkeypatch.setattr(run_tests, "pytest", SimpleNamespace(main=fake_pytest_main))

    exit_code = run_tests.run_pytest_with_coverage()

    assert exit_code == 0
    assert captured_args
    cov_args = captured_args[0]
    assert any(item.startswith("--cov-report=term-missing:") for item in cov_args)
    assert any(item == "--cov=modules" for item in cov_args)
    assert any(item == "--cov=src" for item in cov_args)
