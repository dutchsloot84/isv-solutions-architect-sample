"""Logging utilities for the Release Snapshot Manager."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from .helpers import ensure_directory


_LOGGERS: dict[str, logging.Logger] = {}


class _ContextFilter(logging.Filter):
    """Inject slice metadata into log records for structured output."""

    def __init__(self) -> None:
        super().__init__()
        self.slice_id = os.getenv("ACTIVE_SLICE_ID", "unknown")
        self.phase = os.getenv("MOP_PHASE", "unknown")

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - interface method
        record.slice_id = self.slice_id
        record.phase = self.phase
        return True


def _create_handler(path: Path) -> logging.FileHandler:
    ensure_directory(path.parent)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(_formatter())
    return handler


def _formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s | %(levelname)s | slice=%(slice_id)s | phase=%(phase)s | %(name)s | %(message)s"
    )


def get_logger(
    name: str = "release_snapshot_manager",
    log_file: Optional[Path | str] = None,
) -> logging.Logger:
    """Return a configured logger that logs to both console and optional file."""
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    context_filter = _ContextFilter()
    logger.addFilter(context_filter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_formatter())
    logger.addHandler(console_handler)

    if log_file:
        logger.addHandler(_create_handler(Path(log_file)))

    _LOGGERS[name] = logger
    return logger
