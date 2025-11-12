import logging
from pathlib import Path

import pytest

from modules.fallback import csv_loader


def test_load_csv_returns_metadata(tmp_path: Path) -> None:
    csv_path = tmp_path / "jira.csv"
    csv_path.write_text(
        "Issue key,Summary,Status,Assignee,Fix Version/s,Updated,Created,Deployment notes\n"
        "ABC-1,Issue summary,In Progress,Ada Lovelace,1.0.0,2024-01-01,2023-12-01,Notes\n",
        encoding="utf-8",
    )

    result = csv_loader.load_csv(str(csv_path))

    assert result.row_count == 1
    assert result.issues[0]["key"] == "ABC-1"
    assert result.issues[0]["deployment_notes"] == "Notes"
    assert result.fieldnames[0] == "Issue key"
    assert len(result.checksum) == 64


def test_load_csv_as_issues_compatibility(tmp_path: Path) -> None:
    csv_path = tmp_path / "jira.csv"
    csv_path.write_text(
        "Issue key,Summary,Status,Assignee,Fix Version/s,Updated,Created\n"
        "ABC-2,Compat issue,In Progress,Grace Hopper,1.2.3,2024-01-02,2023-12-02\n",
        encoding="utf-8",
    )

    issues = csv_loader.load_csv_as_issues(str(csv_path))

    assert issues[0]["key"] == "ABC-2"
    assert issues[0]["fixVersions"] == ["1.2.3"]


def test_load_csv_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        csv_loader.load_csv(str(tmp_path / "missing.csv"))


def test_load_csv_warns_on_missing_headers(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    csv_path = tmp_path / "jira_partial.csv"
    csv_path.write_text(
        "Issue key,Summary\n" "ABC-3,Bad header\n",
        encoding="utf-8",
    )

    with caplog.at_level(logging.WARNING):
        csv_loader.load_csv(str(csv_path))

    assert "missing expected columns" in "".join(caplog.messages)


def test_load_csv_uses_golden_sample() -> None:
    sample_path = Path(__file__).parent / "data" / "csv" / "fallback_sample.csv"
    result = csv_loader.load_csv(str(sample_path))

    assert result.row_count == 1
    assert result.issues[0]["key"] == "ABC-10"
    # Checksum is deterministic for audit reporting.
    assert (
        result.checksum
        == "5af2c48168aa8386198f11a1ddf20539e215e5e85a8fe1bab29ea4134ba9b2cb"
    )
