# Master Orchestrator Prompt: Build Phase (v0.1.0 → v0.3.0)

## Purpose
This Master Orchestrator Prompt (MOP) governs Release Intelligence work during the Build Phase, covering the incremental evolution from version **v0.1.0** through **v0.3.0**. It ensures every AEV (Analyze → Execute → Validate) cycle remains aligned with engineering, security, and delivery standards.

## AEV Loop Expectations
1. **Analyze**
   - Inspect repository structure, dependencies, and configuration to identify scope-specific gaps.
   - Cross-reference existing documentation in `docs/`, current slices in `slices/`, and historical prompts in `prompts/` for context.
   - Capture findings as structured notes, highlighting risks, blockers, and environment requirements.
2. **Execute**
   - Implement code and configuration changes following repository conventions.
   - Respect environment variable usage for secrets, credentials, and file system references.
   - Keep changes scoped to the active slice, ensuring atomic commits.
3. **Validate**
   - Run unit tests, linting, and static analysis relevant to modified components.
   - Produce artifacts that document the validation evidence.
   - Summarize the state of the slice, including outstanding follow-ups.

## Environment Configuration
The following environment variables **must** be surfaced and consumed by any automation or scripts initiated within this MOP:

- `JIRA_CLIENT_ID`
- `JIRA_SECRET`
- `SSL_CERT_PATH`
- `ARTIFACT_ROOT`
- `FIX_VERSION`

Never hardcode secrets or certificate paths—always inject via environment configuration. Sensitive values must be masked in logs and reports.

## Artifact Conventions
- Persist all generated artifacts under `${ARTIFACT_ROOT}`.
- Organize artifacts using the pattern `${ARTIFACT_ROOT}/<slice-id>/<artifact-name>` unless otherwise specified.
- Reference timestamps using ISO 8601 (UTC) formatting in filenames to guarantee uniqueness.
- Ensure artifacts include validation evidence (test outputs, coverage reports, lint logs) and design notes when applicable.

## Branch Convention
- Create feature branches per slice using the slug `slice/<slice-id>-<short-description>`.
- Commit messages should follow the `{type}: {summary}` format (e.g., `feat: add oauth snapshot writer`).
- Each slice concludes with a pull request referencing the slice ID and phase (e.g., "Slice 01 – Build Phase").

## Logging and Masking Rules
- Use structured logging with metadata for timestamps, slice ID, and phase.
- Mask all occurrences of `JIRA_SECRET` and any tokens read from `${SSL_CERT_PATH}`.
- Logs stored under `${ARTIFACT_ROOT}` must exclude personally identifiable information and secrets.

## Codex Execution Loop
- Iterate through the AEV structure until acceptance criteria are fulfilled.
- After each Execute step, perform a Critic Check before proceeding to Validate.
- Capture loop status in a progress artifact (`${ARTIFACT_ROOT}/progress/<slice-id>_<timestamp>.json`).

## Critic Check Standards
- Confirm parity between Markdown and JSON orchestration instructions.
- Verify environment variable usage and masking obligations.
- Ensure all artifacts are stored beneath `${ARTIFACT_ROOT}` with phase-appropriate naming.

## Project Board Synchronization
- Sync each slice’s status with **GitHub Project #5** at the end of every AEV loop.
- Update fields: Slice ID, Status (Analyze/Execute/Validate), Fix Version `${FIX_VERSION}`, and Current Branch.
- Attach artifact links from `${ARTIFACT_ROOT}` for traceability.

## Phase Tagging and Release Markers
- Apply the `v0.3.0` phase tag to slices completed after Slice 05.
- Slices 01–05 anchor the roadmap toward v0.3.0 and must reference this MOP in their Critic Check sections.

## Completion Criteria
The Build Phase is considered scaffolded when:
- All slices have MOP-compliant prompts and metadata.
- Project board entries reflect the phase progress.
- Artifacts demonstrate successful AEV loops with masked secrets and proper logging.
