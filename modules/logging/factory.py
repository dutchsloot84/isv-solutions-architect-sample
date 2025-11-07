"""JSON logging factory supporting slice metadata and masking."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from modules.utils.helpers import artifact_root, ensure_directory

_STANDARD_LOG_ATTRIBUTES: set[str] = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "stack",
}


class _JsonFormatter(logging.Formatter):
    """Format log records as JSON with masked sensitive values."""

    def __init__(
        self,
        *,
        slice_id: Optional[str] = None,
        phase: Optional[str] = None,
        masked_values: Optional[Iterable[str]] = None,
    ) -> None:
        super().__init__()
        self.slice_id = slice_id or os.getenv("ACTIVE_SLICE_ID", "unknown")
        self.phase = phase or os.getenv("MOP_PHASE", "unknown")
        self.masked_values = [value for value in (masked_values or []) if value]

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - interface method
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "slice_id": getattr(record, "slice_id", self.slice_id),
            "phase": getattr(record, "phase", self.phase),
        }

        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_ATTRIBUTES or key in payload or key.startswith("_"):
                continue
            payload[key] = value

        masked = self._mask(payload)
        return json.dumps(masked, ensure_ascii=False)

    # -- internal helpers -------------------------------------------------
    def _mask(self, value: Any) -> Any:
        if isinstance(value, str):
            masked_value = value
            for secret in self.masked_values:
                if secret and secret in masked_value:
                    masked_value = masked_value.replace(secret, "***")
            return masked_value
        if isinstance(value, Mapping):
            return {key: self._mask(sub_value) for key, sub_value in value.items()}
        if isinstance(value, list):
            return [self._mask(item) for item in value]
        return value


@dataclass(slots=True)
class LoggerFactory:
    """Factory for creating JSON-formatted loggers."""

    slice_id: Optional[str] = None
    phase: Optional[str] = None
    masked_values: Iterable[str] = field(default_factory=list)
    _masked_values: list[str] = field(init=False, repr=False)
    _loggers: Dict[str, logging.Logger] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        secrets = [os.getenv("JIRA_SECRET"), os.getenv("SSL_CERT_PATH")]
        self._masked_values = [
            value for value in [*self.masked_values, *secrets] if value
        ]
        self._loggers = {}

    def get_logger(
        self,
        name: str,
        *,
        log_file: Optional[Path | str] = None,
        level: int = logging.INFO,
    ) -> logging.Logger:
        """Return a configured JSON logger with optional file output."""

        if name in self._loggers:
            logger = self._loggers[name]
            if log_file:
                self._attach_file_handler(logger, log_file)
            return logger

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False
        formatter = self._formatter()

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        if log_file:
            self._attach_file_handler(logger, log_file, formatter=formatter)

        self._loggers[name] = logger
        return logger

    # -- internal helpers -------------------------------------------------
    def _formatter(self) -> _JsonFormatter:
        return _JsonFormatter(
            slice_id=self.slice_id,
            phase=self.phase,
            masked_values=self._masked_values,
        )

    def _attach_file_handler(
        self,
        logger: logging.Logger,
        log_file: Path | str,
        formatter: Optional[_JsonFormatter] = None,
    ) -> None:
        path = self._resolve_log_path(log_file)
        for handler in logger.handlers:
            if (
                isinstance(handler, logging.FileHandler)
                and Path(handler.baseFilename) == path
            ):
                return

        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter or self._formatter())
        logger.addHandler(file_handler)

    def _resolve_log_path(self, log_file: Path | str) -> Path:
        path = Path(log_file)
        if not path.is_absolute():
            base = os.getenv("ARTIFACT_ROOT")
            if base:
                base_path = Path(base).expanduser().resolve()
                ensure_directory(base_path)
            else:
                base_path = artifact_root()
            path = base_path / path
        ensure_directory(path.parent)
        return path


_default_factory: Optional[LoggerFactory] = None


def get_logger(
    name: str,
    *,
    log_file: Optional[Path | str] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Return a JSON logger from the default factory."""

    global _default_factory
    if _default_factory is None:
        _default_factory = LoggerFactory()
    return _default_factory.get_logger(name, log_file=log_file, level=level)
