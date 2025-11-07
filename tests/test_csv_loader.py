from pathlib import Path

import pytest

from modules.fallback import csv_loader


def test_load_csv_as_issues(tmp_path: Path) -> None:
    csv_path = tmp_path / "jira.csv"
    csv_path.write_text(
        "Issue key,Summary,Status,Assignee,Fix Version/s,Updated,Created\n"
        "ABC-1,Issue summary,In Progress,Ada Lovelace,1.0.0,2024-01-01,2023-12-01\n",
        encoding="utf-8",
    )

    issues = csv_loader.load_csv_as_issues(str(csv_path))

    assert issues[0]["key"] == "ABC-1"
    assert issues[0]["fixVersions"] == ["1.0.0"]
    assert issues[0]["updated"] == "2024-01-01"


def test_load_csv_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        csv_loader.load_csv_as_issues(str(tmp_path / "missing.csv"))
