# Slice 03 – Readiness Reporter Template

This template documents the Markdown structure produced by
`modules.readiness.reporter.generate_readiness_report`. It illustrates how the
release readiness data is surfaced for stakeholders and highlights the
placeholders that may be customized when integrating with other tooling.

## Layout Overview

1. **Title** – `# Release Readiness – <fix version>`
2. **Snapshot Details** – Markdown table summarizing snapshot sources, the
   generation timestamp, and computed readiness score.
3. **Summary Metrics** – Bullet list of totals derived from the delta analyzer.
4. **Field Change Highlights** – Optional section that lists fields updated across
   issues along with how many times they changed between snapshots.
5. **Prioritized Remediation Checklist** – Checkbox list of issues requiring
   attention, sorted by category (new, changed, open) and severity keywords in the
   issue status. Each item may contain nested bullets describing the underlying
   field changes or rationale for inclusion.

## Placeholder Reference

| Placeholder | Description |
| --- | --- |
| `<fix version>` | Value from `metadata.current_fix_version` or `delta.fixVersion`. |
| `<current snapshot>` | File name of the most recent snapshot analyzed. |
| `<previous snapshot>` | File name of the baseline snapshot (may be `n/a`). |
| `<generated at>` | ISO 8601 timestamp respecting the configured timezone. |
| `<score>` | Computed readiness score scaled from 0–100. |
| `<field>` | Field name encountered in delta field changes. |
| `<count>` | Number of times the field changed between snapshots. |
| `<issue key>` | Jira issue key displayed in checklist entries. |
| `<status>` | Normalized status pulled from analyzer outputs. |
| `<category>` | Indicates whether the item is new, changed, or unchanged. |
| `<notes>` | Additional bullet points for context (status change, new issue, etc.). |

## Distribution Guidance

- Save generated reports under `${ARTIFACT_ROOT}/03/reports/` using the
  filename convention `readiness_summary_<timestamp>.md`.
- Pair each Markdown report with an analysis JSON artifact stored at
  `${ARTIFACT_ROOT}/03/analysis/readiness_inputs_<timestamp>.json` for traceability.
- Share the Markdown report with engineering leads and release managers ahead of
  go/no-go checkpoints. The checklist section is intended to guide remediation
  discussions and should be reviewed during readiness stand-ups.

## Customization Notes

- The reporter defaults to config-defined `project.done_statuses` to determine
  which statuses are considered complete. Update `configs/config.yaml` if your
  workflow uses different terminology.
- Additional templating (for example, company-branded headers) can be layered on
  by wrapping the Markdown output in a broader documentation generator.
- The checklist intentionally omits issues in done states to focus readers on
  remaining work. Adjust `_collect_checklist_items` if your rollout requires a
  different emphasis.
