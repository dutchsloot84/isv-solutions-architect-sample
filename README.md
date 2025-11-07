# Release Snapshot Manager

The Release Snapshot Manager automates release readiness reporting for Jira Cloud projects. It authenticates with OAuth 2.0 (3LO), captures timestamped snapshots of issues filtered by fixVersion, compares the most recent snapshots to identify meaningful changes, and generates Markdown reports suitable for leadership stakeholders.

## Features

- OAuth 2.0 (3-legged) authentication against Jira Cloud using the corporate certificate defined by `SSL_CERT_PATH`.
- Snapshot storage for Jira issues retrieved via JQL.
- Delta detection for new, completed, moved, and updated issues using `deepdiff`.
- Markdown readiness report generation driven by Jinja2 templates.
- Modular architecture prepared for future extensions such as validation document creation and release note generation.

## Requirements

- Python 3.11+
- Atlassian Jira Cloud tenant with OAuth 2.0 integration configured
- Corporate SSL certificate stored as a PEM file and referenced via `SSL_CERT_PATH`

### Required Environment Variables

At minimum, configure the following values in your environment or `.env` file:

- `ARTIFACT_ROOT`
- `SSL_CERT_PATH`
- `FIX_VERSION` (optional default)

Optional overrides for Jira endpoints and path locations may be provided via environment variables that match the structure of `configs/config.yaml` (for example `JIRA_BASE_URL`, `JIRA_AUTH_URL`, etc.). Place secrets in a `.env` file for local development—variables are loaded automatically when present.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 🔐 Jira OAuth 3LO Authorization

The Release Snapshot Manager authenticates securely with Jira Cloud using OAuth 2.0 (3-legged).

### 1️⃣ Prerequisites
Ensure your `.env` file includes:

```env
JIRA_CLIENT_ID=<your_client_id>
JIRA_CLIENT_SECRET=<your_client_secret>
JIRA_REDIRECT_URI=http://localhost:8000/callback
JIRA_BASE_URL=https://csaaig.atlassian.net
```

### 2️⃣ Run Authorization

```bash
python -m modules.utils.oauth authorize
```

This command:

- Launches your browser for Atlassian login.
- Captures the authorization code automatically from `http://localhost:8000/callback`.
- Exchanges it for an access token.
- Saves the token securely to `.secrets/jira_token.json`.

Expected success message:

```
✅ Authorization complete! Token saved to .secrets/jira_token.json
```

### 3️⃣ Token Expiration

Atlassian Jira Cloud apps do not currently support `offline_access` for all integrations. As a result, only a short-lived `access_token` is issued (typically valid for ~1 hour).

When the token expires, simply re-run:

```bash
python -m modules.utils.oauth authorize
```

You’ll see:

```
⚠️ Token expired — please reauthorize with `python -m modules.utils.oauth authorize`
```

Tokens are stored automatically under `.secrets/jira_token.json` and excluded from version control.

### 4️⃣ Troubleshooting

- **Error: `(access_denied)` Unauthorized** – Ensure your `.env` contains the correct client ID/secret.
- Verify your redirect URI matches exactly `http://localhost:8000/callback`.
- Re-run authorization after saving `.env`.

✅ Expected Behavior

- Authorization completes successfully with `read:jira-work write:jira-work` scopes.
- `.secrets/jira_token.json` contains an `access_token` (no `refresh_token` expected).
- The tool gracefully requests reauthorization once expired.

## Usage

Generate or update a release snapshot and readiness report for a fix version.

```bash
python main.py --fixVersion "Mobilitas 2025.11.14"
```

Use the `--update` flag to refresh the snapshot even if one exists for today. When the `--fixVersion` flag is omitted, the application falls back to the `FIX_VERSION` environment variable.

### Output

- Snapshots are saved under `${ARTIFACT_ROOT}/snapshots/snapshot_<timestamp>.json`.
- Delta comparisons are written to `${ARTIFACT_ROOT}/snapshots/delta_<timestamp>.json`.
- Markdown readiness reports are generated in `${ARTIFACT_ROOT}/reports/readiness_report_<date>.md`.
- Run metadata is appended to `${ARTIFACT_ROOT}/logs/run_log.csv`.

## Future Extensions

- **Validation Document Creator** – produce checklists for deployment validation activities.
- **Release Notes Generator** – compile customer-facing release notes leveraging stored snapshots.

## Development Notes

- Follow PEP 8 style guidelines.
- Never log secrets or raw access tokens.
- All outbound HTTPS requests must verify certificates using `SSL_CERT_PATH` (automatically exported to `REQUESTS_CA_BUNDLE`).

## Continuous Integration

GitHub Actions run automated checks on pushes to `main` and all pull requests. The active
workflows include:

- **Python CI** – installs dependencies, runs Ruff linting, and executes the pytest suite.
- **Label Sync** – keeps repository labels aligned with `.github/labels.yml`.
- **Weekly Summary** – publishes Friday progress summaries under `reports/`.

No additional PR title validation or pre-commit automation runs in CI, keeping the
pipeline focused on essential quality and reporting tasks.

## 🧭 Ship Phase – Local Setup & Manual Testing

### Prerequisites
- Python 3.11+
- Access to Jira (OAuth 3LO App)
- GitHub Personal Access Token
- `requirements.txt` dependencies installed

### Environment Setup
1. Copy `.env.sample` to `.env` and fill in required fields.
2. Activate virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Verify directory structure under `/artifacts`.

### First Run
- **Step 1:** Authenticate with Jira:
  ```bash
  python -m modules.utils.oauth authorize
  ```
- **Step 1b:** (Rare) If your device cannot receive the automatic callback, copy the `?code=` value from the browser and run:
  ```bash
  python -m modules.utils.oauth complete <auth_code>
  ```
- **Step 2:** Capture a snapshot and build the readiness report:
  ```bash
  python main.py --fixVersion "Mobilitas 2025.11.14"
  ```
- **Step 3:** Validate data changes between two snapshots:
  ```bash
  python -m modules.snapshot_delta.analyzer --current <latest_snapshot.json> --previous <prior_snapshot.json>
  ```
- **Step 4:** (Optional) Export a Markdown delta report:
  ```bash
  python -m modules.snapshot_delta.analyzer \
    --current <latest_snapshot.json> \
    --previous <prior_snapshot.json> \
    --format markdown \
    --output artifacts/reports/delta.md
  ```

### Expected Outputs
- Snapshots under `/artifacts/snapshots/`
- Validation logs under `/artifacts/validation/`
- Reports under `/artifacts/reports/`
- Sanitized logs under `/artifacts/logs/`

### 🔒 Token Storage

Tokens are stored automatically under `.secrets/jira_token.json` and excluded from version control. Do **not** commit this file. It contains your encrypted Jira OAuth credentials.

## ⚠️ Troubleshooting OAuth Errors

### `AccessDeniedError: (access_denied) Unauthorized`
This occurs when Atlassian rejects the token exchange. Check:
- Your `.env` file contains a valid `JIRA_CLIENT_SECRET`
- The redirect URI matches **exactly** `http://localhost:8000/callback`
- You authorized the correct scopes in your Atlassian app:
  - `read:jira-work`
  - `write:jira-work`
  - `offline_access`
- Re-run a fresh authorization (old codes expire after 10 minutes)

### `client_secret may not be blank`
- Ensure `.env` includes a non-empty `JIRA_CLIENT_SECRET`
- Restart your terminal or run `source .env` before re-authorizing

### Debug Logs
Detailed logs and debug snapshots are written to:

```
/logs/oauth_debug_<timestamp>.json
```

Use these to inspect exact Atlassian responses for diagnostics.

### Next Steps
- Begin manual QA per `/docs/test_plan_ship_phase.md`
- Log defects/enhancements in GitHub Project #5
