# Slice 01 – OAuth Snapshot AEV Prompt

## Analyze
1. Inspect the repository for existing OAuth handlers, dotenv configuration, structured logging, and SSL certificate management modules.
2. Identify missing components or outdated implementations related to OAuth 3LO, certificate pinning via `${SSL_CERT_PATH}`, and artifact storage beneath `${ARTIFACT_ROOT}`.
3. Document configuration requirements, dependencies, and potential integration risks using `${ARTIFACT_ROOT}/01/analysis/oauth_surface_<timestamp>.md`.

## Execute
1. Implement OAuth 3-legged authorization, ensuring certificate validation leverages the corporate CA bundle referenced by `${SSL_CERT_PATH}`.
2. Introduce or update dotenv loading and structured logging modules to support secure credential handling.
3. Build a snapshot writer that outputs masked OAuth metadata to `${ARTIFACT_ROOT}/snapshots/snapshot_<timestamp>.json`.
4. Commit changes on branch `slice/01-oauth-snapshot`, following the `{type}: {summary}` convention.

## Validate
1. Run `pytest` and repository lint commands, capturing output artifacts under `${ARTIFACT_ROOT}/01/validation/`.
2. Verify that the OAuth snapshot JSON artifact exists and redacts secrets before storing it.
3. Prepare a pull request titled "Slice 01 – Build Phase" targeting branch `slice/01-oauth-snapshot`, summarizing validation results and linking artifacts.

## Critic Check
- Confirm compliance with `/prompts/MOP_build_phase.json`, including environment variable usage and artifact placement beneath `${ARTIFACT_ROOT}`.
- Ensure secrets from `JIRA_SECRET` and OAuth credentials remain masked across code, logs, and artifacts.
- Verify GitHub Project #5 fields are updated with Slice 01 status, branch, and `${FIX_VERSION}`.
