# Guard Phase Notes

## Slice 09 – Repo Guard & Pre-Commit Hooks
- Pre-commit configuration now enforces `ruff`, `black`, `mypy`, `bandit`, and `pytest` on every commit.
- `scripts/setup_precommit.sh` installs tooling and writes setup output to `${ARTIFACT_ROOT:-reports/slice_09}/logs/`.
- Validation logs for this slice are captured beneath `${ARTIFACT_ROOT}/logs/` with ISO 8601 timestamps (for example `precommit_setup_<timestamp>.log`, `pytest_<timestamp>.log`, `mypy_<timestamp>.log`, and `bandit_<timestamp>.log`).
- Hook outputs should be sanitized before archival using the guard-phase log sanitizer workflow.
