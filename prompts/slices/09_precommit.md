# Slice 09 – Repo Guard & Pre-Commit Hooks AEV Prompt

## Analyze
1. Inspect repository root for existing `.pre-commit-config.yaml` and scripts that manage developer tooling.
2. Review Guard Phase tooling expectations (`ruff`, `black`, `mypy`, `bandit`, `pytest`) and confirm compatibility with current setup.
3. Check `/prompts/MOP_guard_phase.json` for artifact, logging, and masking requirements.

## Execute
1. Generate `.pre-commit-config.yaml` enabling `ruff`, `black`, `mypy`, `bandit`, and `pytest` hooks consistent with Guard policies.
2. Create or update `scripts/setup_precommit.sh` to install dependencies and activate hooks.
3. Document hook usage and artifact paths in Guard Phase notes, ensuring outputs land beneath `${ARTIFACT_ROOT}/logs/`.
4. Commit on branch `slice/09-precommit`, ensuring commit messages follow Guard conventions.

## Validate
1. Run `pre-commit run --all-files` capturing logs to `${ARTIFACT_ROOT}/logs/precommit_setup_<timestamp>.log`.
2. Execute `pytest`, `mypy`, and `bandit` to confirm hooks align with manual runs.
3. Verify `.pre-commit-config.yaml` exists at repository root and is tracked.

## Critic
- Confirm linting, formatting, and typing reports satisfy Guard Phase thresholds.
- Ensure project board entry “Slice 09 – Repo Guard & Pre-Commit Hooks” reflects updated status and notes.
- Check that optional tooling remains scaffolded per Guard MOP definitions.

## Secure
- Inspect hook configuration for secret scanning or sanitization gaps.
- Verify log sanitizer integration covers hook outputs stored under `${ARTIFACT_ROOT}`.
- Ensure no secrets are written to `.pre-commit-config.yaml` or associated scripts.
