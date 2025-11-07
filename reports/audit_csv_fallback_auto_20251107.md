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

→ Tool detects fallback automatically.

## Next Steps
- Monitor Atlassian admin portal for 3LO whitelist approval
- Re-enable OAuth 3LO integration once authorized
