# Slice 04 – Config and Logging Framework AEV Prompt

## Analyze
1. Examine existing configuration loading patterns and environment variable usage across `modules/`.
2. Review logging implementations to understand formatting, handlers, and integration expectations from earlier slices.
3. Draft a configuration and logging design in `${ARTIFACT_ROOT}/04/design/config_logging_design_<timestamp>.md` covering schema validation and structured output.

## Execute
1. Implement `modules/config/loader.py` to centralize dotenv parsing, environment overrides, and default fallbacks with validation.
2. Create `modules/logging/factory.py` that exposes helpers for JSON-formatted logging compatible with readiness and orchestration modules.
3. Ensure all updates occur on branch `slice/04-config-logging` with supporting documentation and examples.

## Validate
1. Add automated checks demonstrating loader behavior against valid and invalid configs, capturing notes in `${ARTIFACT_ROOT}/04/reports/logging_validation_<timestamp>.md`.
2. Verify logging helpers integrate with prior analyzer/report modules without breaking formatting expectations.
3. Run repository lint/tests to ensure compatibility and catch regressions.

## Critic Check
- Ensure compliance with `/prompts/MOP_build_phase.json`, particularly regarding environment variable handling and artifact locations.
- Confirm sensitive configuration values remain masked in logs and artifacts.
- Update GitHub Project #5 entry for Slice 04 with status, branch, and reference links.
