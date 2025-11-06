"""Command-line entrypoint for the Release Snapshot Manager."""

from __future__ import annotations

import argparse
from pathlib import Path

from modules import compare, snapshot, summarize
from modules.utils import helpers
from modules.utils.logger import get_logger


def run(fix_version: str, force_update: bool = False) -> None:
    """Execute the snapshot → delta → report workflow."""
    config = helpers.load_config()
    tz = config.get("reporting", {}).get("timezone")
    logger = get_logger(__name__)

    snapshot_dir = Path(__file__).resolve().parent / config["paths"].get("snapshot_dir", "data/snapshots")
    helpers.ensure_directory(snapshot_dir)

    current_date = helpers.current_timestamp(tz).strftime("%Y%m%d")
    latest_files = helpers.latest_snapshot_files(snapshot_dir, limit=1)
    reuse_snapshot = False
    if latest_files and not force_update:
        latest_path = latest_files[0]
        try:
            latest_data = helpers.read_json(latest_path)
            file_date = latest_path.stem.replace("snapshot_", "")[:8]
            if latest_data.get("fixVersion") == fix_version and file_date == current_date:
                issues = latest_data.get("issues", [])
                logger.info("Reusing existing snapshot %s", latest_path.name)
                reuse_snapshot = True
            else:
                issues = snapshot.fetch_jql_results(fix_version)
        except Exception as error:  # noqa: BLE001
            logger.warning("Failed to reuse snapshot: %s", error)
            issues = snapshot.fetch_jql_results(fix_version)
    else:
        issues = snapshot.fetch_jql_results(fix_version)

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
        "timestamp": helpers.current_timestamp(tz).isoformat(),
        "fix_version": fix_version,
        "total_issues": len(issues),
        "new": counts.get("new", 0),
        "done": counts.get("done", 0),
        "moved": counts.get("moved", 0),
        "updated_notes": counts.get("updated_notes", 0),
        "still_open": counts.get("still_open", 0),
        "notes": report_path.name,
    }
    logs_dir = Path(__file__).resolve().parent / config["paths"].get("logs_dir", "data/logs")
    helpers.append_csv_row(logs_dir / "run_log.csv", run_metadata)
    logger.info("Run metadata appended to %s", logs_dir / "run_log.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Jira release readiness snapshots")
    parser.add_argument("--fixVersion", required=True, help="Fix version to evaluate")
    parser.add_argument("--update", action="store_true", help="Force snapshot refresh")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.fixVersion, force_update=args.update)
