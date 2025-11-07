from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from modules.snapshot_delta import analyzer


@pytest.fixture()
def snapshot_payloads() -> tuple[Dict[str, Any], Dict[str, Any]]:
    current = {
        "fixVersion": "2024.08",
        "issues": [
            {
                "key": "ABC-1",
                "summary": "New telemetry",
                "status": "In Progress",
                "deployment_notes": "Initial rollout",
                "fixVersions": ["2024.08"],
                "credential": "should-mask",
            },
            {
                "key": "ABC-2",
                "summary": "Improve logging",
                "status": "Ready for Prod",
                "deployment_notes": "Ready",
                "fixVersions": ["2024.08"],
            },
        ],
    }
    previous = {
        "fixVersion": "2024.07",
        "issues": [
            {
                "key": "ABC-2",
                "summary": "Improve logging",
                "status": "In Review",
                "deployment_notes": "Pending",
                "fixVersions": ["2024.07"],
                "token": "secret-token",
            },
            {
                "key": "ABC-3",
                "summary": "Legacy cleanup",
                "status": "Done",
                "deployment_notes": "Shipped",
                "fixVersions": ["2024.07"],
            },
        ],
    }
    return current, previous


def test_analyze_snapshots_detects_changes(
    snapshot_payloads: tuple[Dict[str, Any], Dict[str, Any]]
) -> None:
    current, previous = snapshot_payloads
    result = analyzer.analyze_snapshots(
        current,
        previous,
        current_path=Path("/tmp/snapshot_202408.json"),
        previous_path=Path("/tmp/snapshot_202407.json"),
    )

    summary = result["summary"]
    assert summary["added"] == 1
    assert summary["removed"] == 1
    assert summary["changed"] == 1
    assert summary["unchanged"] == 0

    changed_issue = result["details"]["changed"][0]
    changes = changed_issue["changes"]
    assert changes["status"]["previous"] == "In Review"
    assert changes["status"]["current"] == "Ready for Prod"
    assert changes["deployment_notes"]["current"] == "Ready"

    added_issue = result["details"]["added"][0]
    assert added_issue["credential"] == "MASKED"

    removed_issue = result["details"]["removed"][0]
    assert removed_issue["key"] == "ABC-3"
    assert removed_issue["deployment_notes"] == "Shipped"

    metadata = result["metadata"]
    assert metadata["current_snapshot"] == "snapshot_202408.json"
    assert metadata["previous_snapshot"] == "snapshot_202407.json"


def test_format_markdown_report_includes_sections(
    snapshot_payloads: tuple[Dict[str, Any], Dict[str, Any]]
) -> None:
    delta = analyzer.analyze_snapshots(*snapshot_payloads)
    markdown = analyzer.format_markdown_report(delta)

    assert markdown.startswith("# Snapshot Delta")
    assert "## Summary" in markdown
    assert "### Field Changes" in markdown
    assert "## Changed Issues" in markdown
    assert "`ABC-2`" in markdown
