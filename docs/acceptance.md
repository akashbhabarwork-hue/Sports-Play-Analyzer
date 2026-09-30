# Acceptance Verification Log

This document records results from live and local reviewer acceptance runs (`/acceptance-check`).

## Reviewer Acceptance Scenarios
1. **Scenario 1 (Happy Path - User A):**
   - Log in with Google Account A.
   - Submit YouTube URL (`https://www.youtube.com/watch?v=...`) or sample test clip.
   - Live job status progresses: `queued` → `fetching`/`processing` → `succeeded`.
   - Annotated video plays and seeks cleanly.
   - Player selector opens heatmap and displays calculated tactical stats.
2. **Scenario 2 (Corrupt File Handling):**
   - Submit corrupt/malformed video file.
   - Clean, readable error returned (e.g. 422 `CORRUPT_FILE` or failed job with explanatory status). No worker crash or stuck state.
3. **Scenario 3 (User Isolation - User B):**
   - Log in as Google Account B.
   - Attempt to access User A's job details (`GET /jobs/<job_a_id>`, `/stats`, `/video`, etc.).
   - Server returns **404 Not Found**; User A's job never appears in User B's job list.

---

## Test Runs Log

| Date | Environment | Git SHA | Scenario 1 | Scenario 2 | Scenario 3 | Notes / Evidence |
|---|---|---|:---:|:---:|:---:|---|
| _(Pending)_ | local | - | ⏳ | ⏳ | ⏳ | Initial run scheduled after S8/S11 |
