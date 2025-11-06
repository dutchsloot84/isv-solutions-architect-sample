"""Field-level delta analysis for OAuth snapshot exports."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from modules.utils import helpers
from modules.utils.logger import get_logger

LOGGER = get_logger(__name__)

MASK_TOKEN = "***masked***"
SENSITIVE_FIELD_KEYWORDS = ("secret", "token", "password", "credential")


def _should_mask(field_name: str) -> bool:
    return any(keyword in field_name.lower() for keyword in SENSITIVE_FIELD_KEYWORDS)


def _mask_value(field_name: str, value: Any) -> Any:
    """Mask sensitive values while preserving structure."""

    if value is None:
        return None

    if _should_mask(field_name):
        if isinstance(value, list):
            return [MASK_TOKEN for _ in value]
        if isinstance(value, dict):
            return {key: MASK_TOKEN for key in value}
        return MASK_TOKEN

    if isinstance(value, list):
        masked_list: List[Any] = []
        for item in value:
            if isinstance(item, Mapping):
                masked_list.append({k: _mask_value(k, v) for k, v in item.items()})
            else:
                masked_list.append(item)
        return masked_list

    if isinstance(value, Mapping):
        return {key: _mask_value(key, val) for key, val in value.items()}

    return value


def _mask_issue(issue: Mapping[str, Any]) -> Dict[str, Any]:
    masked: Dict[str, Any] = {}
    for field, value in issue.items():
        masked[field] = _mask_value(field, value)
    return masked


def _index_issues(issues: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    indexed: Dict[str, Dict[str, Any]] = {}
    for issue in issues:
        key = issue.get("key")
        if not key:
            continue
        indexed[key] = dict(issue)
    return indexed


def _diff_issue(
    key: str,
    current_issue: Mapping[str, Any],
    previous_issue: Mapping[str, Any],
    field_counter: Counter,
) -> Optional[Dict[str, Any]]:
    diff: Dict[str, Any] = {"key": key, "changes": {}}

    fields = set(current_issue.keys()) | set(previous_issue.keys())
    for field in sorted(fields):
        if field == "key":
            continue
        current_value = current_issue.get(field)
        previous_value = previous_issue.get(field)
        if current_value == previous_value:
            continue
        diff["changes"][field] = {
            "previous": _mask_value(field, previous_value),
            "current": _mask_value(field, current_value),
        }
        field_counter[field] += 1

    if diff["changes"]:
        summary = current_issue.get("summary") or previous_issue.get("summary")
        diff["summary"] = _mask_value("summary", summary)
        return diff
    return None


def analyze_snapshots(
    current_snapshot: Mapping[str, Any],
    previous_snapshot: Mapping[str, Any],
    *,
    current_path: Optional[Path | str] = None,
    previous_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Compute structured differences between two snapshot payloads."""

    current_issues = current_snapshot.get("issues", [])
    previous_issues = previous_snapshot.get("issues", [])

    current_index = _index_issues(current_issues)
    previous_index = _index_issues(previous_issues)

    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    changed: List[Dict[str, Any]] = []
    unchanged: List[Dict[str, Any]] = []

    field_counter: Counter[str] = Counter()

    for key, issue in sorted(current_index.items()):
        previous_issue = previous_index.get(key)
        if not previous_issue:
            added.append(_mask_issue(issue))
            continue

        diff = _diff_issue(key, issue, previous_issue, field_counter)
        if diff:
            changed.append(diff)
        else:
            unchanged.append(
                {
                    "key": key,
                    "summary": _mask_value("summary", issue.get("summary")),
                    "status": _mask_value("status", issue.get("status")),
                }
            )

    for key, issue in sorted(previous_index.items()):
        if key not in current_index:
            removed.append(_mask_issue(issue))

    metadata = {
        "current_snapshot": Path(current_path).name if current_path else None,
        "previous_snapshot": Path(previous_path).name if previous_path else None,
        "current_fix_version": current_snapshot.get("fixVersion"),
        "previous_fix_version": previous_snapshot.get("fixVersion"),
    }

    summary = {
        "total_current": len(current_issues),
        "total_previous": len(previous_issues),
        "added": len(added),
        "removed": len(removed),
        "changed": len(changed),
        "unchanged": len(unchanged),
        "field_deltas": dict(sorted(field_counter.items())),
    }

    details = {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
    }

    return {"metadata": metadata, "summary": summary, "details": details}


def analyze_snapshot_files(current_path: Path | str, previous_path: Path | str) -> Dict[str, Any]:
    """Load snapshot files from disk and compute the delta."""

    current_snapshot = helpers.read_json(current_path)
    previous_snapshot = helpers.read_json(previous_path)
    LOGGER.info(
        "Analyzing snapshot delta between %s and %s", current_path, previous_path
    )
    return analyze_snapshots(
        current_snapshot,
        previous_snapshot,
        current_path=current_path,
        previous_path=previous_path,
    )


def format_markdown_report(delta: Mapping[str, Any]) -> str:
    """Render a human-readable markdown report for a delta payload."""

    metadata = delta.get("metadata", {})
    summary = delta.get("summary", {})
    details = delta.get("details", {})

    header_title = metadata.get("current_fix_version") or "Snapshot Delta"
    lines = [f"# Snapshot Delta – {header_title}", ""]

    if metadata.get("current_snapshot") or metadata.get("previous_snapshot"):
        lines.append("| Snapshot | File |")
        lines.append("| --- | --- |")
        if metadata.get("current_snapshot"):
            lines.append(f"| Current | `{metadata['current_snapshot']}` |")
        if metadata.get("previous_snapshot"):
            lines.append(f"| Previous | `{metadata['previous_snapshot']}` |")
        lines.append("")

    lines.append("## Summary")
    lines.append("")
    summary_rows = {
        "Current Issues": summary.get("total_current", 0),
        "Previous Issues": summary.get("total_previous", 0),
        "Added": summary.get("added", 0),
        "Removed": summary.get("removed", 0),
        "Changed": summary.get("changed", 0),
        "Unchanged": summary.get("unchanged", 0),
    }
    for label, value in summary_rows.items():
        lines.append(f"- **{label}:** {value}")

    field_deltas = summary.get("field_deltas") or {}
    if field_deltas:
        lines.append("")
        lines.append("### Field Changes")
        for field, count in field_deltas.items():
            lines.append(f"- `{field}` updated {count} time(s)")

    def _format_issue_list(title: str, issues: Sequence[Mapping[str, Any]]) -> None:
        if not issues:
            return
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        for issue in issues:
            key = issue.get("key", "Unknown")
            summary_text = issue.get("summary")
            status = issue.get("status")
            if summary_text and status:
                lines.append(f"- `{key}` – {summary_text} _(status: {status})_")
            elif summary_text:
                lines.append(f"- `{key}` – {summary_text}")
            elif status:
                lines.append(f"- `{key}` _(status: {status})_")
            else:
                lines.append(f"- `{key}`")

    _format_issue_list("Added Issues", details.get("added", []))
    _format_issue_list("Removed Issues", details.get("removed", []))

    changed_items = details.get("changed", [])
    if changed_items:
        lines.append("")
        lines.append("## Changed Issues")
        lines.append("")
        for item in changed_items:
            key = item.get("key", "Unknown")
            summary_text = item.get("summary")
            lines.append(f"- `{key}` – {summary_text or 'Summary unavailable'}")
            for field, payload in item.get("changes", {}).items():
                lines.append(
                    f"    - `{field}`: {payload.get('previous')} ➜ {payload.get('current')}"
                )

    unchanged_items = details.get("unchanged", [])
    if unchanged_items:
        lines.append("")
        lines.append("## Unchanged Issues")
        lines.append("")
        for item in unchanged_items:
            key = item.get("key", "Unknown")
            summary_text = item.get("summary")
            status = item.get("status")
            if summary_text and status:
                lines.append(f"- `{key}` – {summary_text} _(status: {status})_")
            elif summary_text:
                lines.append(f"- `{key}` – {summary_text}")
            elif status:
                lines.append(f"- `{key}` _(status: {status})_")
            else:
                lines.append(f"- `{key}`")

    return "\n".join(lines).strip() + "\n"


def _write_output(data: str, output_path: Optional[Path | str]) -> None:
    if not output_path:
        print(data)
        return

    path = Path(output_path)
    helpers.ensure_directory(path.parent)
    path.write_text(data, encoding="utf-8")
    LOGGER.info("Snapshot delta report written to %s", path)


def _write_json(data: Mapping[str, Any], output_path: Optional[Path | str]) -> None:
    payload = json.dumps(data, indent=2, ensure_ascii=False)
    _write_output(payload, output_path)


def _write_markdown(delta: Mapping[str, Any], output_path: Optional[Path | str]) -> None:
    markdown = format_markdown_report(delta)
    _write_output(markdown, output_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze differences between OAuth snapshot exports")
    parser.add_argument("--current", required=True, help="Path to the newer snapshot file")
    parser.add_argument("--previous", required=True, help="Path to the older snapshot file")
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format. Defaults to JSON.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the result. Prints to stdout when omitted.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    delta = analyze_snapshot_files(args.current, args.previous)

    if args.format == "markdown":
        _write_markdown(delta, args.output)
    else:
        _write_json(delta, args.output)


if __name__ == "__main__":
    main()
