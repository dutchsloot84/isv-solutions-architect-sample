# Slice 05 – CLI Orchestrator and Version Tagger AEV Prompt

## Analyze
1. Review modules from Slices 01–04 to map orchestrator dependencies, configuration inputs, and logging expectations.
2. Investigate existing CLI utilities in `modules/` and `main.py` for patterns to reuse or extend.
3. Capture orchestration goals, command flows, and versioning rules in `${ARTIFACT_ROOT}/05/cli/orchestrator_usage_<timestamp>.md`.

## Execute
1. Implement `modules/orchestrator/cli.py` to coordinate analyzer execution, readiness reporting, and artifact generation with structured logging.
2. Build `modules/orchestrator/versioning.py` that manages semantic version tagging, release notes, and integration with source control hooks.
3. Ensure commands support branch `slice/05-cli-orchestrator` workflows and document how to extend orchestrations.

## Validate
1. Run dry-run executions of the CLI orchestrator, capturing logs and tagging results in `${ARTIFACT_ROOT}/05/releases/version_tag_notes_<timestamp>.md`.
2. Add unit or integration tests covering orchestration flows and version tag generation.
3. Confirm compatibility with configuration/logging frameworks introduced in Slice 04 and readiness reporter outputs from Slice 03.

## Critic Check
- Ensure compliance with `/prompts/MOP_build_phase.json`, with attention to environment configuration and artifact locations.
- Verify secrets never surface in CLI output, logs, or generated release notes.
- Update GitHub Project #5 entry for Slice 05 to reflect orchestration readiness and branching details.
