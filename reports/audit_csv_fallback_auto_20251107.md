# Jira OAuth CSV Fallback (Automatic) – 2025-11-07

## Background
OAuth 2.0 (3LO) blocked at CSAA tenant level.
System now detects failure automatically and enables CSV Fallback Mode.

## Key Enhancements
- Auto-detection of OAuth failure
- CSV import with normalized schema
- Full artifact parity with API snapshots
- Structured logs and audit diagnostics

## Usage
1. Export Jira issues via JQL → “Export CSV (All fields)”
2. Place file at `artifacts/imports/jira_export.csv`
3. Run:

```
python main.py --fixVersion "Mobilitas 2025.11.14"
```

If OAuth is unavailable, the CLI now pauses until the CSV is detected and
records diagnostics at `logs/oauth_diagnostics_<timestamp>.json` plus a matching
markdown audit under `reports/audit_csv_fallback_auto_<timestamp>.md`.

Both files capture the trigger reason (`oauth_unavailable` or
`manual_override`), the imported row count, detected column headers, and the
SHA-256 checksum of the CSV used.

### Manual override

You can bypass the OAuth attempt entirely by supplying `--csv <path>` which
produces the same diagnostics and audit artifacts with trigger set to
`manual_override`.

## Next Steps
- Monitor Atlassian admin portal for 3LO whitelist approval
- Re-enable OAuth 3LO integration once authorized
- Review generated diagnostics to validate CSV provenance before sharing
