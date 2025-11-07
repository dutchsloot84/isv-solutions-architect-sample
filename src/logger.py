"""Sensitive log masking and sanitization helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

DEFAULT_PLACEHOLDER = "***"

DEFAULT_SENSITIVE_ENV_VARS: tuple[str, ...] = (
    "JIRA_SECRET",
    "JIRA_CLIENT_SECRET",
    "JIRA_CLIENT_ID",
    "GH_TOKEN",
    "SSL_CERT_PATH",
    "ACCESS_TOKEN",
    "API_TOKEN",
)

_DEFAULT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(bearer\s+)([A-Za-z0-9\-._~+/=]+)"),
    re.compile(r"(?i)(token\s*[=:]\s*)([A-Za-z0-9\-._~+/=]+)"),
    re.compile(r"(?i)(secret\s*[=:]\s*)([A-Za-z0-9\-._~+/=]+)"),
    re.compile(r"(?i)(password\s*[=:]\s*)([A-Za-z0-9\-._~+/=]+)"),
)


def _iter_paths(path_or_paths: Path | str | Iterable[Path | str]) -> Iterator[Path]:
    if isinstance(path_or_paths, (str, Path)):
        yield Path(path_or_paths)
        return
    for path in path_or_paths:
        yield Path(path)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return tuple(result)


def _collect_secrets(extra: Iterable[str] | None = None) -> tuple[str, ...]:
    secrets: list[str] = []
    if extra:
        secrets.extend(str(item) for item in extra if item)
    for env_var in DEFAULT_SENSITIVE_ENV_VARS:
        value = os.getenv(env_var)
        if value:
            secrets.append(value)
    return _dedupe(secrets)


def _collect_patterns(
    patterns: Iterable[re.Pattern[str]] | None,
) -> tuple[re.Pattern[str], ...]:
    if patterns:
        compiled = [pattern for pattern in patterns]
        if compiled:
            return tuple(compiled)
    return _DEFAULT_PATTERNS


@dataclass(slots=True)
class _Sanitizer:
    secrets: tuple[str, ...]
    patterns: tuple[re.Pattern[str], ...]
    placeholder: str

    def mask(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._mask_string(value)
        if isinstance(value, bytes):
            masked = self._mask_string(value.decode("utf-8", errors="ignore"))
            return masked.encode("utf-8")
        if isinstance(value, Mapping):
            return {key: self.mask(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.mask(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.mask(item) for item in value)
        if isinstance(value, set):
            return {self.mask(item) for item in value}
        return value

    def _mask_string(self, value: str) -> str:
        masked = value
        for pattern in self.patterns:
            masked = pattern.sub(
                lambda match: match.group(1) + self.placeholder, masked
            )
        for secret in self.secrets:
            masked = masked.replace(secret, self.placeholder)
        return masked


def mask_sensitive(
    value: Any,
    *,
    secrets: Iterable[str] | None = None,
    patterns: Iterable[re.Pattern[str]] | None = None,
    placeholder: str = DEFAULT_PLACEHOLDER,
) -> Any:
    """Return a version of *value* with sensitive content masked."""

    sanitizer = _Sanitizer(
        secrets=_collect_secrets(secrets),
        patterns=_collect_patterns(patterns),
        placeholder=placeholder,
    )
    return sanitizer.mask(value)


def sanitize_logs(
    path_or_paths: Path | str | Iterable[Path | str],
    *,
    secrets: Iterable[str] | None = None,
    patterns: Iterable[re.Pattern[str]] | None = None,
    placeholder: str = DEFAULT_PLACEHOLDER,
    encoding: str = "utf-8",
) -> list[Path]:
    """Mask sensitive content within the provided log files."""

    sanitizer = _Sanitizer(
        secrets=_collect_secrets(secrets),
        patterns=_collect_patterns(patterns),
        placeholder=placeholder,
    )
    sanitized_paths: list[Path] = []
    for path in _iter_paths(path_or_paths):
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Log file not found: {resolved}")
        if resolved.is_dir():
            raise IsADirectoryError(
                f"Expected a file but received directory: {resolved}"
            )
        content = resolved.read_text(encoding=encoding)
        masked = sanitizer.mask(content)
        if masked != content:
            resolved.write_text(masked, encoding=encoding)
        sanitized_paths.append(resolved)
    return sanitized_paths


__all__ = [
    "DEFAULT_PLACEHOLDER",
    "mask_sensitive",
    "sanitize_logs",
]
