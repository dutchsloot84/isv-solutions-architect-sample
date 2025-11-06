"""Snapshot delta analysis utilities."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = ["analyze_snapshot_files", "format_markdown_report"]

if TYPE_CHECKING:  # pragma: no cover - imports executed only for type checkers
    from .analyzer import analyze_snapshot_files, format_markdown_report


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module("modules.snapshot_delta.analyzer")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
