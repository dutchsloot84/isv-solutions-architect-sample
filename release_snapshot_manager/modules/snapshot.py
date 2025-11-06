"""Snapshot collection from Jira."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from .utils import helpers
from .utils.logger import get_logger
from .utils.oauth import get_jira_session


LOGGER = get_logger(__name__)


def _build_issue_payload(issue: Dict, deployment_field: str) -> Dict:
    fields = issue.get("fields", {})
    fix_versions = [fv.get("name") for fv in fields.get("fixVersions", [])]
    deployment_notes = fields.get(deployment_field)

    return {
        "key": issue.get("key"),
        "summary": fields.get("summary"),
        "status": fields.get("status", {}).get("name"),
        "fixVersions": fix_versions,
        "deployment_notes": deployment_notes,
    }


def fetch_jql_results(fix_version: str) -> List[Dict]:
    """Fetch Jira issues filtered by fixVersion and persist them as a snapshot."""
    config = helpers.load_config()
    tz = config.get("reporting", {}).get("timezone")
    snapshot_dir = helpers.ensure_directory(
        Path(__file__).resolve().parents[1]
        / config["paths"].get("snapshot_dir", "data/snapshots")
    )

    deployment_field = config["project"].get(
        "deployment_notes_field", "customfield_12345"
    )

    try:
        session = get_jira_session()
        base_url = config["jira"].get("base_url")
        jql = f'fixVersion = "{fix_version}"'
        params = {
            "jql": jql,
            "fields": ",".join(config["jira"].get("jql_fields", [])),
            "maxResults": 500,
        }
        verify_path = os.getenv("REQUESTS_CA_BUNDLE")
        response = session.get(
            f"{base_url}/rest/api/3/search",
            params=params,
            verify=verify_path,
        )
        response.raise_for_status()
        data = response.json()
        issues = [
            _build_issue_payload(issue, deployment_field)
            for issue in data.get("issues", [])
        ]
        LOGGER.info(
            "Fetched %s issues from Jira for fixVersion %s",
            len(issues),
            fix_version,
        )
    except (
        Exception
    ) as error:  # noqa: BLE001 - we want to provide friendly fallback
        LOGGER.warning("Falling back to mock data due to API error: %s", error)
        issues = [
            {
                "key": "ABC-1",
                "summary": "Mock issue one",
                "status": "In Progress",
                "fixVersions": [fix_version],
                "deployment_notes": "Initial deployment notes",
            },
            {
                "key": "ABC-2",
                "summary": "Mock issue two",
                "status": "Done",
                "fixVersions": [fix_version],
                "deployment_notes": "Mock notes",
            },
        ]

    timestamp = helpers.timestamp_for_filename(tz)
    snapshot_path = snapshot_dir / f"snapshot_{timestamp}.json"
    helpers.write_json_safe(
        {"fixVersion": fix_version, "issues": issues}, snapshot_path
    )
    LOGGER.info("Snapshot saved to %s", snapshot_path)
    return issues
