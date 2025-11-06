"""Logging utilities for the Release Snapshot Manager."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from .helpers import ensure_directory


_LOGGERS: dict[str, logging.Logger] = {}


def _create_handler(path: Path) -> logging.FileHandler:
    ensure_directory(path.parent)
    handler = logging.FileHandler(path, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    return handler


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

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(console_handler)

    if log_file:
        logger.addHandler(_create_handler(Path(log_file)))

    _LOGGERS[name] = logger
    return logger
