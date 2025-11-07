"""Markdown report generation from snapshot deltas."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

try:
    from jinja2 import Template
except ImportError:
    Template = None  # type: ignore[assignment]

from .utils import helpers
from .utils.logger import get_logger

LOGGER = get_logger(__name__)


def _load_prompt(prompt_dir: Path) -> str:
    prompt_file = prompt_dir / "summary_prompt_v1.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return "Summarize the release readiness snapshot changes."


def _render_with_jinja(
    delta: Dict,
    counts: Dict[str, int],
    items: Dict[str, List],
    prompt_text: str,
    generated_date: str,
) -> str:
    template = Template(
        """## Release Snapshot Update – {{ fix_version }} ({{ generated_date }})\n\n{{ prompt }}\n\n✅ Completed: {{ counts.get('done', 0) }}\n🔁 Moved: {{ counts.get('moved', 0) }}\n⚠️ Still Open: {{ counts.get('still_open', 0) }}\n🧾 Deployment Notes Updated: {{ counts.get('updated_notes', 0) }}\n\n### Highlights\n{% if items.get('new') %}- **New Issues**: {{ items['new'] | length }} added.\n{% endif %}{% if items.get('done') %}- **Completed**: {{ items['done'] | length }} transitioned to done.\n{% endif %}{% if items.get('moved') %}- **Moved**: {{ items['moved'] | length }} changed status or were removed.\n{% endif %}{% if items.get('updated_notes') %}- **Deployment Notes**: {{ items['updated_notes'] | length }} updated.\n{% endif %}{% if items.get('still_open') %}- **Open Risks**: {{ items['still_open'] | length }} still open.\n{% endif %}"""
    )
    return template.render(
        fix_version=delta.get("fixVersion"),
        generated_date=generated_date,
        counts=counts,
        items=items,
        prompt=prompt_text.strip(),
    )


def _render_fallback(
    delta: Dict,
    counts: Dict[str, int],
    items: Dict[str, List],
    prompt_text: str,
    generated_date: str,
) -> str:
    lines = [
        f"## Release Snapshot Update – {delta.get('fixVersion')} ({generated_date})",
        "",
        prompt_text.strip(),
        "",
        f"✅ Completed: {counts.get('done', 0)}",
        f"🔁 Moved: {counts.get('moved', 0)}",
        f"⚠️ Still Open: {counts.get('still_open', 0)}",
        f"🧾 Deployment Notes Updated: {counts.get('updated_notes', 0)}",
        "",
        "### Highlights",
    ]
    if items.get("new"):
        lines.append(f"- **New Issues**: {len(items['new'])} added.")
    if items.get("done"):
        lines.append(f"- **Completed**: {len(items['done'])} transitioned to done.")
    if items.get("moved"):
        lines.append(
            f"- **Moved**: {len(items['moved'])} changed status or were removed."
        )
    if items.get("updated_notes"):
        lines.append(f"- **Deployment Notes**: {len(items['updated_notes'])} updated.")
    if items.get("still_open"):
        lines.append(f"- **Open Risks**: {len(items['still_open'])} still open.")
    return "\n".join(lines)


def create_markdown_report(delta_path: Path | str) -> Path:
    """Create a Markdown readiness report from the provided delta JSON."""
    config = helpers.load_config()
    delta = helpers.read_json(delta_path)

    tz = config.get("reporting", {}).get("timezone")
    generated_at = helpers.current_timestamp(tz)
    generated_date = generated_at.strftime("%b %d, %Y")
    file_date = generated_at.strftime("%Y%m%d")

    prompt_dir_setting = config["paths"].get("prompts_dir", "prompts")
    prompt_dir = Path(__file__).resolve().parents[1] / prompt_dir_setting
    prompt_text = _load_prompt(prompt_dir)

    counts: Dict[str, int] = delta.get("counts", {})
    items: Dict[str, List] = delta.get("items", {})

    if Template is not None:
        markdown = _render_with_jinja(delta, counts, items, prompt_text, generated_date)
    else:
        LOGGER.warning("jinja2 not installed; falling back to basic string rendering")
        markdown = _render_fallback(delta, counts, items, prompt_text, generated_date)

    reports_dir_setting = config["paths"].get("reports_dir", "reports")
    reports_dir_path = Path(reports_dir_setting)
    if not reports_dir_path.is_absolute():
        reports_dir_path = helpers.artifact_path(reports_dir_setting)
    reports_dir = helpers.ensure_directory(reports_dir_path)
    report_path = reports_dir / f"readiness_report_{file_date}.md"
    report_path.write_text(markdown, encoding="utf-8")
    LOGGER.info("Readiness report created at %s", report_path)
    return report_path
