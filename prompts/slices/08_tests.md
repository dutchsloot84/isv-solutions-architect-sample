# Slice 08 – Unit & Integration Tests AEV Prompt

## Analyze
1. Inventory existing tests in `tests/` and identify coverage gaps across snapshot, delta, reporter, and CLI modules.
2. Review coverage tooling configuration, ensuring pytest-cov integrates with Guard Phase expectations.
3. Reference `/prompts/MOP_guard_phase.json` for required artifacts and environment constraints.

## Execute
1. Author or expand pytest suites covering snapshot generation, delta processing, readiness reporting, and CLI commands with mock Jira data.
2. Configure pytest-cov output to emit `reports/coverage_summary_<date>.txt` under `${ARTIFACT_ROOT}/reports/`.
3. Ensure CI-friendly markers respect `ENABLE_CI_VALIDATION` default (disabled) while documenting activation steps.
4. Work on branch `slice/08-tests` with Guard Phase commit formatting.

## Validate
1. Run `pytest --cov`, `mypy`, and `bandit`, storing evidence beneath `${ARTIFACT_ROOT}/validation/08/`.
2. Export JUnit-style results to `${ARTIFACT_ROOT}/reports/test_results_<date>.xml`.
3. Confirm coverage meets or exceeds 70%, documenting metrics in validation artifacts.

## Critic
- Examine validation outputs for coverage ≥70% and type coverage ≥95%.
- Verify formatting and lint hooks (`ruff`, `black`, `pre-commit`) pass locally.
- Update GitHub Project #5 entry for “Slice 08 – Unit & Integration Tests”.

## Secure
- Ensure test fixtures avoid embedding secrets or raw tokens.
- Confirm coverage and test logs are sanitized via log sanitizer.
- Validate that generated reports under `${ARTIFACT_ROOT}` redact sensitive identifiers.
