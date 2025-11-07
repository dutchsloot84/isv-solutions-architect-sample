"""Command-line entrypoint for the Release Snapshot Manager."""

from __future__ import annotations

import argparse
import os
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

    def _capture_with_csv(csv_path: Path) -> "snapshot.SnapshotResult":
        result = snapshot.capture_snapshot(
            fix_version,
            tz=tz,
            csv_path=str(csv_path),
        )
        return result

    if csv_override:
        return _capture_with_csv(csv_override)

    try:
        return snapshot.capture_snapshot(fix_version, tz=tz)
    except snapshot.OAuthUnavailableError as error:
        logger.warning(
            "⚠️ OAuth unavailable — entering CSV fallback mode.",
            extra={"mode": "csv_fallback"},
        )
        csv_prompt_path = _prompt_for_csv(logger)
        result = _capture_with_csv(csv_prompt_path)
        diagnostics_path = _write_oauth_diagnostics(
            error=error,
            config=config,
            tz=tz,
            csv_path=csv_prompt_path,
            issues_loaded=len(result.issues),
        )
        result.metadata.setdefault("oauth_diagnostics", diagnostics_path)
        return result


def _prompt_for_csv(logger) -> Path:
    """Prompt the operator to supply the fallback CSV file."""

    target_path = helpers.project_root() / CSV_DEFAULT_PATH
    helpers.ensure_directory(target_path.parent)
    logger.info(
        "Prompting operator to provide fallback CSV at %s",
        target_path,
        extra={"mode": "csv_fallback"},
    )
    print(
        "\n⚠️ OAuth unavailable — entering CSV fallback mode."
        "\nPlease export your Jira issues as CSV from your desired JQL view (e.g.,"
        ' project=MOB AND fixVersion="Mobilitas 2025.11.14").'
    )
    print("Then place the file at" f" {target_path} and press Enter to continue...")
    input()
    return target_path


def _write_oauth_diagnostics(
    *,
    error: "snapshot.OAuthUnavailableError",
    config: dict,
    tz: str | None,
    csv_path: Path,
    issues_loaded: int,
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
        "oauth_error": error.reason or type(error).__name__,
        "csv_used": str(csv_path),
        "issues_loaded": issues_loaded,
    }
    helpers.write_json_safe(payload, diagnostics_path)
    return diagnostics_path


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
    diagnostics_path: Optional[Path] = None
    csv_used: Optional[str] = None
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
                logger.info("Reusing existing snapshot %s", latest_path.name)
                reuse_snapshot = True
            else:
                snapshot_result = _capture_snapshot(
                    fix_version, tz, logger, config, csv_override
                )
                issues = snapshot_result.issues
                mode = snapshot_result.metadata.get("source", mode)
                csv_used = snapshot_result.metadata.get("csv_file")
                diagnostics_path = snapshot_result.metadata.get("oauth_diagnostics")
        except Exception as error:  # noqa: BLE001
            logger.warning("Failed to reuse snapshot: %s", error)
            snapshot_result = _capture_snapshot(
                fix_version, tz, logger, config, csv_override
            )
            issues = snapshot_result.issues
            mode = snapshot_result.metadata.get("source", mode)
            csv_used = snapshot_result.metadata.get("csv_file")
            diagnostics_path = snapshot_result.metadata.get("oauth_diagnostics")
    else:
        snapshot_result = _capture_snapshot(
            fix_version, tz, logger, config, csv_override
        )
        issues = snapshot_result.issues
        mode = snapshot_result.metadata.get("source", mode)
        csv_used = snapshot_result.metadata.get("csv_file")
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
        "oauth_diagnostics": str(diagnostics_path) if diagnostics_path else None,
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
        description="Generate Jira release readiness snapshots"
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
