# 🧪 Ship Phase Test Plan

## Objective
Validate end-to-end system behavior of Release Intelligence following the Guard Phase.
Ensure all automated modules perform correctly in a real environment.

## Test Environment
- Python 3.11+ (local virtualenv)
- `.env` configured with Jira & GitHub credentials
- All Guard Phase dependencies installed

---

## 1️⃣ Functional Test Cases

| ID | Area | Scenario | Expected Result | Type |
|----|-------|-----------|------------------|------|
| TC-01 | OAuth | Run `oauth_snapshot.py` with valid creds | Token created, auth successful | ✅ Positive |
| TC-02 | OAuth | Run with invalid `JIRA_CLIENT_SECRET` | Auth fails gracefully, error logged | ❌ Negative |
| TC-03 | Snapshot | Run `snapshot_analyzer` | Jira issues fetched, snapshot saved | ✅ Positive |
| TC-04 | Snapshot | Network disconnect mid-run | Recovers gracefully, logs warning | ❌ Negative |
| TC-05 | Validation | Missing required field in schema | Issue skipped, log warning only | ❌ Negative |
| TC-06 | Delta | Compare two snapshots | Delta file created with correct changes | ✅ Positive |
| TC-07 | Delta | Invalid snapshot path | Error handled cleanly, process continues | ❌ Negative |
| TC-08 | CI | Run `pytest` | All tests pass, coverage ≥70% | ✅ Positive |

---

## 2️⃣ End-to-End Scenarios

### Scenario A – Full Workflow Validation
1. Run OAuth setup.
2. Generate a snapshot.
3. Validate snapshot.
4. Modify Jira issue(s).
5. Generate second snapshot and run delta.
6. Verify:
   - Delta matches real Jira changes.
   - Logs are sanitized.
   - Reports generated.

### Scenario B – Recovery from Validation Failures
1. Temporarily remove a required field from the schema.
2. Run snapshot analyzer.
3. Observe that invalid records are skipped, no crash occurs.
4. Restore schema, rerun analyzer, confirm success.

### Scenario C – Security Compliance
1. Run system with DEBUG logging.
2. Inspect all logs under `/artifacts/logs/`.
3. Verify no PII, email, or tokens appear.
4. Run `bandit` and confirm clean report.

---

## 3️⃣ Defect Reporting Workflow
- Create a new GitHub issue per defect:
  - **Title:** `[QA] <short description>`
  - **Labels:** `bug`, `ship-phase`
  - **Attach:** Log snippets or screenshots
- Enhancements use label `enhancement` + `monitor-phase`.

## 4️⃣ Exit Criteria
- All critical bugs resolved.
- Minimum 2 successful end-to-end runs.
- Validation, CI, and sanitization pass.
- Guard → Ship → Monitor transition approved.
