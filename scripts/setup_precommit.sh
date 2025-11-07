#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_ROOT="${ARTIFACT_ROOT:-${REPO_ROOT}/reports/slice_09}"
LOG_DIR="${ARTIFACT_ROOT}/logs"
mkdir -p "${LOG_DIR}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_FILE="${LOG_DIR}/precommit_setup_${TIMESTAMP}.log"
touch "${LOG_FILE}"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "[setup] Using repository root: ${REPO_ROOT}"
echo "[setup] Artifact root: ${ARTIFACT_ROOT}"

python3 -m pip install --upgrade pip >/dev/null
python3 -m pip install --upgrade \
  -r "${REPO_ROOT}/requirements.txt" \
  pre-commit \
  ruff \
  black \
  mypy \
  bandit \
  pytest

cd "${REPO_ROOT}"
python3 -m pre_commit install

echo "[setup] Pre-commit hooks installed."
echo "[setup] Log captured at ${LOG_FILE}"
