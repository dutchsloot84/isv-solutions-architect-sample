"""Command-line entrypoint for the Release Snapshot Manager."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from modules import compare, snapshot, summarize
from modules.utils import helpers
from modules.utils.logger import get_logger

CSV_DEFAULT_PATH = "artifacts/imports/jira_export.csv"


def _capture_snapshot(
    fix_version: str,
    tz: str | None,
    logger,
    config: dict,
    csv_override: Path | None,
) -> "snapshot.SnapshotResult":
    """Capture a snapshot via Jira or CSV fallback based on runtime conditions."""

    def _capture_with_csv(
        csv_path: Path,
        *,
        trigger: str,
        oauth_error: Optional["snapshot.OAuthUnavailableError"],
    ) -> "snapshot.SnapshotResult":
        fallback_started = helpers.current_timestamp(tz)
        result = snapshot.capture_snapshot(
            fix_version,
            tz=tz,
            csv_path=str(csv_path),
        )
        _persist_fallback_records(
            result=result,
            logger=logger,
            config=config,
            tz=tz,
            fix_version=fix_version,
            trigger=trigger,
            oauth_error=oauth_error,
            fallback_started=fallback_started,
        )
        return result

    if csv_override:
        csv_override_path = helpers.resolve_path(csv_override)
        if not csv_override_path.exists():
            raise SystemExit(f"CSV override path not found: {csv_override_path}")
        logger.info(
            "Manual CSV override provided",
            extra={
                "mode": "csv_fallback",
                "csv_path": str(csv_override_path),
                "trigger": "manual_override",
            },
        )
        return _capture_with_csv(
            csv_override_path,
            trigger="manual_override",
            oauth_error=None,
        )

    try:
        return snapshot.capture_snapshot(fix_version, tz=tz)
    except snapshot.OAuthUnavailableError as error:
        logger.warning(
            "⚠️ OAuth unavailable — entering CSV fallback mode.",
            extra={"mode": "csv_fallback", "trigger": "oauth_unavailable"},
        )
        csv_prompt_path = _prompt_for_csv(logger, tz)
        return _capture_with_csv(
            csv_prompt_path,
            trigger="oauth_unavailable",
            oauth_error=error,
        )


def _prompt_for_csv(logger, tz: str | None) -> Path:
    """Prompt the operator to supply the fallback CSV file."""

    target_path = helpers.project_root() / CSV_DEFAULT_PATH
    helpers.ensure_directory(target_path.parent)
    logger.info(
        "Prompting operator to provide fallback CSV at %s",
        target_path,
        extra={"mode": "csv_fallback", "trigger": "oauth_unavailable"},
    )
    print(
        "\n⚠️ OAuth unavailable — entering CSV fallback mode."
        "\nPlease export your Jira issues as CSV from your desired JQL view (e.g.,"
        ' project=MOB AND fixVersion="Mobilitas 2025.11.14").'
    )
    print("Then place the file at" f" {target_path} and press Enter to continue...")

    while True:
        input()
        if target_path.exists():
            logger.info(
                "CSV fallback file detected",
                extra={
                    "mode": "csv_fallback",
                    "trigger": "oauth_unavailable",
                    "csv_path": str(target_path),
                },
            )
            return target_path
        logger.warning(
            "CSV fallback file missing at %s — waiting for operator",
            target_path,
            extra={
                "mode": "csv_fallback",
                "trigger": "oauth_unavailable",
                "attempt_timestamp": helpers.current_timestamp(tz).isoformat(),
            },
        )
        print(
            "\nNo CSV detected at",
            target_path,
            "\nPlease ensure the file exists and press Enter to retry...",
        )


def _write_oauth_diagnostics(
    *,
    error: Optional["snapshot.OAuthUnavailableError"],
    config: dict,
    tz: str | None,
    csv_path: Path,
    fix_version: str,
    csv_metadata: dict,
    trigger: str,
    fallback_started: str,
    fallback_completed: str,
) -> Path:
    """Persist structured diagnostics describing the fallback event."""

    logs_dir_setting = config["paths"].get("logs_dir", "logs")
    logs_dir = Path(logs_dir_setting)
    if not logs_dir.is_absolute():
        logs_dir = helpers.artifact_path(logs_dir_setting)
    helpers.ensure_directory(logs_dir)

    now = helpers.current_timestamp(tz)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    diagnostics_path = logs_dir / f"oauth_diagnostics_{timestamp}.json"
    payload = {
        "timestamp": now.isoformat(),
        "mode": "csv_fallback",
        "trigger": trigger,
        "fix_version": fix_version,
        "oauth_error": (
            error.reason
            if error and error.reason
            else (type(error).__name__ if error else None)
        ),
        "csv_used": str(csv_path),
        "csv_checksum": csv_metadata.get("csv_checksum"),
        "csv_row_count": csv_metadata.get("csv_row_count"),
        "csv_fieldnames": csv_metadata.get("csv_fieldnames"),
        "csv_duration_seconds": csv_metadata.get("csv_duration_seconds"),
        "issues_loaded": csv_metadata.get("csv_row_count"),
        "fallback_started": fallback_started,
        "fallback_completed": fallback_completed,
    }
    helpers.write_json_safe(payload, diagnostics_path)
    return diagnostics_path


def _write_fallback_audit(
    *,
    config: dict,
    tz: str | None,
    fix_version: str,
    csv_metadata: dict,
    diagnostics_path: Path,
    trigger: str,
) -> Path:
    """Generate a Markdown audit report summarizing CSV fallback usage."""

    reports_dir_setting = config["paths"].get("reports_dir", "reports")
    reports_dir = Path(reports_dir_setting)
    if not reports_dir.is_absolute():
        reports_dir = helpers.artifact_path(reports_dir_setting)
    helpers.ensure_directory(reports_dir)

    now = helpers.current_timestamp(tz)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    audit_path = reports_dir / f"audit_csv_fallback_auto_{timestamp}.md"

    csv_file = csv_metadata.get("csv_file")
    csv_checksum = csv_metadata.get("csv_checksum")
    csv_row_count = csv_metadata.get("csv_row_count")
    csv_fields = csv_metadata.get("csv_fieldnames") or []
    csv_duration = csv_metadata.get("csv_duration_seconds")

    content = "\n".join(
        [
            f"# Jira OAuth CSV Fallback (Automatic) – {now.isoformat()}",
            "",
            "## Background",
            (
                "OAuth 2.0 (3LO) was unavailable, so the Release Snapshot Manager "
                "entered CSV fallback mode automatically."
            ),
            "",
            "## CLI Context",
            f"- Fix version: `{fix_version}`",
            f"- Trigger: `{trigger}`",
            f"- CSV file: `{csv_file}`",
            "",
            "## CSV Summary",
            f"- Rows imported: {csv_row_count}",
            f"- Columns detected: {', '.join(csv_fields) if csv_fields else 'n/a'}",
            f"- SHA-256 checksum: `{csv_checksum}`",
            f"- Ingestion duration (s): {csv_duration}",
            "",
            "## Diagnostics",
            f"- Diagnostics log: `{diagnostics_path}`",
            f"- Fallback started: {csv_metadata.get('fallback_started')}",
            f"- Fallback completed: {csv_metadata.get('fallback_completed')}",
            f"- OAuth error: {csv_metadata.get('oauth_error')}",
        ]
    )

    audit_path.write_text(content, encoding="utf-8")
    return audit_path


def _persist_fallback_records(
    *,
    result: "snapshot.SnapshotResult",
    logger,
    config: dict,
    tz: str | None,
    fix_version: str,
    trigger: str,
    oauth_error: Optional["snapshot.OAuthUnavailableError"],
    fallback_started: datetime,
) -> None:
    """Persist diagnostics and audit artifacts when CSV fallback is used."""

    if result.metadata.get("source") != "csv_fallback":
        return

    fallback_completed_dt = helpers.current_timestamp(tz)
    csv_metadata = {
        "csv_file": result.metadata.get("csv_file"),
        "csv_checksum": result.metadata.get("csv_checksum"),
        "csv_row_count": result.metadata.get("csv_row_count", len(result.issues)),
        "csv_fieldnames": result.metadata.get("csv_fieldnames"),
        "csv_duration_seconds": result.metadata.get("csv_duration_seconds"),
        "fallback_started": fallback_started.isoformat(),
        "fallback_completed": fallback_completed_dt.isoformat(),
        "oauth_error": (
            oauth_error.reason
            if oauth_error and oauth_error.reason
            else (type(oauth_error).__name__ if oauth_error else None)
        ),
    }

    csv_path_value = csv_metadata.get("csv_file")
    if not csv_path_value:
        return
    csv_path = Path(csv_path_value)

    diagnostics_path = _write_oauth_diagnostics(
        error=oauth_error,
        config=config,
        tz=tz,
        csv_path=csv_path,
        fix_version=fix_version,
        csv_metadata=csv_metadata,
        trigger=trigger,
        fallback_started=csv_metadata["fallback_started"],
        fallback_completed=csv_metadata["fallback_completed"],
    )
    audit_path = _write_fallback_audit(
        config=config,
        tz=tz,
        fix_version=fix_version,
        csv_metadata=csv_metadata,
        diagnostics_path=diagnostics_path,
        trigger=trigger,
    )

    result.metadata.setdefault("oauth_diagnostics", str(diagnostics_path))
    result.metadata.setdefault("audit_report", str(audit_path))

    logger.info(
        "CSV fallback ingestion completed",
        extra={
            "mode": "csv_fallback",
            "trigger": trigger,
            "csv_path": str(csv_path),
            "csv_rows": csv_metadata.get("csv_row_count"),
            "csv_checksum": csv_metadata.get("csv_checksum"),
            "csv_fields": csv_metadata.get("csv_fieldnames"),
            "duration_seconds": csv_metadata.get("csv_duration_seconds"),
            "diagnostics": str(diagnostics_path),
            "audit_report": str(audit_path),
        },
    )


def run(
    fix_version: str,
    force_update: bool = False,
    csv_path: Optional[str] = None,
) -> None:
    """Execute the snapshot → delta → report workflow."""
    config = helpers.load_config()
    tz = config.get("reporting", {}).get("timezone")
    logger = get_logger(__name__)

    snapshot_dir_setting = config["paths"].get("snapshot_dir", "snapshots")
    snapshot_dir_path = Path(snapshot_dir_setting)
    if not snapshot_dir_path.is_absolute():
        snapshot_dir_path = helpers.artifact_path(snapshot_dir_setting)
    snapshot_dir = helpers.ensure_directory(snapshot_dir_path)

    current_date = helpers.current_timestamp(tz).strftime("%Y%m%d")
    latest_files = helpers.latest_snapshot_files(snapshot_dir, limit=1)
    reuse_snapshot = False
    csv_override = Path(csv_path).expanduser() if csv_path else None
    mode = "jira_api"
    diagnostics_path: Optional[str] = None
    csv_used: Optional[str] = None
    csv_row_count: Optional[int] = None
    csv_checksum: Optional[str] = None
    audit_report: Optional[str] = None
    issues: list[dict]
    snapshot_timestamp = helpers.current_timestamp(tz)
    snapshot_result: Optional[snapshot.SnapshotResult] = None

    if latest_files and not force_update:
        latest_path = latest_files[0]
        try:
            latest_data = helpers.read_json(latest_path)
            file_date = latest_path.stem.replace("snapshot_", "")[:8]
            if (
                latest_data.get("fixVersion") == fix_version
                and file_date == current_date
            ):
                issues = latest_data.get("issues", [])
                metadata = latest_data.get("metadata", {})
                mode = metadata.get("source", mode)
                csv_used = metadata.get("csv_file")
                csv_row_count = metadata.get("csv_row_count")
                csv_checksum = metadata.get("csv_checksum")
                audit_report = metadata.get("audit_report")
                logger.info("Reusing existing snapshot %s", latest_path.name)
                reuse_snapshot = True
            else:
                snapshot_result = _capture_snapshot(
                    fix_version, tz, logger, config, csv_override
                )
                issues = snapshot_result.issues
                mode = snapshot_result.metadata.get("source", mode)
                csv_used = snapshot_result.metadata.get("csv_file")
                csv_row_count = snapshot_result.metadata.get("csv_row_count")
                csv_checksum = snapshot_result.metadata.get("csv_checksum")
                audit_report = snapshot_result.metadata.get("audit_report")
                diagnostics_path = snapshot_result.metadata.get("oauth_diagnostics")
        except Exception as error:  # noqa: BLE001
            logger.warning("Failed to reuse snapshot: %s", error)
            snapshot_result = _capture_snapshot(
                fix_version, tz, logger, config, csv_override
            )
            issues = snapshot_result.issues
            mode = snapshot_result.metadata.get("source", mode)
            csv_used = snapshot_result.metadata.get("csv_file")
            csv_row_count = snapshot_result.metadata.get("csv_row_count")
            csv_checksum = snapshot_result.metadata.get("csv_checksum")
            audit_report = snapshot_result.metadata.get("audit_report")
            diagnostics_path = snapshot_result.metadata.get("oauth_diagnostics")
    else:
        snapshot_result = _capture_snapshot(
            fix_version, tz, logger, config, csv_override
        )
        issues = snapshot_result.issues
        mode = snapshot_result.metadata.get("source", mode)
        csv_used = snapshot_result.metadata.get("csv_file")
        csv_row_count = snapshot_result.metadata.get("csv_row_count")
        csv_checksum = snapshot_result.metadata.get("csv_checksum")
        audit_report = snapshot_result.metadata.get("audit_report")
        diagnostics_path = snapshot_result.metadata.get("oauth_diagnostics")

    if not reuse_snapshot:
        logger.info("Snapshot captured with %s issues", len(issues))
    else:
        logger.info("Snapshot already existed with %s issues", len(issues))

    logger.info("Generating delta between the latest snapshots")
    delta_path, categories = compare.generate_delta()

    logger.info("Building readiness report")
    report_path = summarize.create_markdown_report(delta_path)

    counts = {key: len(value) for key, value in categories.items()}
    run_metadata = {
        "timestamp": snapshot_timestamp.isoformat(),
        "fix_version": fix_version,
        "total_issues": len(issues),
        "new": counts.get("new", 0),
        "done": counts.get("done", 0),
        "moved": counts.get("moved", 0),
        "updated_notes": counts.get("updated_notes", 0),
        "still_open": counts.get("still_open", 0),
        "notes": report_path.name,
        "mode": mode,
        "csv_file": csv_used,
        "csv_row_count": csv_row_count,
        "csv_checksum": csv_checksum,
        "oauth_diagnostics": diagnostics_path,
        "audit_report": audit_report,
    }
    logs_dir_setting = config["paths"].get("logs_dir", "logs")
    logs_dir_path = Path(logs_dir_setting)
    if not logs_dir_path.is_absolute():
        logs_dir_path = helpers.artifact_path(logs_dir_setting)
    logs_dir = helpers.ensure_directory(logs_dir_path)
    run_log_path = logs_dir / "run_log.csv"
    helpers.append_csv_row(run_log_path, run_metadata)
    logger.info("Run metadata appended to %s", run_log_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Jira release readiness snapshots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "The tool automatically falls back to CSV ingestion if Jira OAuth "
            "is unavailable. Provide --csv <path> to skip the OAuth attempt "
            "and use a prepared export directly."
        ),
    )
    parser.add_argument(
        "--fixVersion",
        help="Fix version to evaluate. Overrides FIX_VERSION env if provided.",
    )
    parser.add_argument("--update", action="store_true", help="Force snapshot refresh")
    parser.add_argument(
        "--csv",
        help="Path to a Jira issue CSV export to use instead of OAuth",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    fix_version = args.fixVersion or os.getenv("FIX_VERSION")
    if not fix_version:
        raise SystemExit(
            "A fix version is required. Provide --fixVersion or set the FIX_VERSION environment variable."
        )
    run(fix_version, force_update=args.update, csv_path=args.csv)
