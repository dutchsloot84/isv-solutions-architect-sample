# Slice 07 – Token Refresh & SSL Recovery AEV Prompt

## Analyze
1. Inspect `src/oauth_client.py` for existing token lifecycle management and identify refresh gaps.
2. Review HTTP networking utilities for SSL error handling (`src/http_retry.py` or equivalents).
3. Map environment dependencies (`GH_TOKEN`, `SSL_CERT_PATH`) and artifact expectations from `/prompts/MOP_guard_phase.json`.

## Execute
1. Implement token refresh handlers that renew OAuth credentials without exposing `JIRA_SECRET` or `GH_TOKEN`.
2. Add SSL retry and exponential backoff logic to HTTP utilities, respecting certificate paths and failure masking.
3. Emit structured logs for refresh and retry events, scrubbing sensitive tokens.
4. Work on branch `slice/07-token-refresh`, documenting changes in Guard Phase format.

## Validate
1. Run `pytest`, `mypy`, and `bandit`, storing results in `${ARTIFACT_ROOT}/validation/07/`.
2. Capture authentication refresh outputs within `${ARTIFACT_ROOT}/logs/auth_refresh_<timestamp>.log`.
3. Confirm retry flows are covered by tests or mocks with recorded evidence.

## Critic
- Review validation output for coverage and typing compliance with Guard Phase thresholds.
- Ensure log entries demonstrate masked credentials and reference Guard artifacts.
- Update GitHub Project #5 entry for “Slice 07 – Token Refresh & SSL Recovery”.

## Secure
- Double-check that refresh tokens and SSL certificate details are redacted in logs.
- Verify log sanitizer processed authentication logs prior to storage.
- Ensure new utilities respect secure defaults and do not leak secrets to stdout/stderr.
