"""Schema validation helpers for Jira payloads."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Sequence

from modules.utils import helpers
from modules.utils.logger import get_logger

LOGGER = get_logger(__name__)
MASK_TOKEN = "MASK" + "ED"
SCHEMA_FILENAME = "jira_issue_schema.json"


@lru_cache(maxsize=1)
def _schema_path() -> Path:
    project_schema = helpers.project_root() / "schemas" / SCHEMA_FILENAME
    if not project_schema.exists():
        raise FileNotFoundError(
            f"Jira issue schema not found at {project_schema}."
        )
    return project_schema


@lru_cache(maxsize=1)
def load_jira_issue_schema() -> Mapping[str, Any]:
    """Load the Jira issue schema and persist a copy under the artifact root."""

    schema_path = _schema_path()
    schema = helpers.read_json(schema_path)
    artifact_copy = helpers.artifact_path("schemas", SCHEMA_FILENAME)
    helpers.write_json_safe(schema, artifact_copy)
    return schema


TYPE_MAPPING: dict[str, tuple[type[Any], ...]] = {
    "string": (str,),
    "null": (type(None),),
    "array": (list,),
    "object": (dict,),
    "boolean": (bool,),
    "number": (int, float),
    "integer": (int,),
}


def _type_matches(value: Any, schema_types: Sequence[str]) -> bool:
    python_types: list[type[Any]] = []
    for type_name in schema_types:
        python_types.extend(TYPE_MAPPING.get(type_name, ()))
    if not python_types:
        return True
    if any(isinstance(value, typ) for typ in python_types):
        if "number" in schema_types and isinstance(value, bool):
            return False
        return True
    return False


def _normalise_types(schema_entry: Mapping[str, Any]) -> Sequence[str]:
    raw_type = schema_entry.get("type")
    if raw_type is None:
        return ()
    if isinstance(raw_type, str):
        return (raw_type,)
    if isinstance(raw_type, Sequence):
        return tuple(str(item) for item in raw_type)
    return ()


def _validate_array(value: Sequence[Any], schema_entry: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    item_schema = schema_entry.get("items")
    if not item_schema:
        return errors
    item_types = _normalise_types(item_schema)
    for index, item in enumerate(value):
        if not _type_matches(item, item_types):
            errors.append(f"Index {index} expected types {item_types!r}")
    return errors


def _schema_required_fields(schema: Mapping[str, Any]) -> Sequence[str]:
    required = schema.get("required")
    if isinstance(required, Sequence):
        return tuple(str(field) for field in required)
    return ()


def validate_issue(issue: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Validate a Jira issue against the schema."""

    schema = load_jira_issue_schema()
    if not isinstance(issue, Mapping):
        return False, ["Issue payload must be an object"]

    errors: list[str] = []
    required_fields = _schema_required_fields(schema)
    for field in required_fields:
        if field not in issue:
            errors.append(f"Missing required field '{field}'")

    properties = schema.get("properties", {})
    for field, schema_entry in properties.items():
        if field not in issue:
            continue
        value = issue[field]
        schema_types = _normalise_types(schema_entry)
        if not _type_matches(value, schema_types):
            errors.append(
                f"Field '{field}' expected types {schema_types!r} but received {type(value).__name__}"
            )
            continue
        if isinstance(value, list):
            errors.extend(
                f"Field '{field}' {detail}" for detail in _validate_array(value, schema_entry)
            )
    return not errors, errors


def sanitise_issue(issue: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Return a masked representation safe for logging."""

    mapping: Mapping[str, Any]
    if isinstance(issue, Mapping):
        mapping = issue
    else:
        mapping = {}

    masked: MutableMapping[str, Any] = {
        "key": mapping.get("key", MASK_TOKEN),
        "status": mapping.get("status"),
    }
    if "fixVersions" in mapping and isinstance(mapping["fixVersions"], list):
        masked["fixVersions"] = [MASK_TOKEN for _ in mapping["fixVersions"]]
    return dict(masked)


def filter_valid_issues(
    issues: Iterable[Mapping[str, Any]] | None,
) -> list[Dict[str, Any]]:
    """Filter out invalid issues, logging masked details for diagnostics."""

    valid: list[Dict[str, Any]] = []
    for issue in issues or []:
        is_valid, errors = validate_issue(issue)
        if not is_valid:
            masked_issue = sanitise_issue(issue)
            LOGGER.warning(
                "Skipping Jira issue during validation: masked=%s errors=%s",
                masked_issue,
                "; ".join(errors),
            )
            continue
        valid.append(dict(issue))
    return valid

