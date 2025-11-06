# Slice 06 – Validation Layer AEV Prompt

## Analyze
1. Review existing Jira ingestion modules (`src/`), focusing on snapshot and delta analyzers for missing validation hooks.
2. Inspect `/schemas/` and related artifacts to confirm whether a Jira issue schema already exists.
3. Identify environment variables and logging requirements from `/prompts/MOP_guard_phase.json`, noting artifact paths that must land beneath `${ARTIFACT_ROOT}`.

## Execute
1. Author `schemas/jira_issue_schema.json` representing required Jira issue fields and types.
2. Implement `src/validation.py` with helpers for schema validation and graceful handling of missing fields.
3. Integrate validation checks into snapshot and delta analyzers, ensuring invalid payloads are skipped with masked logging.
4. Commit work on branch `slice/06-validation-layer` using Guard Phase conventions.

## Validate
1. Run `pytest`, `mypy`, and `bandit`, capturing logs under `${ARTIFACT_ROOT}/validation/06/`.
2. Record validation results in `${ARTIFACT_ROOT}/logs/validation_run_<timestamp>.log`.
3. Ensure schema artifacts exist beneath `${ARTIFACT_ROOT}/schemas/`.

## Critic
- Confirm coverage, typing, and lint outputs satisfy Guard Phase success criteria.
- Verify artifacts align with `/prompts/MOP_guard_phase.*` and document any deviations.
- Update GitHub Project #5 item “Slice 06 – Validation Layer” to reflect current status.

## Secure
- Review validation logs for redacted secrets or PII.
- Confirm log sanitizer integrations ran and masked sensitive Jira payload data.
- Ensure no raw tokens or credentials appear in `${ARTIFACT_ROOT}` artifacts.
