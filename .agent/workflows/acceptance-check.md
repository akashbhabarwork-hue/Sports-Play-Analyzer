---
description: Walk through the three reviewer acceptance scenarios on local or live environment, guide the user through browser steps, verify via API, and record evidence in docs/acceptance.md.
---

# /acceptance-check [local | live]

Environment: `local` → http://localhost:8000 (after `docker compose up --build`); `live` → APP_URL.

1. Pre-flight: `curl -fsS <base>/health` → must show `status: ok` and expected version.
2. **Scenario 1 — happy path (user A)**. Ask the user to: log in with Google account A; submit
   the sample YouTube URL (from docs/acceptance.md); watch job list progress; open the job; play the
   annotated video (seek works); choose a player → heatmap renders. Ask for the job id.
   If it fails with `YOUTUBE_BLOCKED` on live: record it, then run the upload fallback with the same
   clip and note which mitigation (cookies/proxy) is configured.
3. **Scenario 2 — corrupt file**: upload `backend/tests/fixtures/corrupt.mp4` → expect immediate
   clear error (422 CORRUPT_FILE) or a job that fails with a readable message. Nothing stuck.
4. **Scenario 3 — isolation**: log in as Google account B (different browser/profile). Open
   `<base>/jobs/<A's job id>` and `<base>/api/jobs/<id>`, `/stats`, `/players/1`, `/video` → all 404;
   A's job not in B's list.
5. Extra: submit a >60 s YouTube URL → `DURATION_EXCEEDED`; 11 rapid submits → 429.
6. Record in `docs/acceptance.md`: date, env, version sha, each scenario ✅/❌, job ids, notes.
7. Any ❌ → create a follow-up ticket with repro steps and mark it MUST.
