#!/usr/bin/env bash
set -e

python -m venv .venv
source .venv/bin/activate
pip install -U pip pre-commit
pre-commit install
npm install --prefix services/integration-hub
npm install --prefix services/salesforce-mock
