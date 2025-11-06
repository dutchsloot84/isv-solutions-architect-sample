# Snapshot Delta Analyzer Example

This sample demonstrates how to diff two OAuth snapshot exports with the `modules.snapshot_delta.analyzer` CLI.
The analyzer loads two snapshot JSON files, computes field-level changes, masks sensitive values (for example `client_secret`),
and emits either JSON or Markdown summaries.

## Usage

```bash
python -m modules.snapshot_delta.analyzer \
  --current data/snapshots/snapshot_20240601T120000Z.json \
  --previous data/snapshots/snapshot_20240525T120000Z.json \
  --format markdown \
  --output data/reports/snapshot_delta_20240601.md
```

- `--format` controls whether the result is emitted as `json` or `markdown` (defaults to `json`).
- `--output` is optional; when omitted the report is printed to stdout.

## Sample Output (Markdown)

```
# Snapshot Delta – 2024.06

| Snapshot | File |
| --- | --- |
| Current | `current_snapshot.json` |
| Previous | `prev_snapshot.json` |

## Summary

- **Current Issues:** 2
- **Previous Issues:** 2
- **Added:** 1
- **Removed:** 1
- **Changed:** 1
- **Unchanged:** 0

### Field Changes
- `deployment_notes` updated 1 time(s)
- `fixVersions` updated 1 time(s)
- `status` updated 1 time(s)

## Added Issues

- `ABC-3` – PKCE enhancements _(status: In Progress)_

## Removed Issues

- `ABC-2` – Admin OAuth handshake _(status: Ready for Prod)_

## Changed Issues

- `ABC-1` – Login flow instrumentation
    - `deployment_notes`: Waiting on security review ➜ Security review completed
    - `fixVersions`: ['2024.05'] ➜ ['2024.06']
    - `status`: In Progress ➜ Ready for Prod
```

## Masked JSON Example

```
{
  "details": {
    "removed": [
      {
        "key": "ABC-2",
        "summary": "Admin OAuth handshake",
        "client_secret": "***masked***"
      }
    ]
  }
}
```

Sensitive fields such as secrets or tokens are redacted with `***masked***` to protect credentials in generated reports.
