"""Guard Phase helper to execute pytest with coverage artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

import pytest

from modules.utils import helpers

DEFAULT_COV_TARGETS: tuple[str, ...] = ("modules", "src")


def build_pytest_args(
    extra_args: Sequence[str] | None = None,
    *,
    targets: Iterable[str] = DEFAULT_COV_TARGETS,
) -> tuple[list[str], Path]:
    """Construct pytest arguments with coverage reporting to the artifact root."""

    config = helpers.load_config()
    timezone = config.get("reporting", {}).get("timezone")
    generated_at = helpers.current_timestamp(timezone)
    report_name = f"coverage_summary_{generated_at.strftime('%Y%m%d')}.txt"
    report_path = helpers.artifact_path("reports", report_name)
    helpers.ensure_directory(report_path.parent)

    args: list[str] = [f"--cov={target}" for target in targets]
    args.append(f"--cov-report=term-missing:{report_path}")
    if extra_args:
        args.extend(extra_args)
    return args, report_path


def run_pytest_with_coverage(extra_args: Sequence[str] | None = None) -> int:
    """Execute pytest with coverage reporting and return the exit code."""

    args, _ = build_pytest_args(extra_args)
    return pytest.main(args)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pytest with coverage artifacts")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Arguments to forward to pytest")
    parsed = parser.parse_args(argv)
    return run_pytest_with_coverage(parsed.pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
