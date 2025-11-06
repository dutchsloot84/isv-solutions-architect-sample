"""Compatibility layer exposing JSON logging via :mod:`modules.logging`."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from modules.logging import LoggerFactory

__all__ = ["LoggerFactory", "get_logger"]


_default_factory = LoggerFactory()


def get_logger(
    name: str = "release_snapshot_manager",
    log_file: Optional[Path | str] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Return a JSON-formatted logger compatible with legacy helpers."""

    return _default_factory.get_logger(name, log_file=log_file, level=level)
