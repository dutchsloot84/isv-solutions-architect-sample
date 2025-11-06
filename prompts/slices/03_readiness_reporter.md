# Slice 03 – Markdown Readiness Reporter AEV Prompt

## Analyze
1. Review outputs from the Snapshot Delta Analyzer to identify required readiness signals and metadata.
2. Audit existing reporting utilities under `reports/` for templates, helper functions, and artifact conventions.
3. Capture report scope, data sources, and stakeholder needs in `${ARTIFACT_ROOT}/03/analysis/readiness_inputs_<timestamp>.json`.

## Execute
1. Implement `modules/readiness/reporter.py` to aggregate analyzer inputs, compute readiness scores, and format Markdown sections.
2. Create `reports/slice_03/readiness_template.md` to document layout, placeholders, and distribution guidance.
3. Commit work against branch `slice/03-readiness-reporter`, keeping configuration references consistent with Slice 01 and 02 outputs.

## Validate
1. Generate sample reports using fixture data and compare them with expectations captured in `${ARTIFACT_ROOT}/03/reports/readiness_summary_<timestamp>.md`.
2. Run linting and unit tests that exercise the reporter formatting logic.
3. Ensure readiness outputs feed into future orchestration steps without breaking existing pipelines.

## Critic Check
- Ensure compliance with `/prompts/MOP_build_phase.json`, especially regarding artifact storage conventions.
- Confirm Markdown output excludes secrets while surfacing blocker status clearly.
- Update GitHub Project #5 entry for Slice 03 with branch, status, and key artifacts.
