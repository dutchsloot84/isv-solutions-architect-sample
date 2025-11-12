# Master Orchestrator Prompt: Guard Phase (v0.3.0 → v0.4.0)

## Purpose
Hardening, reliability, and compliance improvements that prepare Release Intelligence to progress from **v0.3.0** to **v0.4.0** while preserving balanced safeguards across engineering, QA, and security concerns.

## Extended AEV Loop
1. **Analyze** – Inspect repository health, dependency posture, and outstanding guard-rail gaps before modifications.
2. **Execute** – Apply scoped updates that reinforce stability, refresh credentials, and integrate validation tooling.
3. **Validate** – Run automated verification (tests, typing, and security checks) capturing artifacts beneath `${ARTIFACT_ROOT}`.
4. **Critic** – Review coverage, typing, and formatting output to ensure thresholds and conventions are met.
5. **Secure** – Confirm logging redactions, audit trail integrity, and absence of unmasked secrets.

## Environment Configuration
Surface the following environment variables for Guard Phase work. Sensitive values must never be logged directly and should remain masked across outputs and artifacts.

- `ARTIFACT_ROOT`
- `JIRA_CLIENT_ID`
- `JIRA_SECRET`
- `SSL_CERT_PATH`
- `GH_TOKEN`
- `ENABLE_CI_VALIDATION` *(scaffolded, default: false)*

## Tooling Expectations
- **Enabled tooling:** `ruff`, `black`, `mypy`, `pre-commit`, `bandit`, `log_sanitizer`
- **Scaffolded (disabled) tooling:** `trufflehog`, `pip-audit`, and CI validation gated by `ENABLE_CI_VALIDATION`

## Required Artifacts
Store the following artifacts beneath `${ARTIFACT_ROOT}` to document Guard Phase execution:

- `/schemas/jira_issue_schema.json`
- `/reports/test_results_<date>.xml`
- `/logs/security_audit_<timestamp>.log`
- `/.pre-commit-config.yaml`

Ensure filenames include ISO 8601 timestamps where indicated and maintain consistent subdirectory structures.

## Logging & Audit Controls
- Mask secrets, tokens, OAuth refresh credentials, and PII before writing to stdout/stderr or stored logs.
- Emit structured audit logs that capture timestamps, slice identifiers, branch names, and validation verdicts.
- Centralize audit logs beneath `${ARTIFACT_ROOT}/logs/` with consistent naming.
- When Jira OAuth is unavailable, ensure CSV fallback diagnostics (`logs/oauth_diagnostics_<timestamp>.json`) and audit reports
  (`reports/audit_csv_fallback_auto_<timestamp>.md`) are captured with row counts, column headers, and SHA-256 checksums of the
  supplied export.

## Success Criteria
The Guard Phase is considered successful when all of the following hold:

- Test coverage is ≥ 70% across unit and integration suites.
- Type coverage reaches ≥ 95% with `mypy` passing.
- Zero secrets or PII leak into logs, artifacts, or reports.

## Balanced Default Optional Checks
- `pre-commit` hooks remain active and pass for every commit.
- `ruff` and `black` enforce linting and formatting.
- `mypy` executes for typing validation.
- `bandit` runs for security scanning while `trufflehog` and `pip-audit` remain scaffolded.
- Log sanitizer tooling is enabled to scrub sensitive strings.
- CI validation remains disabled unless `ENABLE_CI_VALIDATION=true`.

## Guard Phase Operating Notes
- Maintain branch naming using `slice/<slice-id>-<short-description>`.
- Capture validation artifacts (tests, typing, lint, bandit) beneath `${ARTIFACT_ROOT}/validation/<slice-id>/` unless slice instructions specify otherwise.
- When optional tooling is scaffolded, include notes explaining activation requirements for future operators.
- Synchronize GitHub Project #5 entries after each loop, tagging items with Guard Phase context and storing audit links.

## Completion Definition
Guard Phase scaffolding is complete when:

- Guard MOP (Markdown + JSON) are live and referenced by slice prompts.
- Slices 06–10 are defined with Guard-specific goals and added to the GitHub Project board under “Ready”.
- Audit log entries document the transition from Build to Guard along with required artifacts and masked outputs.
