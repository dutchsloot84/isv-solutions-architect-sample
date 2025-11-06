"""Snapshot comparison utilities."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from deepdiff import DeepDiff
except ImportError:
    class DeepDiff(dict):  # type: ignore[misc]
        def __new__(cls, *args, **kwargs):
            value1, value2 = args[:2]
            return {} if value1 == value2 else {"values_changed": {"old_value": value1, "new_value": value2}}

from .utils import helpers
from .utils.logger import get_logger


LOGGER = get_logger(__name__)


def _index_issues(issues: List[Dict]) -> Dict[str, Dict]:
    return {issue["key"]: issue for issue in issues}


def _categorize(
    current: Dict[str, Dict],
    previous: Dict[str, Dict],
    done_statuses: List[str],
) -> Dict[str, List[Dict]]:
    categories: Dict[str, List[Dict]] = defaultdict(list)

    for key, issue in current.items():
        prev_issue = previous.get(key)
        status = issue.get("status")
        if not prev_issue:
            categories["new"].append(issue)
        else:
            if status != prev_issue.get("status"):
                if status in done_statuses:
                    categories["done"].append(issue)
                else:
                    categories["moved"].append({
                        "key": key,
                        "from": prev_issue.get("status"),
                        "to": status,
                    })
            diff = DeepDiff(prev_issue.get("deployment_notes"), issue.get("deployment_notes"), ignore_string_type_change=True)
            if diff:
                categories["updated_notes"].append({
                    "key": key,
                    "summary": issue.get("summary"),
                })

        if status not in done_statuses:
            categories["still_open"].append(issue)
        elif prev_issue and prev_issue.get("status") not in done_statuses and status in done_statuses:
            if issue not in categories["done"]:
                categories["done"].append(issue)

    for key, issue in previous.items():
        if key not in current:
            categories["moved"].append({
                "key": key,
                "from": issue.get("status"),
                "to": "Removed",
            })

    for required in ['new', 'done', 'moved', 'updated_notes', 'still_open']:
        categories.setdefault(required, [])

    return categories


def generate_delta() -> Tuple[Path, Dict[str, List[Dict]]]:
    """Compare the latest snapshots and return a delta summary."""
    config = helpers.load_config()
    snapshot_dir = Path(__file__).resolve().parents[1] / config["paths"].get("snapshot_dir", "data/snapshots")
    latest_files = helpers.latest_snapshot_files(snapshot_dir, limit=2)

    if not latest_files:
        raise FileNotFoundError("No snapshot files found. Run the snapshot step first.")

    current_path = latest_files[0]
    current_data = helpers.read_json(current_path)
    previous_data = helpers.read_json(latest_files[1]) if len(latest_files) > 1 else {"issues": []}

    current_index = _index_issues(current_data.get("issues", []))
    previous_index = _index_issues(previous_data.get("issues", []))

    done_statuses = config.get("project", {}).get("done_statuses", ["Done"])
    categories = _categorize(current_index, previous_index, done_statuses)

    delta = {
        "fixVersion": current_data.get("fixVersion"),
        "current_snapshot": current_path.name,
        "previous_snapshot": latest_files[1].name if len(latest_files) > 1 else None,
        "counts": {key: len(value) for key, value in categories.items()},
        "items": categories,
    }

    timestamp = helpers.timestamp_for_filename(config.get("reporting", {}).get("timezone"))
    delta_path = snapshot_dir / f"delta_{timestamp}.json"
    helpers.write_json_safe(delta, delta_path)
    LOGGER.info("Delta file saved to %s", delta_path)

    return delta_path, categories
