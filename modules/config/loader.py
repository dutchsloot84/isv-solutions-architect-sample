"""Centralized configuration loader with environment overrides and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, cast

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency fallback
    load_dotenv = None  # type: ignore[assignment]

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency fallback
    import json as _json

    class _SimpleYAML:  # type: ignore[misc]
        """Minimal YAML parser fallback that supports JSON-formatted content."""

        @staticmethod
        def safe_load(stream):  # type: ignore[override]
            if hasattr(stream, "read"):
                return _json.loads(stream.read())
            return _json.loads(stream)

    yaml = cast(Any, _SimpleYAML())


DEFAULTS: Mapping[str, Any] = {
    "jira": {
        "base_url": "",
        "auth_url": "",
        "token_url": "",
        "api_scope": "read:jira-work write:jira-work",
        "token_path": ".secrets/jira_token.json",
        "redirect_uri": "http://localhost:8080/callback",
        "jql_fields": ["key", "summary", "status"],
    },
    "project": {
        "done_statuses": ["Done"],
        "deployment_notes_field": "",
    },
    "paths": {
        "snapshot_dir": "snapshots",
        "logs_dir": "logs",
        "reports_dir": "reports",
        "prompts_dir": "prompts",
    },
    "reporting": {
        "timezone": "UTC",
        "report_template": "default",
    },
}

ENVIRONMENT_OVERRIDES: Mapping[tuple[str, str], str] = {
    ("jira", "base_url"): "JIRA_BASE_URL",
    ("jira", "auth_url"): "JIRA_AUTH_URL",
    ("jira", "token_url"): "JIRA_TOKEN_URL",
    ("jira", "api_scope"): "JIRA_API_SCOPE",
    ("jira", "token_path"): "JIRA_TOKEN_PATH",
    ("jira", "redirect_uri"): "JIRA_REDIRECT_URI",
    ("paths", "snapshot_dir"): "SNAPSHOT_DIR",
    ("paths", "logs_dir"): "LOGS_DIR",
    ("paths", "reports_dir"): "REPORTS_DIR",
    ("paths", "prompts_dir"): "PROMPTS_DIR",
    ("reporting", "timezone"): "REPORTING_TIMEZONE",
}

REQUIRED_FIELDS: Mapping[str, Iterable[str]] = {
    "jira": ("base_url", "auth_url", "token_url", "api_scope"),
    "paths": ("snapshot_dir", "logs_dir", "reports_dir"),
}


class ConfigValidationError(ValueError):
    """Raised when the configuration fails validation."""

    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        message = "; ".join(self.errors) if self.errors else "Invalid configuration"
        super().__init__(message)


@dataclass(slots=True)
class ConfigLoader:
    """Load configuration files with environment overrides and schema validation."""

    config_path: Optional[Path | str] = None
    dotenv_path: Optional[Path | str] = None
    defaults: Mapping[str, Any] = field(default_factory=lambda: DEFAULTS)

    def load(self) -> Dict[str, Any]:
        """Return the merged configuration dictionary."""

        self._load_dotenv()
        config = self._read_config()
        merged = self._apply_defaults(config)
        merged = self._apply_environment_overrides(merged)
        self._validate(merged)
        return merged

    # -- internal helpers -------------------------------------------------
    def _load_dotenv(self) -> None:
        path = (
            Path(self.dotenv_path).expanduser()
            if self.dotenv_path
            else self._project_root() / ".env"
        )
        if path.exists():
            if load_dotenv is not None:
                load_dotenv(dotenv_path=path)  # type: ignore[arg-type]
                return

            for line in path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, _, value = stripped.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    def _read_config(self) -> Dict[str, Any]:
        config_file = (
            Path(self.config_path).expanduser()
            if self.config_path
            else self._default_config_path()
        )
        if not config_file.exists():
            return {}

        with config_file.open("r", encoding="utf-8") as stream:
            loaded = yaml.safe_load(stream) or {}
        if not isinstance(loaded, MutableMapping):
            raise ConfigValidationError(
                ["Configuration file must contain a mapping at the top level."]
            )
        return dict(loaded)

    def _apply_defaults(self, config: Mapping[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {
            section: dict(values) for section, values in self.defaults.items()
        }
        for section, values in config.items():
            if isinstance(values, Mapping):
                merged.setdefault(section, {})
                merged[section].update(values)
            else:
                merged[section] = values
        return merged

    def _apply_environment_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        for (section, key), env_var in ENVIRONMENT_OVERRIDES.items():
            value = os.getenv(env_var)
            if value:
                section_values = config.setdefault(section, {})
                if isinstance(section_values, MutableMapping):
                    section_values[key] = value
                    continue
                if isinstance(section_values, Mapping):
                    mutable_section = dict(section_values)
                    mutable_section[key] = value
                    config[section] = mutable_section
                    continue
                config[section] = {key: value}
        return config

    def _validate(self, config: Mapping[str, Any]) -> None:
        errors: list[str] = []
        for section, keys in REQUIRED_FIELDS.items():
            section_values = config.get(section, {})
            if not isinstance(section_values, Mapping):
                errors.append(f"Section '{section}' must be a mapping")
                continue
            for key in keys:
                value = section_values.get(key)
                if value in (None, ""):
                    errors.append(f"Missing required setting '{section}.{key}'")
        # Basic structure validation for list fields
        jira_fields = config.get("jira", {}).get("jql_fields")
        if jira_fields is not None and not isinstance(jira_fields, list):
            errors.append("jira.jql_fields must be a list when provided")

        done_statuses = config.get("project", {}).get("done_statuses")
        if done_statuses is not None and not isinstance(done_statuses, list):
            errors.append("project.done_statuses must be a list when provided")

        if errors:
            raise ConfigValidationError(errors)

    def _default_config_path(self) -> Path:
        return self._project_root() / "configs" / "config.yaml"

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[2]


def load_config(
    override_path: Optional[Path | str] = None,
    dotenv_path: Optional[Path | str] = None,
    defaults: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper returning the loaded configuration."""

    loader = ConfigLoader(
        config_path=override_path,
        dotenv_path=dotenv_path,
        defaults=defaults or DEFAULTS,
    )
    return loader.load()
