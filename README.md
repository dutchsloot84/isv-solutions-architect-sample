# Release Snapshot Manager

The Release Snapshot Manager automates release readiness reporting for Jira Cloud projects. It authenticates with OAuth 2.0 (3LO), captures timestamped snapshots of issues filtered by fixVersion, compares the most recent snapshots to identify meaningful changes, and generates Markdown reports suitable for leadership stakeholders.

## Features

- OAuth 2.0 (3-legged) authentication against Jira Cloud using the corporate certificate defined by `REQUESTS_CA_BUNDLE`.
- Snapshot storage for Jira issues retrieved via JQL.
- Delta detection for new, completed, moved, and updated issues using `deepdiff`.
- Markdown readiness report generation driven by Jinja2 templates.
- Modular architecture prepared for future extensions such as validation document creation and release note generation.

## Requirements

- Python 3.11+
- Atlassian Jira Cloud tenant with OAuth 2.0 integration configured
- Corporate SSL certificate stored as a PEM file and referenced via `REQUESTS_CA_BUNDLE`

### Required Environment Variables

```
JIRA_CLIENT_ID
JIRA_CLIENT_SECRET
REQUESTS_CA_BUNDLE
```

Optional overrides for other Jira endpoints and paths may be provided via environment variables that match the structure of `configs/config.yaml` (for example `JIRA_BASE_URL`, `JIRA_AUTH_URL`, etc.).

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## One-Time OAuth Setup

Run the authorization flow locally. This launches a browser window where you can complete the Jira login and grant permissions.

```bash
python -m modules.utils.oauth authorize
```

This command stores tokens at the path specified by `JIRA_TOKEN_PATH` (default `~/.jira_token.json`).

## Usage

Generate or update a release snapshot and readiness report for a fix version.

```bash
python main.py --fixVersion "Mobilitas 2025.11.14"
```

Use the `--update` flag to refresh the snapshot even if one exists for today.

### Output

- Snapshots are saved under `data/snapshots/snapshot_<timestamp>.json`.
- Delta comparisons are written to `data/snapshots/delta_<timestamp>.json`.
- Markdown readiness reports are generated in `reports/readiness_report_<date>.md`.
- Run metadata is appended to `data/logs/run_log.csv`.

## Future Extensions

- **Validation Document Creator** – produce checklists for deployment validation activities.
- **Release Notes Generator** – compile customer-facing release notes leveraging stored snapshots.

## Development Notes

- Follow PEP 8 style guidelines.
- Never log secrets or raw access tokens.
- All outbound HTTPS requests must verify certificates using `REQUESTS_CA_BUNDLE`.

## Continuous Integration

GitHub Actions run automated checks on pushes to `main` and all pull requests. The active
workflows include:

- **Python CI** – installs dependencies, runs Ruff linting, and executes the pytest suite.
- **Label Sync** – keeps repository labels aligned with `.github/labels.yml`.
- **Weekly Summary** – publishes Friday progress summaries under `reports/`.

No additional PR title validation or pre-commit automation runs in CI, keeping the
pipeline focused on essential quality and reporting tasks.
