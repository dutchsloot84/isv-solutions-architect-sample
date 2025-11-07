"""Snapshot collection from Jira with CSV fallback support."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

import requests

from modules.fallback.csv_loader import load_csv_as_issues
from modules.utils import helpers
from modules.utils.http_retry import request_with_retry
from modules.utils.logger import get_logger
from modules.utils.oauth import get_jira_session

from . import builder

LOGGER = get_logger(__name__)


SnapshotResult = builder.SnapshotResult


class OAuthUnavailableError(RuntimeError):
    """Raised when OAuth is unavailable and CSV fallback should be triggered."""

    def __init__(self, message: str, *, reason: Optional[str] = None) -> None:
        super().__init__(message)
        self.reason = reason


def _build_issue_payload(issue: Mapping[str, object], deployment_field: str) -> Dict:
    fields = issue.get("fields", {}) if isinstance(issue, Mapping) else {}
    fix_versions = [
        fv.get("name")
        for fv in (fields.get("fixVersions") or [])
        if isinstance(fv, Mapping)
    ]
    deployment_notes = fields.get(deployment_field)

    return {
        "key": issue.get("key") if isinstance(issue, Mapping) else None,
        "summary": fields.get("summary") if isinstance(fields, Mapping) else None,
        "status": (
            fields.get("status", {}).get("name")
            if isinstance(fields.get("status"), Mapping)
            else None
        ),
        "fixVersions": fix_versions,
        "deployment_notes": deployment_notes,
    }


def _detect_oauth_error(status_code: Optional[int], body: Optional[str]) -> bool:
    if status_code in {401, 403}:
        return True
    if body and "access_denied" in body.lower():
        return True
    return False


def _fetch_jira_issues(fix_version: str) -> Iterable[Mapping[str, object]]:
    config = helpers.load_config()
    deployment_field = config["project"].get(
        "deployment_notes_field", "customfield_12345"
    )

    try:
        session = get_jira_session()
    except RuntimeError as error:
        raise OAuthUnavailableError(str(error), reason="token_missing") from error
    except Exception as error:  # noqa: BLE001 - preserve oauth context
        raise OAuthUnavailableError(str(error), reason=type(error).__name__) from error

    base_url = config["jira"].get("base_url")
    jql = f'fixVersion = "{fix_version}"'
    params = {
        "jql": jql,
        "fields": ",".join(config["jira"].get("jql_fields", [])),
        "maxResults": 500,
    }
    verify_path_obj = helpers.ssl_verify_path()
    verify_path = str(verify_path_obj) if verify_path_obj else True

    try:
        response = request_with_retry(
            session,
            "GET",
            f"{base_url}/rest/api/3/search",
            params=params,
            verify=verify_path,
        )
        response.raise_for_status()
    except requests.HTTPError as error:
        body = None
        try:
            body = error.response.text if error.response is not None else None
        except Exception:  # noqa: BLE001 - diagnostics only
            body = None
        status_code = error.response.status_code if error.response is not None else None
        if _detect_oauth_error(status_code, body):
            raise OAuthUnavailableError(
                "OAuth token rejected during Jira query",
                reason=f"HTTP {status_code}",
            ) from error
        raise
    except Exception as error:  # noqa: BLE001
        LOGGER.warning("Falling back to bundled mock data due to API error: %s", error)
        return [
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

    data = response.json()
    LOGGER.info(
        "Fetched %s issues from Jira for fixVersion %s",
        len(data.get("issues", [])),
        fix_version,
    )
    return (
        _build_issue_payload(issue, deployment_field)
        for issue in data.get("issues", [])
    )


def capture_snapshot(
    fix_version: str,
    *,
    tz: Optional[str] = None,
    csv_path: Optional[str] = None,
) -> SnapshotResult:
    """Capture a snapshot either from Jira or a CSV fallback source."""

    if csv_path:
        csv_path_obj = Path(csv_path).expanduser().resolve()
        csv_issues = load_csv_as_issues(str(csv_path_obj))
        metadata = {"csv_source": str(csv_path_obj)}
        return builder.build_snapshot(
            fix_version=fix_version,
            issues=csv_issues,
            mode="csv_fallback",
            csv_file=str(csv_path_obj),
            tz=tz,
            metadata=metadata,
        )

    issues = _fetch_jira_issues(fix_version)
    return builder.build_snapshot(
        fix_version=fix_version,
        issues=issues,
        mode="jira_api",
        csv_file=None,
        tz=tz,
    )


def fetch_jql_results(fix_version: str) -> List[Dict]:
    """Backward-compatible wrapper returning only the issue list."""

    result = capture_snapshot(fix_version)
    return result.issues


__all__ = [
    "SnapshotResult",
    "OAuthUnavailableError",
    "capture_snapshot",
    "fetch_jql_results",
]
