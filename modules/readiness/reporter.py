"""Aggregate snapshot delta signals into Markdown readiness reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
)

from modules.utils import helpers
from modules.utils.logger import get_logger

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class ChecklistItem:
    """Structured representation of a remediation action."""

    key: str
    summary: str
    status: str
    category: str
    notes: Tuple[str, ...]
    category_rank: int
    status_rank: int

    def sort_key(self) -> Tuple[int, int, str, str]:
        return (self.category_rank, self.status_rank, self.key, self.summary.lower())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "summary": self.summary,
            "status": self.status,
            "category": self.category,
            "notes": list(self.notes),
            "priority": {
                "category": self.category_rank,
                "status": self.status_rank,
            },
        }


def _normalize_status(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, Mapping):
        name = value.get("name")
        if name:
            return str(name)
        return str(value)
    return str(value)


def _status_priority(status: Optional[str]) -> int:
    if not status:
        return 5
    lowered = status.lower()
    if "block" in lowered or "critical" in lowered:
        return 0
    if "high" in lowered or "urgent" in lowered:
        return 1
    if "progress" in lowered:
        return 2
    if "review" in lowered or "qa" in lowered:
        return 3
    if "ready" in lowered or "done" in lowered:
        return 4
    return 5


CATEGORY_PRIORITY = {
    "New Issue": 0,
    "Changed Issue": 1,
    "Open Issue": 2,
}


def _category_priority(category: str) -> int:
    return CATEGORY_PRIORITY.get(category, 9)


def _issue_identifier(issue: Mapping[str, Any], default_prefix: str = "issue") -> str:
    key = issue.get("key")
    if key:
        return str(key)
    summary = issue.get("summary")
    if summary:
        return f"{default_prefix}-{abs(hash(summary))}"[:32]
    return f"{default_prefix}-unknown"


def _dedupe_notes(notes: Iterable[str]) -> Tuple[str, ...]:
    seen: List[str] = []
    for note in notes:
        if note not in seen:
            seen.append(note)
    return tuple(seen)


def _collect_checklist_items(
    details: Mapping[str, Any],
    done_statuses: Sequence[str],
) -> List[ChecklistItem]:
    done_lower = {str(status).lower() for status in done_statuses}
    collected: MutableMapping[str, ChecklistItem] = {}

    def _should_track(status: Optional[str]) -> bool:
        return not status or status.lower() not in done_lower

    def _store(
        issue: Mapping[str, Any],
        *,
        category: str,
        status: Optional[str],
        base_notes: Sequence[str] = (),
    ) -> None:
        if not _should_track(status):
            return
        identifier = _issue_identifier(issue)
        summary = issue.get("summary") or "Summary unavailable"
        normalized_status = status or "Unknown"
        category_rank = _category_priority(category)
        status_rank = _status_priority(status)
        note_payload = tuple(base_notes)

        existing = collected.get(identifier)
        if existing:
            merged_notes = _dedupe_notes(existing.notes + note_payload)
            existing_category_rank = _category_priority(existing.category)
            if category_rank < existing_category_rank:
                best_category = category
                best_category_rank = category_rank
            else:
                best_category = existing.category
                best_category_rank = existing_category_rank
            best_status_rank = min(existing.status_rank, status_rank)
            status_text = (
                normalized_status if normalized_status != "Unknown" else existing.status
            )
            collected[identifier] = ChecklistItem(
                key=identifier,
                summary=str(summary) if summary else existing.summary,
                status=status_text,
                category=best_category,
                notes=merged_notes,
                category_rank=best_category_rank,
                status_rank=best_status_rank,
            )
            return

        collected[identifier] = ChecklistItem(
            key=identifier,
            summary=str(summary),
            status=normalized_status,
            category=category,
            notes=note_payload,
            category_rank=category_rank,
            status_rank=status_rank,
        )

    added = details.get("added") or []
    for issue in added:
        status = _normalize_status(issue.get("status"))
        _store(
            issue,
            category="New Issue",
            status=status,
            base_notes=("Newly captured in latest snapshot.",),
        )

    changed = details.get("changed") or []
    for issue in changed:
        changes = issue.get("changes", {})
        status_change = changes.get("status")
        status = _normalize_status(
            (status_change or {}).get("current") or issue.get("status")
        )
        notes: List[str] = []
        for field, payload in sorted(changes.items()):
            previous = payload.get("previous")
            current = payload.get("current")
            notes.append(f"{field}: {previous} ➜ {current}")
        if not notes:
            notes.append("Field updates detected without detailed payload.")
        _store(
            issue,
            category="Changed Issue",
            status=status,
            base_notes=tuple(notes),
        )

    unchanged = details.get("unchanged") or []
    for issue in unchanged:
        status = _normalize_status(issue.get("status"))
        _store(
            issue,
            category="Open Issue",
            status=status,
            base_notes=("Status unchanged since previous snapshot.",),
        )

    return sorted(collected.values(), key=lambda item: item.sort_key())


def _extract_summary(delta: Mapping[str, Any]) -> Dict[str, Any]:
    summary = delta.get("summary")
    if isinstance(summary, Mapping):
        return dict(summary)
    counts = delta.get("counts")
    if isinstance(counts, Mapping):
        return {
            "total_current": (
                counts.get("total", sum(counts.values())) if "total" in counts else None
            ),
            "field_deltas": delta.get("field_deltas") or {},
            "counts": dict(counts),
        }
    return {}


def _extract_details(delta: Mapping[str, Any]) -> Dict[str, Any]:
    details = delta.get("details")
    if isinstance(details, Mapping):
        return dict(details)
    return {}


def _derive_totals(summary: Mapping[str, Any]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for key, value in summary.items():
        if isinstance(value, int):
            totals[key] = value
    counts = summary.get("counts")
    if isinstance(counts, Mapping):
        for key, value in counts.items():
            if isinstance(value, int):
                totals.setdefault(key, value)
    return totals


def _compute_readiness_score(open_items: int, total_issues: int) -> Tuple[int, str]:
    if total_issues <= 0:
        return 100, "On Track"
    completion_ratio = max(0.0, 1.0 - (open_items / max(total_issues, 1)))
    score = int(round(completion_ratio * 100))
    if score >= 85:
        label = "On Track"
    elif score >= 60:
        label = "Watch"
    else:
        label = "At Risk"
    return score, label


def aggregate_readiness(
    delta: Mapping[str, Any],
    *,
    config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Aggregate analyzer signals into readiness metadata."""

    config_data = dict(config) if config is not None else helpers.load_config()
    project_config = config_data.get("project", {})
    done_statuses = project_config.get("done_statuses", ["Done"])
    reporting_config = config_data.get("reporting", {})
    timezone = reporting_config.get("timezone")

    summary = _extract_summary(delta)
    details = _extract_details(delta)

    totals = _derive_totals(summary)
    total_current = totals.get("total_current")
    if total_current is None:
        total_current = (
            len(details.get("added", []))
            + len(details.get("unchanged", []))
            + len(details.get("changed", []))
        )
    checklist_items = _collect_checklist_items(details, done_statuses)
    open_items = len(checklist_items)
    score, score_label = _compute_readiness_score(open_items, total_current)

    metadata = delta.get("metadata") or {}
    fix_version = metadata.get("current_fix_version") or metadata.get(
        "previous_fix_version"
    )
    if not fix_version:
        fix_version = delta.get("fixVersion")

    aggregated = {
        "metadata": {
            "fix_version": fix_version,
            "current_snapshot": metadata.get("current_snapshot")
            or delta.get("current_snapshot"),
            "previous_snapshot": metadata.get("previous_snapshot")
            or delta.get("previous_snapshot"),
            "generated_at": helpers.current_timestamp(timezone).isoformat(),
            "timezone": timezone,
        },
        "summary": {
            "totals": totals,
            "field_changes": summary.get("field_deltas")
            or summary.get("field_changes")
            or {},
        },
        "readiness": {
            "score": score,
            "label": score_label,
            "open_items": open_items,
            "total_issues": total_current,
        },
        "checklist": [item.to_dict() for item in checklist_items],
    }

    removed = details.get("removed") or []
    aggregated["summary"]["removed"] = len(removed)
    aggregated["summary"]["added"] = len(details.get("added") or [])
    aggregated["summary"]["changed"] = len(details.get("changed") or [])

    return aggregated


def format_markdown(aggregated: Mapping[str, Any]) -> str:
    """Format aggregated readiness data into Markdown."""

    metadata = aggregated.get("metadata", {})
    readiness = aggregated.get("readiness", {})
    summary = aggregated.get("summary", {})
    checklist = aggregated.get("checklist", [])

    fix_version = metadata.get("fix_version") or "Unspecified Fix Version"
    header = f"# Release Readiness – {fix_version}"
    score = readiness.get("score", 0)
    label = readiness.get("label", "Unknown")

    lines = [header, ""]
    lines.append("## Snapshot Details")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(
        f"| Current Snapshot | `{metadata.get('current_snapshot') or 'n/a'}` |"
    )
    lines.append(
        f"| Previous Snapshot | `{metadata.get('previous_snapshot') or 'n/a'}` |"
    )
    lines.append(f"| Generated At | {metadata.get('generated_at', 'Unknown')} |")
    lines.append(f"| Readiness Score | {score}/100 ({label}) |")
    lines.append("")

    totals = summary.get("totals", {})
    if totals:
        lines.append("## Summary Metrics")
        lines.append("")
        for key, value in sorted(totals.items()):
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
        lines.append("")

    field_changes = summary.get("field_changes") or {}
    if field_changes:
        lines.append("## Field Change Highlights")
        lines.append("")
        for field, count in field_changes.items():
            lines.append(f"- `{field}` updated {count} time(s)")
        lines.append("")

    lines.append("## Prioritized Remediation Checklist")
    lines.append("")
    if not checklist:
        lines.append("All tracked items are complete. No remediation required.")
    else:
        for item in checklist:
            status = item.get("status", "Unknown")
            category = item.get("category", "Open Issue")
            summary_text = item.get("summary", "Summary unavailable")
            lines.append(
                f"- [ ] `{item.get('key')}` – {summary_text} _(Status: {status}; {category})_"
            )
            for note in item.get("notes", []):
                lines.append(f"  - {note}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_readiness_report(
    delta: Mapping[str, Any] | Path | str,
    *,
    config: Optional[Mapping[str, Any]] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Create aggregated readiness data and Markdown report.

    Parameters
    ----------
    delta:
        Either a dictionary produced by the snapshot delta analyzer or a path to the
        JSON payload on disk.
    config:
        Optional configuration dictionary. When omitted the global config file is
        loaded.
    persist:
        When ``True`` the aggregated analysis and Markdown report are written to the
        artifact directory as defined by ``ARTIFACT_ROOT``.
    """

    if isinstance(delta, (str, Path)):
        payload = helpers.read_json(delta)
    else:
        payload = dict(delta)

    config_data = dict(config) if config is not None else helpers.load_config()
    aggregated = aggregate_readiness(payload, config=config_data)
    markdown = format_markdown(aggregated)

    analysis_path: Optional[Path] = None
    report_path: Optional[Path] = None

    if persist:
        tz = config_data.get("reporting", {}).get("timezone")
        timestamp = helpers.timestamp_for_filename(tz)

        analysis_dir = helpers.artifact_path("03", "analysis")
        report_dir = helpers.artifact_path("03", "reports")
        helpers.ensure_directory(analysis_dir)
        helpers.ensure_directory(report_dir)

        analysis_path = analysis_dir / f"readiness_inputs_{timestamp}.json"
        report_path = report_dir / f"readiness_summary_{timestamp}.md"

        helpers.write_json_safe(aggregated, analysis_path)
        report_path.write_text(markdown, encoding="utf-8")

        LOGGER.info("Readiness analysis saved to %s", analysis_path)
        LOGGER.info("Readiness summary saved to %s", report_path)

    return {
        "aggregated": aggregated,
        "markdown": markdown,
        "analysis_path": analysis_path,
        "report_path": report_path,
    }
