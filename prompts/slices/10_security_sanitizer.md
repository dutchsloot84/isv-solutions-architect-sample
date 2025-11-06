# Slice 10 – Security Sanitizer & Audit Log AEV Prompt

## Analyze
1. Review logging utilities (e.g., `src/logger.py`) to determine existing masking or sanitization coverage.
2. Audit current log outputs under `${ARTIFACT_ROOT}/logs/` for potential exposure of tokens or PII.
3. Reference `/prompts/MOP_guard_phase.json` to align security audit requirements and artifact destinations.

## Execute
1. Implement `mask_sensitive()` and `sanitize_logs()` helpers in `src/logger.py`, ensuring reusable masking patterns.
2. Integrate sanitization into logging pipelines and validation flows, capturing masked output only.
3. Generate a security audit log at `${ARTIFACT_ROOT}/logs/security_audit_<timestamp>.log` summarizing findings.
4. Operate on branch `slice/10-security-sanitizer`, documenting Guard Phase decisions.

## Validate
1. Run `pytest`, `mypy`, and `bandit`, storing logs under `${ARTIFACT_ROOT}/validation/10/`.
2. Confirm sanitizer functions include unit tests with coverage metrics captured in validation artifacts.
3. Verify security audit log exists and references sanitized evidence.

## Critic
- Check validation outputs for Guard success criteria (coverage, typing, formatting).
- Ensure audit documentation cites sanitized paths and excludes raw credentials.
- Update GitHub Project #5 entry “Slice 10 – Security Sanitizer & Audit Log”.

## Secure
- Inspect all logs and audit artifacts to confirm secrets remain masked.
- Validate log sanitizer configurations align with Guard MOP optional checks.
- Ensure any generated reports exclude sensitive payloads and adhere to retention policies.
