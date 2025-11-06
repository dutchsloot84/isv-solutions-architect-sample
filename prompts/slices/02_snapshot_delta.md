# Slice 02 – Snapshot Delta Analyzer AEV Prompt

## Analyze
1. Review Slice 01 outputs to understand OAuth snapshot structure and masking rules.
2. Inspect modules under `modules/` and existing analyzers to determine integration patterns and logging expectations.
3. Outline delta comparison requirements in `${ARTIFACT_ROOT}/02/analysis/delta_requirements_<timestamp>.md`, including field normalization and tolerated drift thresholds.

## Execute
1. Implement the delta analyzer library in `modules/snapshot_delta/analyzer.py`, supporting comparison of two snapshot files and emitting structured differences.
2. Provide a CLI wrapper or orchestration hook that stores sample output at `reports/slice_02/delta_report_example.md`.
3. Ensure artifacts and code align with branch `slice/02-snapshot-delta`, following established naming conventions.

## Validate
1. Run unit tests or targeted scripts demonstrating diff output using representative fixtures.
2. Capture summary results in `${ARTIFACT_ROOT}/02/reports/delta_summary_<timestamp>.md`, noting masked fields and regression checks.
3. Confirm tooling integrates with logging utilities and prepares for downstream readiness reporting.

## Critic Check
- Ensure compliance with `/prompts/MOP_build_phase.json`, maintaining artifact placement beneath `${ARTIFACT_ROOT}`.
- Confirm secrets remain masked in diff outputs and documentation.
- Verify GitHub Project #5 metadata reflects Slice 02 status and branch `slice/02-snapshot-delta`.
