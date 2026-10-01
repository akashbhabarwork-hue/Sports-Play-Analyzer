# Sports Play Analyzer — Tickets

How to use: work top-to-bottom. Each ticket = one `/implement-ticket T-xxx` run = one commit.
Tick `[x]` when done and fill **Done notes** (the agent does this; you review).
Priority: `MUST` (needed for acceptance/brief) · `SHOULD` (quality) · `BONUS` (only if time left).
`[review-plan]` = agent must show an Implementation Plan and wait for your approval.
Estimates are *your hands-on time* with the agent writing code and you reviewing — total ≈ 10 h 30 m, so apply the cut order below if you fall behind.

## Suggested session plan (36 h window, ≈10 h work)
| Session | Target | Stages | ≈ Time |
|---|---|---|---|
| 1 | Foundation live on the internet, DB + queue | S0, S1, S2 | 2 h 40 m |
| 2 | Login works, both input paths create jobs | S3, S4 | 1 h 55 m |
| 3 | Pipeline produces stats + annotated video | S5, S6, S7 | 2 h 45 m |
| 4 | UI, hardening, CD, docs, acceptance | S8–S11 | 3 h 10 m |

**Cut order if behind:** T-092 → T-064 → T-101 rehearsal (keep the workflow) → simplify T-084
(no track overlay) → T-052 falls back to a single "all players" team heatmap (document it in ADR).

## Acceptance scenarios (the reviewers run these on the live URL)
- [ ] A1 Login → submit YouTube URL → job completes → annotated video plays → player heatmap opens
- [ ] A2 Corrupt file → clean failure
- [ ] A3 Second user → first user's job inaccessible

---

## S0 · Kickoff & decisions (20 m)

### [x] T-001 · Kickoff: repo scaffold and doc skeletons — `MUST` `10m`
- **Agent:** orchestrator
- **Why:** Brief §7 requires README (session log), docs/ADR.md, AI_USAGE.md, .env.example; §1 wants commits from the start.
- **Scope:** run `/kickoff`: git init, `.gitignore`, folders from rule 00 layout, doc skeletons, first session row.
- **Acceptance:** repo has the layout folders, README with session-log table, ADR/AI_USAGE templates, decisions.md, DEVLOG.md; first commit made.
- **Verify:** `git log --oneline | head`, `ls docs`
- **Done notes:** Repos, skeletons, and devlogs created. Missing tools (docker, ffmpeg) noted locally.

### [x] T-002 · Confirm open decisions — `MUST` `10m`
- **Agent:** architect
- **Depends on:** T-001
- **Why:** Brief §4 (justify model), §5 (host, sessions), ADR.
- **Scope:** confirm or change defaults and record D-001…D-006: (1) detector YOLOX-S ONNX (Apache-2.0) vs Ultralytics (AGPL); (2) host Fly.io + Neon + Tigris/R2; (3) server-side cookie sessions; (4) API paths `/api/jobs/...` with `/jobs/...` alias (brief uses `/jobs/{id}`); (5) Google as OAuth provider; (6) polling for live status.
- **Acceptance:** decisions.md has D-001…D-006 with option/why/consequence; rule 00 table updated if anything changed.
- **Verify:** read `docs/decisions.md`
- **Done notes:** Confirmed all 6 defaults. decisions.md is up to date.

## S1 · Foundation & first deploy (1 h 25 m)

### [x] T-010 · Backend skeleton, config, errors, /health, JSON logs — `MUST` `20m`
- **Agent:** backend-api
- **Depends on:** T-002
- **Why:** Ops: "/health endpoint", "Structured logs", "All configuration via env vars".
- **Scope:** `backend/app/config.py` (UPPERCASE env variables → frozen Settings, no argparse), `errors.py`, `wiring.py` (`build_container`), `entrypoints/api.py` (`create_app(container)`), error-envelope handler, JSON logging, `/health` with DB `SELECT 1` + `GIT_SHA`, `requirements.txt` + `requirements-dev.txt` pinned, `pyproject.toml` (ruff, pytest markers).
- **Acceptance:** `/health` returns `{"status":"ok","db":"ok","version":…}` or 503 when DB down; logs are JSON lines; design checker passes.
- **Verify:** `pytest -q backend/tests/unit`, design checker, `curl localhost:8000/health`
- **Done notes:** Built strict python functional core architecture, pinned deps, json logger, env configs, DB health check, and tests pass.

### [x] T-011 · Frontend skeleton — `MUST` `10m`
- **Agent:** frontend
- **Depends on:** T-002
- **Why:** UI requirements; CI needs lint/build.
- **Scope:** Vite React TS app, `react-router-dom`, `src/api.ts` envelope client, ESLint, `typecheck` script, dev proxy for `/api` and `/auth`; FastAPI serves `static/` build with SPA fallback.
- **Acceptance:** `npm run lint && npm run typecheck && npm run build` green; page loads via FastAPI at `/`.
- **Verify:** the three npm commands; open `http://localhost:8000/`
- **Done notes:** Initialized Vite React TS v5 app, configured dev proxy, added `typecheck`, setup routing, API client shell, and integrated static SPA serving in FastAPI.

### [x] T-012 · Dockerfile + one-command docker compose — `MUST` `20m`
- **Agent:** devops
- **Depends on:** T-010, T-011
- **Why:** Ops: "One-command Docker setup".
- **Scope:** multi-stage Dockerfile (node build → python slim + ffmpeg, non-root, HEALTHCHECK), compose with `db`, `migrate`, `web`, `worker` (placeholder loop for now), `blobs` volume; `.dockerignore`; `.env.example` with every variable documented.
- **Acceptance:** fresh clone + `cp .env.example .env` + `docker compose up --build` → `/health` ok.
- **Verify:** `docker compose up --build -d && curl -fsS localhost:8000/health`
- **Done notes:** Built multi-stage Dockerfile, docker-compose.yml with 4 services, and a dummy worker entrypoint. Docker verification skipped locally per request.

### [x] T-013 · CI workflow — `MUST` `15m` `[review-plan]`
- **Agent:** devops
- **Depends on:** T-012
- **Why:** CI/CD: "CI on every PR and push: lint, test, build"; least-privilege; pinned actions.
- **Scope:** `.github/workflows/ci.yml` from skill template; resolve real SHAs for every action (no guessing); postgres service; frontend job; docker build job.
- **Acceptance:** workflow green on GitHub; `permissions: {}` top-level; every `uses:` has a 40-char SHA + version comment.
- **Verify:** push branch, check Actions tab; `grep -n "uses:" .github/workflows/ci.yml`
- **Done notes:** `ci.yml` with backend / frontend / docker jobs, all actions SHA-pinned, `permissions: {}`. Docker job also runs the image against Postgres and smoke-tests `/health`. Fixed what CI exposed: `*.ts` gitignore rule (recreated `vite.config.ts`, `vite-env.d.ts`, `api.ts`), ruff lint/format, `STATIC_DIR` setting, uvicorn `--factory` target, no-op `typecheck` script. See D-007..D-009.

### [ ] T-014 · First deploy + day-1 YouTube spike — `MUST` `20m` `[review-plan]`
- **Agent:** devops
- **Depends on:** T-012
- **Why:** Live URL is mandatory; brief warns YouTube blocks cloud IPs — discover it on day 1, not at the end.
- **Scope:** create Fly app (web+worker process groups), Neon DB, storage bucket; manual `flyctl deploy`; set secrets; run `yt-dlp --dump-single-json <sample>` from the prod machine and record the result.
- **Acceptance:** `https://<app>/health` ok; decision D-xxx records whether YouTube works from prod and which mitigation (none/cookies/proxy) is planned.
- **Verify:** `curl -fsS https://<app>/health`
- **Done notes:** **Partial (owner deferred the deploy until the app is complete locally).** YouTube spike done from GitHub-hosted runners (datacenter IPs) via `youtube-spike.yml`: blocked with "Sign in to confirm you're not a bot", with and without a JS runtime — see D-010. Still open: Fly app + Neon + bucket + first deploy + `/health` (tracked as F-005, do before T-100).

## S2 · Database & job queue (55 m)

### [x] T-020 · Alembic + initial schema + indexes — `MUST` `20m` `[review-plan]`
- **Agent:** database
- **Depends on:** T-010
- **Why:** "Postgres, with versioned migrations", "Foreign keys, and at least one index you can justify", "Every job belongs to a user_id".
- **Scope:** Alembic setup, `adapters/db_tables.py` (Core Tables, naming convention), revision 0001 with `users, sessions, videos, jobs, job_results, player_tracks`, CHECK constraints, `ix_jobs_claimable` (partial), `ix_jobs_user_created`, `ix_sessions_user`; working downgrade.
- **Acceptance:** `alembic upgrade head` then `downgrade base` then `upgrade head` all succeed; decisions.md has the index justification lines.
- **Verify:** those three commands against compose DB
- **Done notes:** `db_tables.py` (Core tables, naming convention) + revision `0001` (6 tables, CHECKs, 3 indexes, full downgrade); `alembic.ini` + `migrations/env.py` read `DATABASE_URL`. upgrade → downgrade → upgrade verified on local Postgres 16; 13 integration tests (cycle, `alembic check` drift guard, every CHECK/unique/PK, cascade, index defs). Index EXPLAIN evidence in D-011. Also: pinned sqlalchemy/alembic, compose `migrate` no longer swallows failures, `.env.example` URL uses `+psycopg`, CI exit-5 allowance removed (F-004).

### [x] T-021 · User-scoped repositories — `MUST` `15m`
- **Agent:** database
- **Depends on:** T-020
- **Why:** "Users can only access their own jobs… enforced server-side".
- **Scope:** Protocols in `core/ports.py`; `PostgresUserRepo`, `PostgresSessionRepo`, `PostgresVideoRepo`, `PostgresJobRepo` (every read takes `user_id`), `PostgresResultRepo`.
- **Acceptance:** no job/video/result read method without `user_id` except worker-only methods (named `*_for_worker`); integration tests for upsert user + create/list jobs.
- **Verify:** `pytest -q backend/tests -m integration -k repo`
- **Done notes:** `core/models.py` dataclasses, 5 Protocols in `core/ports.py`, `adapters/pg_repos.py` (User/Session/Video/Job/Result repos), shared engine in `wiring.py`. Every video/job/result read is `user_id`-scoped; worker-only methods end `_for_worker`, enforced by `tests/unit/test_ports.py`. 7 repo integration tests (upsert, create/list newest-first, B cannot read A's job/video/result/tracks, unknown ids, worker methods, atomic `create_with_video`, session expiry/logout-all) — mutation-checked. See D-013.

### [ ] T-022 · Queue: claim, heartbeat, finish, fail, sweep — `MUST` `20m` `[review-plan]`
- **Agent:** database
- **Depends on:** T-021
- **Why:** "Workers claim jobs safely (SELECT … FOR UPDATE SKIP LOCKED)"; "Idempotent retry… no jobs stuck in processing".
- **Scope:** queries from skill `postgres-job-queue`; lease + attempts; `finish_job` single transaction (delete→insert→succeeded); `fail_job`; dead-letter sweep.
- **Acceptance:** tests: concurrent claim gives distinct jobs; expired lease reclaimed; attempts exhausted → `failed/WORKER_CRASHED`; double finish → same row counts; stale heartbeat → rowcount 0.
- **Verify:** `pytest -q backend/tests -m integration -k queue`
- **Done notes:** _

## S3 · Authentication & authorization (45 m)

### [ ] T-030 · Google OAuth (Authorization Code + PKCE) + sessions — `MUST` `30m` `[review-plan]`
- **Agent:** auth-security
- **Depends on:** T-021
- **Why:** "OAuth 2.0 login… Authorization Code flow with PKCE, using a vetted library"; "Secure session handling".
- **Scope:** Authlib Starlette client (S256), `/auth/login`, `/auth/callback`, `/auth/logout`; transient SessionMiddleware cookie for OAuth state only; our `__Host-sid` httpOnly Secure SameSite=Lax cookie; hashed session tokens; decision entry for the async-route exception.
- **Acceptance:** local login with a real Google test account works; cookie flags verified in devtools; logout invalidates the session row; no token/secret in logs.
- **Verify:** manual login; `pytest -q -k auth`
- **Done notes:** _

### [ ] T-031 · current_user, /api/me, CSRF origin check — `MUST` `10m`
- **Agent:** auth-security
- **Depends on:** T-030
- **Why:** server-side authz on every route; defence in depth for cookie auth.
- **Scope:** `current_user` dependency, `/api/me`, Origin + `X-Requested-With` check on unsafe methods.
- **Acceptance:** no cookie → 401 envelope; foreign Origin POST → 403; `/api/me` returns id/email/name.
- **Verify:** `pytest -q -k "me or csrf"`
- **Done notes:** _

### [ ] T-032 · Test harness: login_as + two-user clients — `MUST` `5m`
- **Agent:** qa
- **Depends on:** T-031
- **Why:** "At least one authorization test (user A cannot read user B's job)".
- **Scope:** conftest fixtures (`settings`, `migrated_db`, `container`, `client`, `login_as`), truncate between tests.
- **Acceptance:** a placeholder test creates two users with separate cookie jars and hits `/api/me` as each.
- **Verify:** `pytest -q -m integration -k two_users`
- **Done notes:** _

## S4 · Ingestion (1 h 10 m)

### [ ] T-040 · BlobStore (local + S3) — `MUST` `15m`
- **Agent:** backend-api
- **Depends on:** T-010
- **Why:** "Annotated video… saved to storage"; web and worker on different machines in prod.
- **Scope:** `BlobStore` Protocol (`put_file`, `get_to_path`, `open_range`/`presigned_url`, `delete`), `LocalBlobStore` (path-traversal safe keys), `S3BlobStore` (boto3, endpoint from env); registry in wiring by `BLOB_BACKEND`.
- **Acceptance:** unit test for key validation (`..` rejected); local adapter round-trip test.
- **Verify:** `pytest -q -k blob`
- **Done notes:** _

### [ ] T-041 · Upload endpoint with content validation — `MUST` `20m`
- **Agent:** backend-api (with auth-security review)
- **Depends on:** T-022, T-031, T-040
- **Why:** "File upload: Max 60 s and 100 MB"; "Check content by inspecting the file, not the extension… clean up temp files"; "returns a job_id immediately".
- **Scope:** `POST /api/jobs/upload`: Content-Length precheck, chunked copy with byte cap, magic-byte sniff (`core/file_sniff.py`), ffprobe check, store blob, insert video+job (config snapshot), 202 `{job_id}`; temp dir cleanup in `finally`.
- **Acceptance:** tiny.mp4 → 202; fake.mp4 → 415 UNSUPPORTED_FORMAT; corrupt.mp4 → 422 CORRUPT_FILE; oversize (test limit) → 413; long clip → 422 DURATION_EXCEEDED; temp dir empty after each.
- **Verify:** `pytest -q -k upload`
- **Done notes:** _

### [ ] T-042 · URL submit endpoint (syntactic SSRF rules) — `MUST` `10m`
- **Agent:** auth-security
- **Depends on:** T-041
- **Why:** "YouTube URL: fetched server-side"; "Host allowlist"; "Both paths must feed the same pipeline".
- **Scope:** `core/url_rules.py` normalise to canonical watch URL; `POST /api/jobs/url` inserts video(source_type=url)+job, 202. No network call in the request.
- **Acceptance:** unit table tests (accepted forms, rejected tricks incl. `youtube.com.evil.io`, userinfo, ports, http); endpoint returns 202 < 100 ms.
- **Verify:** `pytest -q -k url_rules`
- **Done notes:** _

### [ ] T-043 · Worker fetch stage: yt-dlp + SSRF-safe download — `MUST` `25m` `[review-plan]`
- **Agent:** auth-security
- **Depends on:** T-042
- **Why:** "Block private and internal IPs, including redirects"; "Hard duration cap"; "No shell string interpolation"; YouTube blocking handled gracefully.
- **Scope:** `core/net_rules.py` (`is_public_ip`), `adapters/ytdlp_fetcher.py` (arg list, `--use-extractors youtube`, verified flags, optional cookies/proxy from env), `adapters/safe_http_fetcher.py` (manual redirects ≤5, per-hop host+IP validation, byte cap), stderr → `YOUTUBE_BLOCKED` classifier, duration check → `DURATION_EXCEEDED`.
- **Acceptance:** IP table tests; redirect-to-metadata-IP test blocked; classifier test; manual run on a real short YouTube URL locally downloads ≤60 s file.
- **Verify:** `pytest -q -k "net_rules or fetch or classifier"`
- **Done notes:** _

## S5 · Tracking & metrics core — pure, no model (55 m)

### [ ] T-050 · Tracker (ByteTrack-style) + fixture tests — `MUST` `25m`
- **Agent:** cv-pipeline
- **Depends on:** T-010
- **Why:** "Track players across frames with stable IDs (IoU or ByteTrack-style)"; "Unit tests for the tracking… using fixture detections".
- **Scope:** `core/models.py` types, `core/tracking.py` (`iou_matrix`, `associate`, `update`), fixtures `tracks_*.json`, the 8 tests listed in skill `player-tracking`.
- **Acceptance:** all 8 tests pass in < 1 s; params come from `TrackerParams` built from Settings.
- **Verify:** `pytest -q backend/tests/unit -k track`
- **Done notes:** _

### [ ] T-051 · Metrics: distance, heatmaps, ball %, possession — `MUST` `20m`
- **Agent:** cv-pipeline
- **Depends on:** T-050
- **Why:** Metrics list in brief §6; "Unit tests for… metric maths".
- **Scope:** `core/metrics.py`, `core/heatmap.py`, `core/possession.py`; stats JSON builder matching the contract in skill `sports-metrics`.
- **Acceptance:** tests from skill (line distance, jitter, gap, heatmap edges, ball 25 %, possession hysteresis) pass.
- **Verify:** `pytest -q backend/tests/unit -k "metric or heatmap or possession"`
- **Done notes:** _

### [ ] T-052 · Team split by jersey colour — `MUST` `10m`
- **Agent:** cv-pipeline
- **Depends on:** T-051
- **Why:** "Per-player and team position heatmaps".
- **Scope:** pure k-means (k=2, fixed seed) on per-track colour features + `unknown` fallback; team heatmap aggregation.
- **Acceptance:** synthetic two-colour test → 2 teams; identical colours → `unknown`; team heatmap = sum of members.
- **Verify:** `pytest -q -k team`
- **Done notes:** _

## S6 · Worker pipeline (1 h 25 m)

### [ ] T-060 · ffmpeg frame reader/writer — `MUST` `15m`
- **Agent:** cv-pipeline
- **Depends on:** T-012
- **Why:** "Sample frames at a configurable FPS"; "Frames are streamed. The full video is never loaded into RAM"; arg arrays only.
- **Scope:** `adapters/ffmpeg_video.py`: probe, output size calc, streaming reader generator, encoder writer, stderr to temp files, kill/wait in finally.
- **Acceptance:** testsrc 2 s at fps 5 → 10 frames; encoded output probe-able; unit tests for size calc/read_exact.
- **Verify:** `pytest -q -m ffmpeg`
- **Done notes:** _

### [ ] T-061 · ONNX detector adapter + model in image — `MUST` `25m`
- **Agent:** cv-pipeline
- **Depends on:** T-060
- **Why:** "Detect players and the ball"; "Use pretrained models only"; licence justification.
- **Scope:** Dockerfile model download with verified URL + sha256; `adapters/onnx_detector.py` (letterbox, decode, NMS, class filter, one ball); output-shape assert; `FakeDetector`; pure NMS/decode tests.
- **Acceptance:** sample frame → persons detected (manual/`model` marker test); unit tests pass without the model.
- **Verify:** `pytest -q -k "nms or decode"`; `pytest -q -m model` locally
- **Done notes:** _

### [ ] T-062 · process_job service end-to-end — `MUST` `25m` `[review-plan]`
- **Agent:** cv-pipeline
- **Depends on:** T-022, T-043, T-051, T-052, T-061
- **Why:** Worker + Outputs sections of the brief; progress %.
- **Scope:** fetch (url) or load (upload) → probe → stream → detect → track → accumulate → draw → encode → upload `jobs/{id}/annotated.mp4` → `finish_job`; heartbeats with progress/stage; error-code mapping; temp cleanup.
- **Acceptance:** integration test with FakeDetector + tiny.mp4 → succeeded, stats JSON valid, player_tracks rows, blob exists; corrupt-but-sniffable file → failed/DECODE_ERROR.
- **Verify:** `pytest -q -m integration -k process_job`
- **Done notes:** _

### [ ] T-063 · Worker loop + crash-retry idempotency — `MUST` `15m`
- **Agent:** database
- **Depends on:** T-062
- **Why:** "Idempotent retry after a worker crash mid-job (no duplicate rows, no jobs stuck in processing)".
- **Scope:** `entrypoints/worker.py` (`run_once`, `run_forever`, SIGTERM handling, jittered polling); compose/Fly worker command.
- **Acceptance:** tests: crash simulation then retry → same row counts; exhausted attempts → failed; `docker compose up` processes a real upload end-to-end.
- **Verify:** `pytest -q -m integration -k "retry or idempot"`; manual compose run
- **Done notes:** _

### [ ] T-064 · Performance check & default tuning — `SHOULD` `5m`
- **Agent:** cv-pipeline
- **Depends on:** T-063
- **Why:** reviewers wait for the job live; ADR needs speed numbers.
- **Scope:** time a 60 s sample on prod worker size; adjust `SAMPLE_FPS`/`DETECT_INPUT_SIZE`/threads; record fps + wall time.
- **Acceptance:** decision entry with measured numbers; 60 s clip < ~3 min on prod.
- **Verify:** worker logs timing line
- **Done notes:** _

## S7 · Read API (25 m)

### [ ] T-070 · Job read endpoints — `MUST` `20m`
- **Agent:** backend-api
- **Depends on:** T-062
- **Why:** API list in brief: `GET /jobs/{id}`, `/stats`, `/players/{pid}`; UI needs list, video, heatmap.
- **Scope:** `GET /api/jobs`, `/api/jobs/{id}` (status, progress, stage, error), `/stats` (409 if not done), `/players/{pid}`, `/heatmap?team=`, `/video` (Range stream locally or 302 presigned ≤5 min); `/jobs/...` alias if decided in T-002; all user-scoped → 404.
- **Acceptance:** response shapes match skill `sports-metrics` contract; video seeks in browser.
- **Verify:** `pytest -q -m integration -k api_read`
- **Done notes:** _

### [ ] T-071 · Required authorization test (A vs B) — `MUST` `5m`
- **Agent:** qa
- **Depends on:** T-070, T-032
- **Why:** "At least one authorization test (user A cannot read user B's job)".
- **Scope:** the test from skill `testing-strategy` covering every job-scoped endpoint + list.
- **Acceptance:** passes; fails if any repository `user_id` filter is removed (try it once, revert).
- **Verify:** `pytest -q -m integration -k user_b_cannot`
- **Done notes:** _

## S8 · Frontend (1 h 10 m)

### [ ] T-080 · Login page + auth guard + layout — `MUST` `10m`
- **Agent:** frontend
- **Depends on:** T-031, T-011
- **Scope:** Login page, `/api/me` guard, header with user + logout.
- **Acceptance:** logged-out user redirected to login; logout returns to login.
- **Verify:** manual + `npm run build`
- **Done notes:** _

### [ ] T-081 · Submit page (upload + URL) — `MUST` `15m`
- **Agent:** frontend
- **Depends on:** T-080, T-041, T-042
- **Scope:** tabs, client pre-checks, server error messages inline, navigate to job on 202.
- **Acceptance:** corrupt file shows server message (A2); URL submit navigates instantly.
- **Verify:** manual A2 run locally
- **Done notes:** _

### [ ] T-082 · Job list with live status — `MUST` `10m`
- **Agent:** frontend
- **Depends on:** T-070, T-080
- **Scope:** table, status chips, progress bars, 2 s polling only while active, pause when tab hidden.
- **Acceptance:** progress moves live during a real job; polling stops when all jobs finished.
- **Verify:** manual + network tab
- **Done notes:** _

### [ ] T-083 · Job detail: video, stats, errors — `MUST` `15m`
- **Agent:** frontend
- **Depends on:** T-082
- **Scope:** video player, stats cards, error banner incl. "Upload instead" for `YOUTUBE_BLOCKED`, 404 page.
- **Acceptance:** A1 video plays + seeks; A3 shows "Job not found".
- **Verify:** manual
- **Done notes:** _

### [ ] T-084 · Heatmap view + player selector — `MUST` `20m`
- **Agent:** frontend
- **Depends on:** T-083
- **Scope:** canvas heatmap, pitch outline, legend, selector (All / Team A / Team B / #ids), optional track overlay.
- **Acceptance:** switching players redraws within 200 ms; keyboard accessible select.
- **Verify:** manual A1 final step
- **Done notes:** _

## S9 · Security hardening (25 m)

### [ ] T-090 · Rate limiting + active-job cap — `MUST` `10m`
- **Agent:** auth-security
- **Depends on:** T-041, T-042
- **Why:** "Rate limiting on submit endpoints".
- **Scope:** per-user limits on both submit endpoints, 429 + Retry-After envelope; max 3 active jobs per user.
- **Acceptance:** test: 11th submit in a minute → 429.
- **Verify:** `pytest -q -k rate`
- **Done notes:** _

### [ ] T-091 · Security headers + CORS + error audit — `MUST` `10m`
- **Agent:** auth-security
- **Depends on:** T-070
- **Why:** "restricted CORS, security headers".
- **Scope:** header middleware (CSP incl. storage origin for media, HSTS prod-only), CORS only from `CORS_ORIGINS`, no stack traces in responses, log redaction.
- **Acceptance:** header test on `/health` and `/`; UI still works under CSP (video, canvas).
- **Verify:** `pytest -q -k headers`; `curl -I`
- **Done notes:** _

### [ ] T-092 · Secret scanning in CI — `SHOULD` `5m`
- **Agent:** devops
- **Depends on:** T-013
- **Why:** "Nothing sensitive in git history".
- **Scope:** pinned gitleaks step over full history (`fetch-depth: 0`).
- **Acceptance:** CI green; scan output clean.
- **Verify:** Actions log
- **Done notes:** _

## S10 · CD, production config, rollback (40 m)

### [ ] T-100 · CD workflow — `MUST` `20m` `[review-plan]`
- **Agent:** devops
- **Depends on:** T-013, T-014, T-020
- **Why:** CD steps 1–5 exactly; GitHub Environments; least privilege; pinned actions.
- **Scope:** `cd.yml` from template with real SHAs; `production` environment secrets/vars; smoke test asserts new sha in `/health`.
- **Acceptance:** merge to main → green run; deliberately broken `/health` on a test branch merge makes the workflow fail (or explain the dry-run you did).
- **Verify:** Actions run URL in done notes
- **Done notes:** _

### [ ] T-101 · Rollback workflow + rehearsal — `MUST` `10m`
- **Agent:** devops
- **Depends on:** T-100
- **Why:** "Document a rollback path in the ADR".
- **Scope:** `rollback.yml`; rehearse once to previous sha and back.
- **Acceptance:** rehearsal recorded (shas, time taken) in decisions.md.
- **Verify:** Actions run
- **Done notes:** _

### [ ] T-102 · Production config for reviewers — `MUST` `10m`
- **Agent:** devops
- **Depends on:** T-030, T-100
- **Why:** "Live URL. It must work without any setup on our side."
- **Scope:** Google OAuth redirect URI for prod, consent screen **In production** (any Google account can log in), `COOKIE_SECURE=true`, storage bucket private, `min_machines_running=1`, YouTube mitigation env (if chosen).
- **Acceptance:** login works in an incognito window with an account never used before.
- **Verify:** manual
- **Done notes:** _

## S11 · Acceptance, docs, final review (55 m)

### [ ] T-110 · Live acceptance run — `MUST` `15m`
- **Agent:** qa
- **Depends on:** T-084, T-090, T-091, T-102
- **Scope:** `/acceptance-check live`; fix-forward tickets for any ❌.
- **Acceptance:** A1–A3 ✅ recorded in `docs/acceptance.md` with job ids and version sha.
- **Done notes:** _

### [ ] T-111 · Final ADR (1–2 pages) — `MUST` `15m`
- **Agent:** docs-scribe
- **Depends on:** T-110
- **Scope:** fill template from decisions.md: architecture, model justification, queue + index justification, sessions, SSRF, YouTube blocking, rollback, what was cut, more time.
- **Acceptance:** ≤2 pages; every brief-required topic present.
- **Done notes:** _

### [ ] T-112 · Final AI_USAGE.md — `MUST` `5m`
- **Agent:** docs-scribe
- **Scope:** tools, real key prompts, ≥2 real "AI was wrong" cases with how caught.
- **Done notes:** _

### [ ] T-113 · Final README — `MUST` `5m`
- **Agent:** docs-scribe
- **Scope:** run/test/deploy, env var table, API list, complete session log with totals.
- **Done notes:** _

### [ ] T-114 · Loom script — `MUST` `5m`
- **Agent:** docs-scribe
- **Scope:** `docs/loom-script.md` (architecture, data flow, one AI mistake) — record the 5-min video yourself.
- **Done notes:** _

### [ ] T-115 · Final whole-repo review — `MUST` `10m`
- **Agent:** reviewer
- **Depends on:** T-111…T-114
- **Scope:** `/review` on the whole repo; fix blockers; generate your "30-minute review" cheat sheet (top 10 questions + answers) in `docs/devlog/interview-prep.md`.
- **Done notes:** _

---

## BONUS (only after all MUST are ✅)
- [ ] **T-B01** Pitch-normalised distance via homography (4 clicked points) — cv-pipeline + frontend
- [ ] **T-B02** Upload progress bar (XHR progress events) — frontend
- [ ] **T-B03** Server-Sent Events for job status instead of polling — backend-api + frontend
- [ ] **T-B04** Annotated video at native fps (detect every k-th frame, interpolate boxes) — cv-pipeline
- [ ] **T-B05** Postgres-backed rate limiter for multi-instance web — auth-security
- [ ] **T-B06** Kalman filter / appearance re-ID to reduce ID switches — cv-pipeline

## Follow-ups (added by /review or acceptance runs)
- [ ] **F-001** (T-091) `serve_spa` joins the raw URL path onto the static dir without confirming the resolved path stays inside it — add a `realpath` containment check (path traversal).
- [ ] **F-002** (devops) Node 20 is past EOL — move the Dockerfile build stage and CI to Node 22 together.
- [ ] **F-003** (backend-api) `pydantic` is unpinned in `backend/requirements.txt` (sqlalchemy pinned in T-020); local dev ruff differs from the pinned 0.4.8 — pin and bump deliberately.
- [ ] **F-005** (devops, before T-100) Finish T-014: Fly app (web+worker), Neon, bucket, first deploy, `/health` live; re-run the YouTube spike from the prod worker (`fly ssh console`) and update D-010. Pick the mitigation (none / cookies / proxy) for A1.
- [x] **F-004** (T-020) Remove the "exit 5 = ok" allowance from the CI integration step once integration tests exist.
