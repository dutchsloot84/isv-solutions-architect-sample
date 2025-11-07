# Jira OAuth Offline Access Pain Point – 2025-11-07

## Tenant Capability Check
- Atlassian tenant rejected the `offline_access` scope during token exchange.
- Granular scopes `read:issue:jira write:issue:jira read:project:jira` remain functional.

## Outcome
- Fallback executed automatically after a `(access_denied)` response (HTTP 403).
- Session recovered with short-lived tokens (no refresh token granted).
- Diagnostic trail written to `logs/oauth_diagnostics_*.json` for auditability.

## Environment Snapshot
```
JIRA_CLIENT_ID=<redacted>
JIRA_SCOPES=read:issue:jira write:issue:jira read:project:jira offline_access
OAUTH_BROWSER_OPEN=false
```

## Lessons Learned
- Atlassian tenants may silently drop unsupported scopes; structured retries are essential.
- Persisting Phoenix-local timestamps in `.secrets/jira_token.json` simplifies incident reviews.
- Keep `.env` scoped to granular permissions and rely on runtime fallback when refresh tokens are unavailable.
