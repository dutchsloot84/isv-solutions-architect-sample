from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.readiness import reporter


@pytest.fixture
def sample_delta() -> dict[str, object]:
    return {
        "metadata": {
            "current_snapshot": "snapshot_20240608.json",
            "previous_snapshot": "snapshot_20240601.json",
            "current_fix_version": "2024.06",
        },
        "summary": {
            "total_current": 4,
            "added": 1,
            "removed": 0,
            "changed": 1,
            "unchanged": 2,
            "field_deltas": {"status": 2, "deployment_notes": 1},
        },
        "details": {
            "added": [
                {
                    "key": "ABC-1",
                    "summary": "New login flow instrumentation",
                    "status": "In Progress",
                }
            ],
            "removed": [],
            "changed": [
                {
                    "key": "ABC-2",
                    "summary": "Audit logging hardening",
                    "changes": {
                        "status": {"previous": "In Progress", "current": "Blocked"},
                        "deployment_notes": {
                            "previous": "Pending security",
                            "current": "Security review requested",
                        },
                    },
                }
            ],
            "unchanged": [
                {
                    "key": "ABC-3",
                    "summary": "Feature flag cleanup",
                    "status": "Ready for Prod",
                },
                {
                    "key": "ABC-4",
                    "summary": "QA automation",
                    "status": "In Review",
                },
            ],
        },
    }


def test_aggregate_readiness_scores_open_items(sample_delta: dict[str, object]) -> None:
    aggregated = reporter.aggregate_readiness(sample_delta)

    readiness = aggregated["readiness"]
    assert readiness["open_items"] == 3
    assert readiness["total_issues"] == 4
    assert readiness["score"] == 25
    assert readiness["label"] == "At Risk"

    checklist = aggregated["checklist"]
    assert any(item["key"] == "ABC-1" for item in checklist)
    assert any("status: In Progress ➜ Blocked" in note for item in checklist for note in item["notes"])


def test_format_markdown_contains_sections(sample_delta: dict[str, object]) -> None:
    aggregated = reporter.aggregate_readiness(sample_delta)
    markdown = reporter.format_markdown(aggregated)

    assert "# Release Readiness" in markdown
    assert "## Snapshot Details" in markdown
    assert "Prioritized Remediation Checklist" in markdown
    assert "`ABC-1`" in markdown


def test_generate_readiness_report_persists_artifacts(tmp_path: Path, sample_delta: dict[str, object]) -> None:
    os.environ["ARTIFACT_ROOT"] = str(tmp_path)

    result = reporter.generate_readiness_report(sample_delta, persist=True)

    analysis_path = result["analysis_path"]
    report_path = result["report_path"]

    assert analysis_path is not None and analysis_path.exists()
    assert report_path is not None and report_path.exists()

    analysis_data = analysis_path.read_text(encoding="utf-8")
    report_data = report_path.read_text(encoding="utf-8")

    assert "open_items" in analysis_data
    assert "Release Readiness" in report_data

    # Clean up environment override
    del os.environ["ARTIFACT_ROOT"]
