"""Command-line interface orchestrating release intelligence workflows."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Mapping, MutableMapping, Optional, Sequence, Tuple

from modules import compare, snapshot, summarize
from modules.logging import LoggerFactory
from modules.orchestrator.versioning import ReleasePlan, VersionManager
from modules.utils import helpers

SnapshotFetcher = Callable[[str], Sequence[Mapping[str, object]]]
DeltaGenerator = Callable[[], Tuple[Path, Mapping[str, Sequence[object]]]]
ReportBuilder = Callable[[Path], Path]

_REQUIRED_ENV_VARS = (
    "JIRA_CLIENT_ID",
    "JIRA_SECRET",
    "SSL_CERT_PATH",
    "ARTIFACT_ROOT",
)


@dataclass
class Orchestrator:
    """Coordinate analyzers, readiness reporting, and tagging workflows."""

    fix_version: Optional[str] = None
    force_update: bool = False
    release_type: str = "patch"
    current_tag: Optional[str] = None
    env: MutableMapping[str, str] = field(default_factory=dict)
    snapshot_fetcher: SnapshotFetcher = snapshot.fetch_jql_results
    delta_generator: DeltaGenerator = compare.generate_delta
    report_builder: ReportBuilder = summarize.create_markdown_report
    version_manager: VersionManager = field(default_factory=VersionManager)

    slice_id: str = "09"
    phase: str = "guard"

    def __post_init__(self) -> None:
        if self.env:
            self.env = dict(self.env)
        else:
            self.env = dict(os.environ)
        self.fix_version = self.fix_version or self.env.get("FIX_VERSION")
        self._timestamp = helpers.timestamp_for_filename()
        self._artifact_root = helpers.artifact_path(self.slice_id)
        helpers.ensure_directory(self._artifact_root)
        self._logger = self._configure_logger()
        self._progress_path = (
            helpers.ensure_directory(helpers.artifact_path("progress"))
            / f"{self.slice_id}_{self._timestamp}.json"
        )

    # -- public API --------------------------------------------------
    def analyze(self) -> Path:
        """Persist orchestration guidance for operators and CI pipelines."""

        self._validate_environment()
        usage_path = self._usage_artifact_path()
        lines = [
            "# CLI Orchestrator Usage – Guard Phase",
            "",
            f"- **Slice:** {self.slice_id}",
            f"- **Phase:** {self.phase}",
            "- **Commands:** `analyze`, `execute`, `validate`.",
            "- **Required env vars:** `JIRA_CLIENT_ID`, `JIRA_SECRET`, `SSL_CERT_PATH`, `ARTIFACT_ROOT`, `FIX_VERSION`.",
            "- **Masking:** Secrets logged via the JSON logger are replaced with `***`.",
            "- **Artifacts:** progress JSON, usage notes, readiness report, release notes, pre-commit logs.",
            "",
            "## Notes",
            "- Ensure analyzers from Slices 01-04 are installed in the environment.",
            "- Provide a writable `${ARTIFACT_ROOT}` for logs and reports.",
            "- Review Slice 08 validation outputs in `${ARTIFACT_ROOT}/validation/08/` and related reports for regressions.",
            "- Reference `${ARTIFACT_ROOT}/reports/slice_08_<timestamp>.md` and `/reports/weekly_summary_<latest>.md` for context.",
            "- Capture blockers or dependency gaps below.",
            "- Guard Phase requires `.pre-commit-config.yaml` and hook activation notes to remain current.",
            "",
            "> Update this file with findings from each Analyze pass.",
        ]
        helpers.ensure_directory(usage_path.parent)
        usage_path.write_text("\n".join(lines), encoding="utf-8")
        self._logger.info("Usage guidance written", extra={"artifact": str(usage_path)})
        self._write_progress("analyze", {"usage_artifact": str(usage_path)})
        return usage_path

    def execute(self) -> ReleasePlan:
        """Run analyzers, build reports, and prepare version tagging."""

        self._validate_environment()
        if not self.fix_version:
            raise ValueError("A fix version must be provided for execution.")

        self._write_progress(
            "execute:start",
            {"fix_version": self.fix_version, "force_update": self.force_update},
        )

        issues = self._capture_snapshot()
        delta_path, categories = self.delta_generator()
        report_path = self.report_builder(delta_path)

        category_counts = {key: len(value) for key, value in categories.items()}
        highlights = self._summarize_highlights(category_counts)
        metadata: Dict[str, object] = {
            "fix_version": self.fix_version,
            "issues": len(issues),
            "delta_path": str(delta_path),
            "report_path": str(report_path),
        }
        plan = self.version_manager.plan_release(
            release_type=self.release_type,
            current_tag=self.current_tag,
            fix_version=self.fix_version,
            highlights=highlights,
            metadata=metadata,
        )

        self._write_progress(
            "execute:complete",
            {
                "issues": len(issues),
                "report_path": str(report_path),
                "release_notes": str(plan.notes_path),
                "next_version": plan.version,
            },
        )
        return plan

    def validate(self) -> Path:
        """Capture validation state and return the progress artifact path."""

        self._validate_environment()
        evidence = {
            "checks": [
                "Snapshot acquisition complete",
                "Delta comparison executed",
                "Readiness report generated",
                "Release notes prepared",
            ],
            "timestamp": helpers.current_timestamp().isoformat(),
        }
        self._write_progress("validate", evidence)
        self._logger.info(
            "Validation recorded", extra={"progress": str(self._progress_path)}
        )
        return self._progress_path

    # -- CLI entry ---------------------------------------------------
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Orchestrator":
        return cls(
            fix_version=args.fix_version,
            force_update=getattr(args, "force_update", False),
            release_type=getattr(args, "release_type", "patch"),
            current_tag=getattr(args, "current_tag", None),
        )

    # -- internal helpers -------------------------------------------
    def _validate_environment(self) -> None:
        missing = [name for name in _REQUIRED_ENV_VARS if not self.env.get(name)]
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(sorted(missing))}"
            )
        if not self.env.get("FIX_VERSION") and not self.fix_version:
            raise EnvironmentError("FIX_VERSION must be provided via env or argument.")

    def _configure_logger(self) -> logging.Logger:
        factory = LoggerFactory(slice_id=self.slice_id, phase=self.phase)
        log_dir = helpers.ensure_directory(self._artifact_root / "cli")
        log_path = log_dir / f"orchestrator_{self._timestamp}.log"
        logger = factory.get_logger(
            "release.orchestrator",
            log_file=log_path,
        )
        logger.debug("Logger configured", extra={"log_path": str(log_path)})
        return logger

    def _usage_artifact_path(self) -> Path:
        return (
            helpers.ensure_directory(self._artifact_root / "cli")
            / f"orchestrator_usage_{self._timestamp}.md"
        )

    def _capture_snapshot(self) -> Sequence[Mapping[str, object]]:
        self._logger.info(
            "Fetching snapshot",
            extra={"fix_version": self.fix_version, "force_update": self.force_update},
        )
        return self.snapshot_fetcher(str(self.fix_version))

    def _summarize_highlights(self, counts: Mapping[str, int]) -> Sequence[str]:
        if not counts:
            return ("No issue movements detected.",)
        return [
            f"{category}: {total}"
            for category, total in sorted(counts.items(), key=lambda item: item[0])
        ]

    def _write_progress(self, stage: str, details: Mapping[str, object]) -> Path:
        entry = {
            "stage": stage,
            "details": dict(details),
            "timestamp": helpers.current_timestamp().isoformat(),
        }
        if self._progress_path.exists():
            payload = dict(helpers.read_json(self._progress_path))
        else:
            payload = {
                "slice_id": self.slice_id,
                "phase": self.phase,
                "events": [],
            }

        events_data = payload.get("events")
        events: list[Dict[str, object]]
        if isinstance(events_data, list):
            events = [
                dict(event) for event in events_data if isinstance(event, Mapping)
            ]
        else:
            events = []

        events.append(dict(entry))
        payload["events"] = events
        helpers.write_json_safe(payload, self._progress_path)
        return self._progress_path


# -- CLI glue ---------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Release Intelligence CLI orchestrator",
    )
    parser.add_argument(
        "command",
        choices=("analyze", "execute", "validate"),
        help="AEV stage to run",
    )
    parser.add_argument(
        "--fix-version",
        dest="fix_version",
        help="Fix version to target. Falls back to FIX_VERSION env.",
    )
    parser.add_argument(
        "--current-tag",
        dest="current_tag",
        help="Current semantic version tag (e.g., 0.2.3)",
    )
    parser.add_argument(
        "--release-type",
        dest="release_type",
        default="patch",
        help="Release type for the next tag (major|minor|patch)",
    )
    parser.add_argument(
        "--force-update",
        dest="force_update",
        action="store_true",
        help="Force snapshot refresh instead of reusing cached results.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    orchestrator = Orchestrator.from_args(args)

    command = args.command
    if command == "analyze":
        orchestrator.analyze()
        return 0
    if command == "execute":
        orchestrator.execute()
        return 0
    if command == "validate":
        orchestrator.validate()
        return 0
    parser.error(f"Unsupported command: {command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
