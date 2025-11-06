# Slice 05 – CLI Orchestrator and Version Tagger AEV Prompt

## Analyze
1. Review orchestration requirements from Slices 01–04 to understand analyzer inputs, readiness reporter expectations, logging hooks, and configuration loaders.
2. Audit existing CLI entry points in `main.py` and `modules/` to identify reusable patterns, flag missing dependency injections, and catalogue required environment variables (`JIRA_CLIENT_ID`, `JIRA_SECRET`, `SSL_CERT_PATH`, `ARTIFACT_ROOT`, `FIX_VERSION`).
3. Document orchestration goals, command flows, and masking rules in `${ARTIFACT_ROOT}/05/cli/orchestrator_usage_<timestamp>.md`, capturing dependencies and potential blockers discovered during analysis.

## Execute
1. Implement `modules/orchestrator/cli.py` with commands that coordinate analyzers, readiness reporting, artifact generation, and progress logging (`${ARTIFACT_ROOT}/progress/05_<timestamp>.json`) while enforcing structured logging from Slice 04.
2. Build `modules/orchestrator/versioning.py` to manage semantic version tagging, release note assembly, and safeguards for Git workflows without exposing secrets.
3. Ensure branch `slice/05-cli-orchestrator` captures updates, extends configuration/loading patterns, and documents extension points for future slices.

## Validate
1. Run dry-run executions of the CLI orchestrator, saving logs and tag outputs in `${ARTIFACT_ROOT}/05/releases/version_tag_notes_<timestamp>.md` with sensitive fields masked.
2. Add automated tests (unit or integration) covering orchestration flows, version tag generation, and environment-variable handling, storing supporting evidence alongside test logs.
3. Confirm compatibility with configuration/logging utilities from Slice 04 and readiness reporter outputs from Slice 03 by executing relevant test suites or scripts.

## Critic Check
- Verify alignment with `/prompts/MOP_build_phase.md`, confirming artifact locations, environment usage, and masking obligations.
- Ensure CLI output and release notes never emit `JIRA_SECRET` or credentials from `${SSL_CERT_PATH}`.
- Update GitHub Project #5 entry for Slice 05 with Analyze/Execute/Validate status, branch name, artifacts, and Fix Version metadata.
