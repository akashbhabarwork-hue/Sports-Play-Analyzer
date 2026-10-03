# Development log

One entry per ticket, newest at the bottom. Written by the agent, reviewed by me.
Stage summaries live in `docs/devlog/stages/`.

---

## 2026-09-30 00:58 IST — T-001 Kickoff: repo scaffold and doc skeletons (agent: orchestrator)
**What changed:** Created `.gitignore`, `.env.example`, `README.md` (with session log initialized), `docs/ADR.md`, `AI_USAGE.md`, `docs/acceptance.md`, `docs/decisions.md`, and directory skeletons for `backend/`, `frontend/`, `.github/workflows/`.
**Why:** Assignment requirement §1 & §7 to establish project structure, session logging, and architecture documentation from the very first commit.
**Decisions:** D-001 through D-006 recorded in `docs/decisions.md`.
**Verification:** `git status` verifies all scaffolded paths; tooling check verified available compilers/interpreters.
**AI mistakes caught:** none.
**Explain-it-in-review:** "We set up an agentic, ticket-driven repository layout with strict separation between pure CV/domain logic, adapters, entrypoints, and frontend SPA, backed by a clear ADR and session log."
**Next:** T-002 Confirm open decisions & T-010 Backend skeleton.

---

## 2026-09-30 23:27 IST — T-002 Confirm open decisions (agent: architect)
**What changed:** Confirmed the 6 default architecture and design choices. Verified `docs/decisions.md` and ADR are up to date.
**Why:** Required by Brief §4 and §5 to lock in model choices, hosting, and architecture before implementation.
**Decisions:** D-001 (YOLOX-S), D-002 (Fly.io+Neon), D-003 (Cookie Sessions), D-004 (API aliases), D-005 (OAuth PKCE), D-006 (Polling) all confirmed without changes.
**Verification:** Read `docs/decisions.md`.
**AI mistakes caught:** none.
**Explain-it-in-review:** "We reviewed the default tech stack options against the assignment constraints and formally committed to them, ensuring our upcoming development is fully aligned with the requirements."
**Next:** T-010 Backend skeleton, config, errors, /health, JSON logs

---

## 2026-09-30 23:55 IST — T-010 Backend skeleton (agent: backend-api)
**What changed:** Added `backend` requirements, `pyproject.toml`, and the foundational API structure (`config.py`, `errors.py`, `wiring.py`, `api.py` and `db.py`) along with a working `/health` endpoint.
**Why:** Required by Ops for structured logging and env configuration.
**Decisions:** Unpinned `sqlalchemy` and updated `psycopg` to handle Python 3.14 on Windows.
**Verification:** Ran `pytest tests/unit/test_health.py` (Passed) and the Python backend design checker (Passed).
**AI mistakes caught:** Wrote explicit protocol inheritance (`class PostgresHealthCheck(HealthCheck):`), which the design checker blocked. Fixed it to use implicit composition.
**Explain-it-in-review:** "We laid out a strict functional core architecture for our FastAPI backend, mapping environment variables to a frozen `Settings` dataclass and handling dependency injection in `wiring.py`, ensuring business logic stays pure."
**Next:** T-011 Frontend skeleton

---

## 2026-10-01 00:36 IST — T-011 Frontend skeleton (agent: frontend)
**What changed:** Initialised a Vite + React + TypeScript app in `frontend/`, added `react-router-dom`, created an `api.ts` client to handle the `{error:{code,message}}` envelope, set up development proxies, and added a `typecheck` script. Modified `backend/app/entrypoints/api.py` to serve the frontend SPA build with a fallback route.
**Why:** Sets up the UI foundation and satisfies the requirement that FastAPI serves the production frontend build.
**Decisions:** Used Vite 5 (`create-vite@5`) since the latest Vite 6 (`create-vite@9`) requires a newer Node version than available in this environment. Mounted a static fallback route in FastAPI using `FileResponse` for everything except `api/` and `auth/`.
**Verification:** Ran `npm run lint`, `typecheck`, and `build` successfully, and added a pytest script to verify FastAPI correctly returns `index.html` on frontend routes.
**AI mistakes caught:** None in this ticket.
**Explain-it-in-review:** "We created a strict TypeScript React application configured to proxy requests to the backend during development, and set up our FastAPI backend to seamlessly serve the built SPA in production with proper routing fallback."
**Next:** T-012 Dockerfile + one-command docker compose

---

## 2026-10-01 01:27 IST — T-012 Dockerfile + one-command docker compose (agent: devops)
**What changed:** Created a multi-stage `Dockerfile` (Node for frontend -> Python slim for backend), `.dockerignore`, and `docker-compose.yml` with `db`, `migrate`, `web`, and `worker` services. Added a placeholder loop for the worker in `backend/app/entrypoints/worker.py` and wrapped the `migrate` command in a resilient shell command until Alembic is installed.
**Why:** Meets the "Ops: one-command Docker setup" requirement and prepares the image for production deployment.
**Decisions:** Used a shell wrapper for the `alembic` compose command (`sh -c "alembic upgrade head || echo 'Migrations skipped'"`) to prevent the container from crashing before Alembic is formally set up in T-020.
**Verification:** Skipped running `docker compose` per user request since Docker isn't installed locally.
**AI mistakes caught:** None.
**Explain-it-in-review:** "We created a production-ready, multi-stage Dockerfile that builds the React frontend and copies it into a Python backend container running as a non-root user. The local dev environment is spun up with a single `docker compose up` command covering the database, migrations, web API, and async worker."
**Next:** T-013 CI workflow

---

## 2026-10-01 17:10 IST — T-013 CI workflow (agent: devops)
**What changed:** Added `.github/workflows/ci.yml` (backend: ruff lint+format, design checker, unit + integration tests with a Postgres 16 service; frontend: lint, typecheck, build; docker: buildx build without push, then run the image against Postgres and smoke-test `/health` and the SPA root). Fixed everything a clean-checkout CI run would have failed on: `.gitignore` `*.ts` rule removed and the lost `frontend/vite.config.ts`, `src/vite-env.d.ts`, `src/api.ts` recreated; `typecheck` now `tsc -b`; ruff lint/format applied; `STATIC_DIR` setting so the image actually serves the SPA and tests don't need a build; uvicorn `--factory app.entrypoints.api:create_app` in Dockerfile and compose; pytest markers registered.
**Why:** CI/CD requirement "CI on every PR and push: lint, test, build", least privilege, pinned actions.
**Decisions:** D-007 (`*.ts` ignore), D-008 (`STATIC_DIR`), D-009 (CI shape, SHA pins).
**Verification:** ruff 0.4.8 check + format clean; design checker clean; `pytest -m "not integration and not model"` 5 passed; integration run exits 5 (no tests yet, allowed); frontend lint/typecheck/build green and typecheck proven to catch a planted error; `uvicorn --factory` started locally, `/health` 503 without DB, SPA route served; actionlint clean; every `uses:` SHA resolved via `git ls-remote` and confirmed to be a commit.
**AI mistakes caught:** `*.ts` gitignore swallowed TypeScript sources; non-existent `api:app` uvicorn target; typecheck checking zero files (AI_USAGE #2, #3).
**Explain-it-in-review:** "Every push and PR runs three least-privilege jobs with SHA-pinned actions: backend lint/design/tests against real Postgres, frontend lint/typecheck/build, and a Docker build that is actually started and health-checked — which is how we found the image could never have booted."
**Next:** T-014 First deploy + day-1 YouTube spike

---

## 2026-10-01 17:40 IST — T-014 YouTube spike (partial; deploy deferred) (agent: devops)
**What changed:** Added `.github/workflows/youtube-spike.yml` (manual or on change; least-privilege, SHA-pinned) that runs yt-dlp metadata + a ≤360p download from a GitHub-hosted runner, once without and once with the deno JS runtime, and reports WORKS / METADATA_ONLY / BLOCKED in the summary and log.
**Why:** The brief warns YouTube blocks cloud IPs and A1 depends on a YouTube URL; the owner deferred the deploy, and this session's network policy blocks both Fly and YouTube, so a datacenter-IP runner is the closest available stand-in for prod.
**Decisions:** D-010 — blocked from cloud IPs; baseline mitigation is a clean `YOUTUBE_BLOCKED` error with an upload suggestion; cookies vs proxy left to the owner.
**Verification:** run 36859379841 — both variants `ERROR: [youtube] jNQXAC9IVRw: Sign in to confirm you're not a bot`, metadata rc=1, download rc=1. First run hid stderr in the step summary only; fixed to echo it into the log.
**AI mistakes caught:** none.
**Explain-it-in-review:** "We tested YouTube from datacenter IPs on day 1 rather than at the end: it demands sign-in from cloud hosts regardless of yt-dlp's JS runtime, so the product degrades to a clear 'upload the file instead' error and the live demo needs cookies or a proxy."
**Next:** T-020 Alembic + initial schema (deploy itself tracked as F-005)

---

## 2026-10-01 18:45 IST — T-020 Alembic + initial schema + indexes (agent: database)
**What changed:** `backend/app/adapters/db_tables.py` (SQLAlchemy Core tables with a naming convention), `backend/alembic.ini`, `backend/migrations/` (`env.py` reads `DATABASE_URL`; tests can inject a URL), revision `0001_initial_schema` (users, sessions, videos, jobs, job_results, player_tracks; CHECKs; partial `ix_jobs_claimable`, `ix_jobs_user_created`, `ix_sessions_user`; full downgrade). `tests/integration/test_migrations.py` (13 tests). Pinned `sqlalchemy==2.1.1`, `alembic==1.20.0`; compose `migrate` is a plain `alembic upgrade head`; `.env.example` uses `postgresql+psycopg://`; CI integration step no longer tolerates "no tests".
**Why:** "Postgres with versioned migrations", "foreign keys and at least one index you can justify", "every job belongs to a user_id".
**Decisions:** D-011 (index justification with EXPLAIN), D-012 (schema conventions, extra CHECKs, pins).
**Verification:** local Postgres 16.14: `alembic upgrade head` → `downgrade base` → `upgrade head` all succeed; `alembic check` clean; integration 13 passed, unit 5 passed; drift test proven by adding a stray column (fails with `AutogenerateDiffsDetected`); ruff, design checker, actionlint clean; EXPLAIN on 20k seeded jobs shows each query using its index.
**AI mistakes caught:** imported a non-existent `sqlalchemy.Real` (it is `REAL`) — caught by the first DDL compile, fixed before any commit.
**Explain-it-in-review:** "The schema lives in one Core module and a reviewed Alembic revision that a test keeps in sync; constraints enforce the job state machine at the database level, and the partial claim index stays tiny because finished jobs fall out of it."
**Next:** T-021 User-scoped repositories

---

## 2026-10-01 19:30 IST — T-021 User-scoped repositories (agent: database)
**What changed:** `core/models.py` (User, NewVideo, Video, Job, JobResult, PlayerTrack), Protocols `UserRepo/SessionRepo/VideoRepo/JobRepo/ResultRepo` in `core/ports.py`, `adapters/pg_repos.py` with the five Postgres repos, `create_db_engine` shared by repos and `PostgresHealthCheck`, `Container` now carries the repos, `ExternalServiceError` (502) and the error handler uses `status_code`. Tests: `unit/test_ports.py`, `integration/conftest.py` (shared migrated DB), `integration/test_repos.py`.
**Why:** server-side per-user isolation (A3) is enforced in the data layer, not left to each route.
**Decisions:** D-013.
**Verification:** local Postgres 16: integration 20 passed (7 repo + 13 migration), unit 8 passed; ruff, design checker clean; `/health` ok with the new wiring. Mutation checks: splitting `create_with_video` into two transactions makes the atomicity test fail (orphan video); adding `JobRepo.get_any(job_id)` makes `test_ports` fail.
**AI mistakes caught:** the first atomicity test passed `config=None` expecting a NOT NULL violation, but SQLAlchemy stores it as JSON `null`, so nothing failed; then a non-serialisable value raised a Python `TypeError` rather than a DB error. Switched to a value Postgres itself rejects (NUL in jsonb) and proved the test with a mutation.
**Explain-it-in-review:** "Authorization lives in the SQL: every user-data query has `user_id` in its WHERE clause, cross-user reads come back empty so the API can 404, and a test fails the build if anyone adds an unscoped read."
**Next:** T-022 Queue: claim, heartbeat, finish, fail, sweep

---

## 2026-10-01 20:10 IST — T-022 Queue: claim, heartbeat, finish, fail, sweep (agent: database)
**What changed:** `backend/app/adapters/pg_queue.py` (`PostgresJobQueue`), `JobQueue` protocol and `JobOutcome` model, `LEASE_SECONDS` + `WORKER_ID` in `config.py`/`.env.example`, `Container.queue`; repo helpers in `pg_repos.py` made public (`db_errors`, `row_to`, `rows_to`) for reuse. `tests/integration/test_queue.py` (11 tests).
**Why:** safe concurrent claiming with SKIP LOCKED, crash recovery via leases, idempotent result writes, and no job stuck in `processing`.
**Decisions:** D-014 (queue semantics; handled errors are final, only crashes retry).
**Verification:** local Postgres 16: integration 31 passed, unit 8 passed; concurrency tests stable over 5 repeats; ruff + design checker clean. Mutation checks: removing `FOR UPDATE SKIP LOCKED`, the heartbeat ownership guard, the delete-before-insert, or the `max_attempts` filter each fails a test.
**AI mistakes caught:** none in this ticket.
**Explain-it-in-review:** "Workers claim with one SKIP LOCKED statement, hold a lease they keep alive with heartbeats, and can only write while they still own the job; if a worker dies the lease lapses and another worker retries, and after three tries a sweep marks the job failed — so nothing stays stuck in processing."
**Next:** S2 stage summary, then S3 — T-030 Google OAuth (Authorization Code + PKCE) + sessions

---

## 2026-10-01 21:00 IST — T-030 Google OAuth (Authorization Code + PKCE) + sessions (agent: auth-security)
**What changed:** `adapters/oauth_google.py` (Authlib, explicit Google endpoints), `services/auth.py` (`login_user` with rotation, `logout`, `user_for_token`), `core/sessions.py` (`hash_token`, `session_expiry`), `OAuthProfile` + `OAuthProvider` protocol, auth settings + production validation in `config.py`, `SessionMiddleware` (`oauth_tx`) and `/auth/login`, `/auth/callback`, `POST /auth/logout` in `api.py`, JSON access-log middleware; `ServiceUnavailableError`, `OAuthLoginError`. Deps `authlib`, `httpx2`, `itsdangerous`. `.env.example`/compose use `APP_ORIGIN`; compose no longer injects placeholder Google credentials; uvicorn runs `--no-access-log`.
**Threats blocked:** code interception (PKCE S256), forged callbacks (state, nonce, ID-token validation), XSS token theft (httpOnly), DB leak (hash-only tokens), session fixation (rotation), logout CSRF via GET (POST only), secrets/codes in logs.
**Decisions:** D-015.
**Verification:** unit 14 passed, integration 38 passed (52 total) on local Postgres 16; ruff + design checker clean. Live server: `/auth/login` → 302 to Google with S256 challenge, state, nonce and `oauth_tx` cookie (httponly, lax, 600 s); forged `state` → 303 `/login?error=oauth_failed` (`MismatchingStateError` logged by type only); logout 204. Mutations: removing rotation and storing the raw token each fail tests. **Not yet done:** real Google login — needs the owner's OAuth client.
**AI mistakes caught:** smoke test showed uvicorn's default access log writing `/auth/callback?code=…&state=…` — switched to `--no-access-log` + a path-only access-log middleware, with a test. Also a log-capture test initially saw nothing because `create_app()` replaces root handlers.
**Explain-it-in-review:** "Authlib does the OAuth: PKCE S256, state and nonce, and ID-token validation. We then issue our own random session token in an httpOnly __Host- cookie, store only its hash, rotate it on every login and delete it on logout; and we make sure the one-time OAuth code never lands in our logs."
**Next:** owner verifies real login; then T-031 current_user, /api/me, CSRF origin check

---

## 2026-10-01 23:30 IST — T-031 current_user, /api/me, CSRF origin check (agent: auth-security)
**What changed:** `make_current_user` dependency and an `/api` router that applies it; `GET /api/me` with `MeResponse` (`entrypoints/schemas.py`); CSRF middleware using `entrypoints/csrf.py:is_request_trusted`; `UnauthorizedError` (401) and `CsrfRejectedError` (403); stable UPPER_SNAKE `code` on every `AppError`, used by the error envelope; `TRUSTED_ORIGINS` setting (replaces `CORS_ORIGINS` in `.env.example`); frontend `api.ts` sends `X-Requested-With: fetch`. Tests: `unit/test_csrf.py`, `unit/test_api_routes.py`, `integration/test_me.py`; logout tests now send same-origin headers.
**Threats blocked:** unauthenticated API access, expired/forged sessions, CSRF (custom header + Origin/Referer allowlist on top of SameSite=Lax).
**Decisions:** D-016.
**Verification:** 76 tests pass (32 for `-k "me or csrf"`) on local Postgres 16; ruff + design checker clean; frontend lint/typecheck/build green. Live server: `/api/me` without cookie → 401 `UNAUTHORIZED`; plain `curl -X POST /auth/logout` → 403 `CSRF_REJECTED`; with Origin + header → 204.
**AI mistakes caught:** put the CSRF helper in `core/` importing `urllib.parse`; the design checker flags `urllib` as I/O — moved to `entrypoints/` where HTTP concerns belong.
**Explain-it-in-review:** "Every /api route hangs off one router that requires a valid session, and a test fails if one doesn't. Writes additionally need our custom header and our Origin, so a malicious page can't make the browser act with the user's cookie."
**Next:** T-032 Test harness: login_as + two-user clients

---

## 2026-10-01 23:55 IST — T-032 Test harness: login_as + two-user clients (agent: qa)
**What changed:** `backend/tests/integration/conftest.py` gained app-level fixtures (`settings`, `settings_factory`, `container`, `container_factory`, `make_client`, `client`, `login_as`, `csrf_headers`, `google`/`FakeGoogle`) and an autouse `clean_db` that truncates after every integration test. `test_me.py` and `test_auth_flow.py` now use them (≈40 lines of duplicated setup removed); repo/queue tests rely on `clean_db` instead of their own truncates. New `test_two_users.py`.
**Why:** A3 ("user B cannot read user A's job") and every job-scoped endpoint test from S4 on need two independent logged-in users in one test.
**Decisions:** `login_as` issues sessions through the real `services.auth.login_user` (same code as the OAuth callback, minus Authlib) — fast and faithful; the full callback path stays covered by `test_auth_flow.py`.
**Verification:** 79 passed (3 for `-k two_users`) on local Postgres 16; ruff + design checker clean. Mutation: disabling `clean_db` fails 5 tests through leaked rows, so test isolation is real.
**AI mistakes caught:** first version imported helpers with `from .conftest import …`, which fails because the test dirs are not packages — exposed them as `settings_factory` / `container_factory` fixtures instead.
**Explain-it-in-review:** "Each TestClient is its own browser with its own cookie jar; `login_as` mints a real session for it through the same service the OAuth callback uses, and every integration test starts from empty tables."
**Next:** S3 stage summary once T-030's manual Google login is confirmed; then S4 — T-040 BlobStore (local + S3)

---

## 2026-10-02 00:30 IST — T-040 BlobStore (local + S3) (agent: backend-api)
**What changed:** `BlobStore` protocol in `core/ports.py`; `core/blob_keys.py` (`validate_blob_key`, `upload_key`, `annotated_key`, `clamp_presign_ttl`); `adapters/blob_local.py` and `adapters/blob_s3.py`; `BLOB_STORES` registry and `Container.blobs` in `wiring.py`; blob/S3 settings with validation in `config.py`; `InvalidBlobKeyError`, `BlobNotFoundError`. `boto3` runtime dep, `moto` dev dep. `.env.example`/README storage docs fixed (`BLOB_LOCAL_DIR` said `/data/blobs`; Docker uses `/app/blobs`).
**Threats blocked:** path traversal and symlink escape on local storage, partial-file reads, long-lived public video links, credentials in logs.
**Decisions:** D-017.
**Verification:** 120 tests pass (41 for `-k blob`), ruff + design checker clean. Mutation: removing the local root-containment check fails the symlink-escape test.
**AI mistakes caught:** the first S3 test client was built without SigV4, so the presigned URL used the legacy `Expires=` format and the TTL assertion failed — tests now build the client through the production `make_s3_client`; one config test was written in a needlessly convoluted way and rewritten plainly.
**Explain-it-in-review:** "Storage is one protocol with a disk and an S3 implementation picked by config; every key is validated, local paths can't escape the root even through symlinks, writes are atomic, and videos are served via 5-minute signed links or streamed by the API."
**Next:** T-041 Upload endpoint with content validation

---

## 2026-10-02 01:15 IST — T-041 Upload endpoint with content validation (agent: backend-api, auth-security review)
**What changed:** `core/file_sniff.py`, `core/video_rules.py`, `VideoProbe` model and `VideoProber` protocol, `adapters/ffprobe.py`, `services/submit.py` (`submit_upload_job`), `entrypoints/limits.py` (`BodySizeLimitMiddleware`, `copy_capped`), `POST /api/jobs/upload` + `JobAccepted` schema, `NewVideo` gains app-generated `id` + probe fields (repo inserts them), new 413/415/422 errors, `MAX_UPLOAD_SIZE_BYTES` / `MAX_VIDEO_DURATION_SECONDS` / `UPLOAD_TMP_DIR` settings, `Container.prober`. `python-multipart` pinned; CI backend job installs ffmpeg.
**Threats blocked:** disk/memory exhaustion via huge or length-less uploads, extension spoofing, malformed/huge media, temp-file leaks, jobs referencing missing files.
**Decisions:** D-018; follow-up F-006 (aliases + validation-error envelope).
**Verification:** 148 tests pass (31 for `-k upload`) on local Postgres 16 with real ffprobe; ruff + design checker + actionlint clean. Mutations: never removing the temp dir fails 5 tests; skipping the sniff fails the fake-file case. Live server: valid clip 202 + one blob stored + empty temp dir; fake 415; missing CSRF headers 403.
**AI mistakes caught:** (1) an integration assertion that the body stream was cut off early could never hold — `TestClient` buffers the whole request body first — moved that proof to ASGI-level unit tests; (2) first draft of the size cap would have been turned into a 400 by FastAPI's form-parse error handling, so the middleware swallows the inner response and sends 413 itself; (3) `python-multipart` had never been added to requirements (only present in this environment).
**Explain-it-in-review:** "Uploads are judged by content, cheapest check first: size at the ASGI layer before parsing, magic bytes, then ffprobe for decodability and duration. The file is stored under a fresh id before the job row exists, so the worker never sees a job without its video, and the temp dir is always removed."
**Next:** T-042 URL submit endpoint (syntactic SSRF rules)

---

## 2026-10-02 01:45 IST — T-042 URL submit endpoint (syntactic SSRF rules) (agent: auth-security)
**What changed:** `core/url_rules.py` (`canonicalize_youtube_url`, `YouTubeRef`), `UrlNotAllowedError` (422 `URL_NOT_ALLOWED`), `services/submit.py: submit_url_job`, `UrlSubmit` schema and `POST /api/jobs/url`. Design checker (`.agent/skills/python-backend-design/scripts/check_design.py`) now treats `urllib.parse` as pure.
**Threats blocked:** SSRF via non-YouTube hosts, IP literals, look-alike/suffix hosts, userinfo and backslash parser differentials, odd ports, non-https schemes; raw user strings reaching yt-dlp.
**Decisions:** D-019.
**Verification:** 220 tests pass (72 for url_rules/url_submit) on local Postgres 16; ruff + design checker clean. Mutations caught: suffix host matching, dropped userinfo check, any port, storing the raw URL. Live: 202 in ~8 ms warm; `youtube.com.evil.io` → 422; only the canonical URL stored.
**AI mistakes caught:** none in the code; the design checker's blanket `urllib` rule was a false positive for a pure parser — fixed narrowly in the checker rather than moving the module out of `core/`.
**Explain-it-in-review:** "A submitted link must be https, on one of four exact YouTube hostnames, with no credentials or odd port; we pull out the 11-character video id and rebuild the URL ourselves, so only that canonical URL is ever stored or passed to yt-dlp. DNS and redirect checks happen later, in the worker, right before any download."
**Next:** T-043 Worker fetch stage: yt-dlp + SSRF-safe download

---

## 2026-10-02 02:45 IST — T-043 Worker fetch stage: yt-dlp + SSRF-safe download (agent: auth-security)
**What changed:** `core/net_rules.py` (`is_public_ip`, `unwrap_ipv4`, `is_allowed_media_host`), `core/ytdlp_errors.py` (`classify_ytdlp_failure`), `check_remote_media` in `core/video_rules.py`, `MediaInfo` model + `MediaInfoFetcher`/`MediaDownloader` protocols, `adapters/ytdlp_fetcher.py`, `adapters/safe_http_fetcher.py`, `services/fetch.py` (`fetch_url_video`), `validate_video_file` shared with uploads, `YTDLP_COOKIES_B64`/`YTDLP_PROXY` settings, `Container.media_info`/`downloader`, `backend/scripts/fetch_check.py`, `YouTubeBlockedError`/`DownloadFailedError`. `yt-dlp[default,deno]==2026.8.19` pinned.
**Threats blocked:** SSRF through DNS, redirects and IPv6-wrapped IPv4; command/option injection into yt-dlp; huge/long/live downloads; cookie secret leakage; ambient proxy env hijacking the downloader.
**Decisions:** D-020 (owner: baseline + optional cookies/proxy; video-only ≤720p; ship deno; owner runs the real-URL check).
**Verification:** 313 tests pass (103 for this ticket), ruff + design checker clean, no network used in tests. Mutations caught: no per-hop IP check, client-side redirect following, `any` instead of `all` DNS answers, no IPv6 unwrapping (via a direct unwrap test), cookie file left behind, no `--` before the URL. yt-dlp flags and the `youtube` extractor name verified against the installed version; a non-YouTube URL is refused by yt-dlp itself before any network access. `fetch_check.py` here fails cleanly with DOWNLOAD_FAILED (session has no YouTube access).
**AI mistakes caught:** (1) a classifier test expected a private video to be `YOUTUBE_BLOCKED` — wrong; it is `DOWNLOAD_FAILED` (uploading wouldn't help either); (2) the first "no unwrapping" mutation survived because this Python's `ipaddress` already treats those ranges as non-global — added a direct `unwrap_ipv4` test so the defence-in-depth path is covered; (3) one mutation produced a syntax error instead of a behaviour change and had to be redone; (4) `IPv6Address.ipv4_compat` doesn't exist on Python 3.11 — replaced with an explicit ::/96 check.
**Explain-it-in-review:** "yt-dlp only tells us what to download; our own client downloads it, refusing any hop that isn't https on a Google video host whose every DNS answer is public, and it never follows redirects on its own. Then the file goes through exactly the same checks as an upload."
**Next:** owner runs `scripts/fetch_check.py` locally; S4 stage summary; then S5 — T-050 tracker

---

## 2026-10-02 10:45 IST — T-050 Tracker (ByteTrack-style) + fixture tests (agent: cv-pipeline)
**What changed:** `Box`, `Detection`, `Track`, `TrackerParams`, `TrackerState` in `core/models.py`; `core/tracking.py` (`iou_matrix`, `associate`, `predict`, `update`, `player_detections`, `pick_ball`); tracker settings (`TRACKER_HIGH_THRESH`, `TRACKER_LOW_THRESH`, `TRACKER_IOU_THRESHOLD`, `TRACKER_LOW_IOU`, `TRACKER_MAX_AGE`, `TRACKER_MIN_HITS`, `MIN_BOX_AREA_REL`) with range validation; `wiring.tracker_params`; fixtures `tests/fixtures/tracks_*.json` + generator; `numpy` and `scipy` pinned. Also wrote the S4 stage summary.
**Threats blocked:** n/a (pure maths); bad tracker config fails at startup instead of silently mis-tracking.
**Decisions:** D-021 (Hungarian via scipy, low boxes only extend established tracks, `TRACKER_MAX_AGE` 30 → 10, detector must keep boxes down to the low threshold).
**Verification:** 33 tracker tests in ~0.1 s; full suite, ruff and design checker clean. 7 mutations caught; the 8th ("tentative tracks join stage 2") survived at first and got its own test.
**AI mistakes caught:** the first test set did not cover tentative tracks being fed by low-confidence boxes — found by the mutation run, test added.
**Explain-it-in-review:** "Each frame we predict where every player should be, match confident boxes to those predictions with the Hungarian algorithm, then let weak boxes keep already-known players alive. A player gets a number only after three sightings, so one-frame false positives never show up and ids stay 1..N."
**Next:** T-051 Metrics: distance, heatmaps, ball %, possession

---

## 2026-10-02 11:15 IST — T-051 Metrics: distance, heatmaps, ball %, possession (agent: cv-pipeline)
**What changed:** `FrameObservation`, `MetricsParams`, `MatchMetrics` in `core/models.py`; `core/heatmap.py`, `core/possession.py`, `core/metrics.py` (`build_stats` → stats JSON + `player_tracks` rows); `JITTER_PX`, `HEATMAP_GRID_W/H`, `POSSESSION_DIST_RATIO`, `POSSESSION_MIN_FRAMES` settings with validation; `wiring.metrics_params`.
**Threats blocked:** n/a (pure maths); bad metric config fails at startup.
**Decisions:** D-022 (one pass at the end; jitter measured from the last counted point; loose ball is a hysteresis candidate; stats carry team/all heatmaps).
**Verification:** 33 metric tests in < 1 s; full suite, ruff and design checker clean. 9 mutations caught (no jitter filter, reference moved every frame, gap bridged, no hysteresis, no reset after a long ball gap, reset on any gap, no possession distance limit, no heatmap clamp, wrong ball-% denominator).
**AI mistakes caught:** (1) the skill's literal jitter rule ("skip steps < JITTER_PX") would give a player walking 1 px per sampled frame zero distance — replaced with a dead-band from the last counted point and a test for the slow walker; (2) my first gap-bridging test had wrong arithmetic (the bridged step didn't move), so it asserted the wrong number — fixed the test data so the bridged step is a real 100 px jump.
**Explain-it-in-review:** "The worker records what it saw each frame; at the end, plain functions turn that into distance (ignoring detector wobble), heatmaps, ball visibility and possession, where the ball has to stay with a new player for three frames before it changes hands."
**Next:** T-052 Team split by jersey colour

---

## 2026-10-02 11:45 IST — T-052 Team split by jersey colour (agent: cv-pipeline)
**What changed:** `core/teams.py` (`torso_region`, `torso_pixels`, `rgb_to_hsv`, `colour_feature`, `kmeans_two`, `assign_teams`); `TEAM_MIN_SEPARATION` setting with validation; `core/metrics.py` now takes team labels from `core/teams.py`. S5 stage summary written.
**Threats blocked:** n/a (pure maths).
**Decisions:** D-023 (HSV-cone feature with value, median per crop and per track, farthest-point 2-means, A = lowest id, `unknown` fallbacks).
**Verification:** 15 team tests in ~0.3 s; full suite, ruff and design checker clean. 7 mutations caught (raw hue, no value channel, no separation check, A not lowest id, mean instead of median ×2, unsorted ids); the two median mutations survived at first and got robustness tests.
**AI mistakes caught:** (1) the skill's hue+saturation feature can't tell white from black kits and splits reds across the 0°/360° wrap — switched to the HSV cone with value; (2) a crop-clamping test used a box whose torso lay completely outside the frame, so it tested the wrong case — fixed the box.
**Explain-it-in-review:** "We take a small crop of each player's shirt, turn it into one colour point that treats hue as an angle and keeps brightness, and split the players into two groups. If the groups are too close, we say 'unknown' rather than guess."
**Next:** S6 — T-060 ffmpeg frame reader/writer

---

## 2026-10-02 11:21 IST — T-060 ffmpeg frame reader/writer (agent: cv-pipeline)
**What changed:** new `adapters/ffmpeg_video.py` (`read_exact`, `FfmpegFrameReader.frames()` generator, `FfmpegVideoEncoder.encode(frames)`); new `core/video_frames.py` (`output_size`, `expected_frames`); `FrameSize` model; `VideoProbe.rotation` read by the ffprobe adapter; `FrameReader`/`VideoEncoder` ports; `DecodeError` (`DECODE_ERROR`); settings `SAMPLE_FPS`, `MAX_FRAME_SIDE`, `ENCODE_CRF`, `ENCODE_PRESET` (+ validation, `.env.example`); `ffmpeg` pytest marker.
**Why:** "Sample frames at a configurable FPS"; "frames are streamed, the full video is never loaded into RAM"; argument lists only.
**Decisions:** D-024 (size computed in Python so each frame is exactly W*H*3 bytes; iterator-fed encoder; stderr to temp files; kill+wait in `finally`; ffmpeg tests in `tests/unit` behind a marker).
**Verification:** `pytest -q -m ffmpeg` → 11 passed; frame-geometry + `read_exact` tests → 18 passed; adapter coverage 96 % (only timeout branches uncovered); ruff, format and design checker clean; full unit suite 357 passed, 1 failed (`test_fetch_ytdlp_cookies_file_is_private_and_deleted` — Windows ignores chmod 0600, pre-existing, passes on Linux CI). Mutation: disabling kill/reap makes `test_reader_closed_early_kills_ffmpeg` fail.
**AI mistakes caught:** banker's rounding in the even-size calculation (test went red) and a Windows-only `OSError` the encoder didn't map — see AI_USAGE #6.
**Explain-it-in-review:** "ffmpeg decodes the clip at 5 frames a second and pipes raw pixels to us; we know the exact frame size, so we read exactly that many bytes per frame and only ever hold one frame. The encoder pulls frames from a generator, so detection, drawing and encoding all happen one frame at a time, and if anything fails we kill ffmpeg in a `finally`."
**Next:** T-061 ONNX detector adapter + model in image

---

## 2026-10-02 11:45 IST — T-061 ONNX detector adapter + model in image (agent: cv-pipeline)
**What changed:** pure `core/detection.py` (`yolox_num_anchors`, `decode_yolox`, `letterbox_ratio`, `nms`, `select_detections`); `adapters/onnx_detector.py` (`letterbox`, `OnnxYoloxDetector` with startup I/O-shape check); `adapters/fake_detector.py`; `Detector` port; `DetectorParams`; `ModelError` (`MODEL_ERROR`); settings `MODEL_PATH`, `DETECT_INPUT_SIZE`, `BALL_CONF_THRESHOLD`, `NMS_THRESHOLD`, `DETECT_MAX_CANDIDATES`, `ORT_THREADS`; `requirements.txt` + `onnxruntime==1.30.0`, `opencv-python-headless==5.0.0.93`; Dockerfile downloads YOLOX-S and verifies sha256; `tests/fixtures/people.jpg` (Apache-2.0 crop, attributed); `.env.example`/README env docs cleaned up.
**Why:** "Detect players and the ball"; "Use pretrained models only"; licence justification.
**Decisions:** D-025 (YOLOX-S Apache-2.0 vs AGPL Ultralytics; verified URL + sha256; per-class scores; players down to `TRACKER_LOW_THRESH`; one ball; startup shape check; generic user-facing errors).
**Verification:** `pytest -q -k "nms or decode"` → 13 passed; detector tests 26 passed incl. `-m model` with real weights (≥3 confident players on the fixture; ~160 ms/frame); core 100 %, adapter 92 % coverage; ruff, format, design checker clean; unit suite 383 passed, 1 failed (pre-existing Windows-only chmod test). Docker build not run locally (no Docker) — CI's docker build job is the check.
**AI mistakes caught:** duplicate `SAMPLE_FPS` and missing README rows from T-060 (AI_USAGE #7); first `ModelError` messages leaked the model path to users — found in self-review, now logged only.
**Explain-it-in-review:** "We use YOLOX-S, a pretrained Apache-licensed detector, through ONNX Runtime on CPU. The image downloads it at build time and checks its hash. The model gives raw grid predictions; plain numpy code turns them into boxes, keeps every plausible player for the tracker, and keeps just the single most likely ball."
**Next:** T-062 process_job service end-to-end `[review-plan]`

---

## 2026-10-02 12:25 IST — T-062 process_job service end-to-end (agent: cv-pipeline)
**What changed:** new `services/process.py` (`process_job`, `PipelinePorts`, `ProcessConfig`, `_annotated_frames`), `core/pipeline.py` (progress bands, team sampling cap, config snapshot), `adapters/opencv_annotator.py`; `FrameAnnotator` port; `PipelineParams` model; `LeaseLostError`; settings `HEARTBEAT_EVERY_FRAMES`, `TEAM_SAMPLE_EVERY`, `TEAM_MAX_SAMPLES` (+ `.env.example`, README); `wiring.py` `pipeline_params`, `detector_params`, `process_config`, `build_detector`, `build_pipeline_ports`; tests `tests/unit/test_pipeline.py`, `tests/unit/test_process_job.py`, `tests/integration/test_process_job_pg.py`, shared `tests/pipeline_helpers.py`; follow-up F-007.
**Why:** Worker + Outputs sections of the brief, progress %, readable failures (A2); the step that makes scenario A1 produce a video and stats.
**Decisions:** D-026 (one streamed pass; final vs transient failures; lost lease = stop without writing; BGR→RGB before team colours; boxes coloured by id). Plan reviewed and approved before coding (`[review-plan]`).
**Verification:** `pytest -q -k "process_job or pipeline"` locally → 20 passed (2 Postgres tests skipped: no DB); mutations "ignore lost lease" and "storage outage is final" both caught; full unit suite 402 passed, 1 failed (pre-existing Windows-only chmod test); ruff, format, design checker clean. **Not run locally:** `pytest -q -m integration -k process_job` — Docker/Postgres deferred to the end by the owner, so CI is its first run.
**AI mistakes caught:** two test modules named `test_process_job.py` collided at collection (AI_USAGE #8). De-risked before coding: confirmed a truncated `+faststart` MP4 passes ffprobe but decodes to zero frames.
**Explain-it-in-review:** "The worker streams the video through ffmpeg; for each frame it detects, tracks, notes positions and shirt colours, draws the boxes and hands the frame straight to the encoder — so we never hold the video in memory. If the input is bad the job fails with a clear message; if something like storage hiccups, we let the lease expire so another attempt retries it, and after three tries it's marked crashed."
**Next:** T-063 Worker loop + crash-retry idempotency (database)

---

## 2026-10-02 12:41 IST — T-063 Worker loop + crash-retry idempotency (agent: database)
**What changed:** real `entrypoints/worker.py` replacing the placeholder sleep loop (`run_once`, `run_forever`, signal handlers, `main`); logging setup moved from `api.py` to shared `entrypoints/log_config.py`; `core/pipeline.poll_delay`; `WORKER_POLL_SECONDS` (+ `.env.example`, README); compose worker: healthcheck disabled, `stop_grace_period: 60s`, `restart: unless-stopped`; tests `tests/unit/test_worker.py`, `tests/integration/test_worker_retry.py`.
**Why:** "Idempotent retry after a worker crash mid-job (no duplicate rows, no jobs stuck in processing)".
**Decisions:** D-027 (poll with jitter via `Event.wait`; finish current job on SIGTERM; never die on a job error or DB blip; model checked at startup; no early-release call).
**Verification:** unit 13 passed locally; worker started without a model → JSON error log + exit 1; full unit suite 415 passed, 1 failed (pre-existing Windows-only chmod test); ruff, format, design checker clean. **Not run locally:** `pytest -q -m integration -k "retry or idempot"` (CI is the first run) and the `docker compose up` end-to-end upload — queued for the final Docker pass (owner's decision).
**AI mistakes caught:** a DB outage during an idle poll would have killed the worker (AI_USAGE #9) — found in self-review, regression tests written first, then fixed.
**Explain-it-in-review:** "The worker loop is deliberately boring: sweep jobs that ran out of attempts, claim the next one with SKIP LOCKED, process it, repeat. The safety is in the queue — leases, attempt counts and a one-transaction finish — so if the worker dies anywhere, the lease runs out and another worker redoes the job from scratch without duplicating anything. On SIGTERM it finishes the job it has, then exits."
**Next:** T-070 Job read endpoints (backend-api) — T-064 (SHOULD) needs the prod worker, so it waits for the deploy.

---

## 2026-10-02 12:59 IST — T-070 Job read endpoints (agent: backend-api)
**What changed:** `services/read_job.py` (list, get, stats, player, heatmap, video access), pure `core/http_range.py`, errors `NotFoundError`/`JobNotReadyError`/`RangeNotSatisfiableError`, response schemas (`JobSummary`, `JobDetail`, `JobList`, `VideoInfo`, `PlayerDetail`, `Heatmap`), `api.py` job routes on one router mounted at `/api/jobs…` and `/jobs…` (aliases), video route with Range streaming or presigned 302, upload alias under the body-size limit, `serve_spa` leaves `/jobs…` to the API; tests `tests/unit/test_http_range.py`, `tests/unit/test_read_api.py` (+ shared `tests/api_fakes.py`), `tests/integration/test_api_read.py`.
**Why:** brief API list + UI needs; scenarios A1 (video, heatmap) and A3 (404 for other users).
**Decisions:** D-028 (404 before 409; presigned 302 on S3 vs Range streaming locally; aliases + SPA under `/app/…`, chosen by the owner in plan review).
**Verification:** plan approved first (touches authorization). Locally `pytest -q -k "http_range or read_api"` → 45 passed; full unit suite 460 passed, 1 failed (pre-existing Windows-only chmod test); ruff, format, design checker clean. **Not run locally:** `pytest -q -m integration -k api_read` (3 tests, CI first run). Browser seek check comes with the frontend (T-083).
**AI mistakes caught:** design checker flagged `JobDetail(JobSummary)` inheritance (house rule) → fields spelled out; a no-op assertion in the list test removed during self-review.
**Explain-it-in-review:** "Every read starts by looking the job up together with your user id, so somebody else's job looks exactly like a job that doesn't exist — 404. Results before the job finishes are a 409. The video is either a 5-minute signed link to object storage or, locally, streamed by us with Range support so the player can seek."
**Next:** T-071 Required authorization test (A vs B) (qa)

---

## 2026-10-02 13:02 IST — T-071 Required authorization test (A vs B) (agent: qa)
**What changed:** `tests/integration/test_authz_user_b_cannot.py` (Postgres, two browsers via `make_client` + `login_as`) and `tests/unit/test_authz_matrix.py` (same matrix over user-scoped in-memory repos, runs locally). Matrix: detail, stats, players/1, heatmap (all, A), video × `/api/jobs` and `/jobs` aliases; A's finished job → A 200, B 404 `NOT_FOUND`; A's queued job → B's response is byte-identical to a random id (404, never the 409 A would see); A's jobs absent from B's list; B's ranged video request → 404 with no bytes.
**Why:** brief: "At least one authorization test (user A cannot read user B's job)"; scenario A3.
**Decisions:** none new (D-028 ordering: ownership check before readiness check is what makes B's 404 indistinguishable).
**Verification:** `pytest -q -k user_b_cannot` locally → 27 passed (26 Postgres cases skipped: no DB, CI runs them). Mutations: `JobRepo.get` without `user_id` → 14 failures; `list_for_user` without `user_id` → 2 failures; `ResultRepo` without `user_id` alone → **not caught at the API level, by design** (every read checks job ownership first, so nothing leaks); that SQL filter is covered by T-021's `tests/integration/test_repos.py::test_other_user_cannot_read_job_video_or_results`. Re-running these mutations against the real SQL repos is **queued for the Docker pass**.
**AI mistakes caught:** none.
**Explain-it-in-review:** "Two browsers, Alice and Bob. Bob tries every URL for Alice's job, on both the /api and the short /jobs paths: always 404, the same answer as for a made-up id — even for a job that isn't finished, where Alice herself would get 409. I checked the test actually bites by removing the user filter from the job lookup and the list: it fails."
**Next:** S7 complete → stage summary; then T-080 Login page + auth guard + layout (frontend)

---

## 2026-10-02 13:18 IST — T-080 Login page + auth guard + layout (agent: frontend)
**What changed:** `src/types.ts` (mirrors backend schemas), `src/api.ts` (typed `api` client on the existing envelope-aware `apiFetch`, friendly 413/429 text), `src/auth.tsx` + `src/useAuth.ts` (session from `GET /api/me`, `RequireAuth`), `src/components/Layout.tsx`, `src/pages/LoginPage.tsx`, `src/logic/login.ts`, `src/App.tsx` routes under `/app/…`, new `index.css`/`App.css`, page title; Vitest 3.2.7 (`npm test`) with `src/api.test.ts`, `src/logic/login.test.ts`; CI frontend job runs `npm test`.
**Why:** "OAuth 2.0 login"; logged-out users must land on login; A1 starts here.
**Decisions:** D-029 (routes under `/app`, auth only via `/api/me` + httpOnly cookie, pure lib + Vitest, CI step — plan approved by the owner); F-008 (dev-only npm advisories).
**Verification:** `npm run lint`, `npm run typecheck`, `npm test` (10 passed), `npm run build` ✓. Browser walkthrough deferred to the end of S8 (preview server over in-memory repos; real Google login needs Postgres → Docker pass).
**AI mistakes caught:** test helper typed errors as `unknown` (strict TS caught it) → `failure()` helper; fast-refresh lint warning → context/hook moved to `useAuth.ts`; helpers first placed in `src/lib/`, which the root `.gitignore` (`lib/`) silently excluded from the commit → renamed to `src/logic/`, unpushed commit amended (AI_USAGE #10). Also corrected earlier advice: `.claude/` is *meant* to be untracked (the repo tracks `.agent/`), so the owner's local `ci.yml` path edit must not be committed — the CI change was staged on top of HEAD's file only.
**Explain-it-in-review:** "The page never sees the session token — it's an httpOnly cookie. The app asks /api/me who you are; if that's a 401 you're sent to the login page, and logging out is a POST so another site can't trigger it."
**Next:** T-081 Submit page (upload + URL)

---

## 2026-10-02 13:28 IST — T-081 Submit page (upload + URL) (agent: frontend)
**What changed:** `src/pages/SubmitPage.tsx` (tabs, file input + link input, inline server errors, navigate on 202), `src/logic/precheck.ts` + tests, route `/app/submit`, form/tab styles.
**Why:** both input paths from the brief; scenario A2 needs the server's "corrupt file" message shown cleanly.
**Decisions:** pre-checks are UX only and never stricter than the server (unknown MIME types like `.mkv` are allowed through; the server sniffs bytes) — part of D-029.
**Verification:** lint, typecheck, `npm test` (18 passed), build ✓. A2 click-through deferred to the S8 preview-server walkthrough.
**AI mistakes caught:** none.
**Explain-it-in-review:** "The browser checks size and length first so nobody waits for a 100 MB upload to be refused, but the server decides: if the file is corrupt, its exact message appears under the form."
**Next:** T-082 Job list with live status

---

## 2026-10-02 13:36 IST — T-082 Job list with live status (agent: frontend)
**What changed:** `src/pages/JobsPage.tsx`, `src/logic/poller.ts` + tests, `src/logic/jobs.ts` + tests, `src/hooks/usePolling.ts`, `src/components/StatusChip.tsx`, `src/components/ProgressBar.tsx` (`role="progressbar"` with aria values), table/chip/progress styles; follow-up F-009.
**Why:** "live job status" in the brief; reviewers watch A1's job progress.
**Decisions:** polling waits 2 s after each response (never overlapping requests on a slow network), keeps going after errors, pauses while the tab is hidden and refreshes immediately on return; enabled only while a job is active, so a finished list stops hitting the server (D-029).
**Verification:** lint, typecheck, `npm test` (27 passed), build ✓.
**AI mistakes caught:** none.
**Explain-it-in-review:** "The list asks the server every two seconds, but only while something is still running, never twice at once, and not at all while the tab is in the background."
**Next:** T-083 Job detail: video, stats, errors

---

## 2026-10-02 13:44 IST — T-083 Job detail: video, stats, errors (agent: frontend)
**What changed:** `src/pages/JobDetailPage.tsx`, `src/pages/NotFoundPage.tsx`, `src/components/{ErrorBanner,StatsCards,VideoPlayer}.tsx`, `src/logic/results.ts` + tests (`errorHelp`, `summarize`), routes `/app/jobs/:jobId` and catch-all, styles.
**Why:** A1 (annotated video plays, stats), A2 (readable failure), A3 ("Job not found" for another user's job).
**Decisions:** the page shows the same "Job not found" for missing and foreign jobs because the API can't tell them apart (D-028); distance is shown in frame diagonals with a tooltip saying pixels aren't metres (D-022 limit); a polling error never replaces a job already on screen.
**Verification:** lint, typecheck, `npm test` (32 passed), build ✓.
**AI mistakes caught:** first version replaced the whole page with an error on any polling failure — fixed in self-review before commit.
**Explain-it-in-review:** "If the job failed you get a plain headline, the server's message and the next step — for a YouTube block, a button to upload the file instead. If it isn't yours, you get exactly what you'd get for a job that doesn't exist."
**Next:** T-084 Heatmap view + player selector

---

## 2026-10-02 13:37 IST — T-084 Heatmap view + player selector, and the S8 browser walkthrough (agent: frontend)
**What changed:** `src/components/{HeatmapPanel,HeatmapCanvas,PlayerSelector}.tsx`, `src/logic/heatmap.ts` + tests, heatmap wired into the job detail page, styles. Separate fix commit: `src/logic/session.ts` + regression test, `auth.tsx` uses it (logout always signs out locally).
**Why:** A1's last step ("one player's heatmap opens"); per-player and per-team heatmaps from the brief.
**Decisions:** team heatmaps come straight from the stats JSON (no request → instant); a player's map is one request then cached; native `<select>` for keyboard/screen-reader support; distances shown in frame diagonals (D-022, D-029).
**Verification:** lint, typecheck, `npm test` (43 passed), build ✓. **Browser walkthrough** (Chrome, throwaway preview server in the scratchpad — real FastAPI app + built SPA over `tests/api_fakes.py` repos, finished job produced by the real T-062 pipeline with a scripted 6-player detector; not committed): logged-out `/app` → `/app/login` ✓; `/login?error=oauth_failed` → `/app/login` with the friendly message ✓; jobs list chips/progress/failure text ✓, `/api/jobs` polled every 2 s while a job was processing (server log 13:31:35/37/39) ✓; detail video: duration 12 s, seek to 7 s, `readyState` 3, no error, boxes #1–#6 drawn ✓ (server log 206 for range requests); stats cards ✓; heatmap All/Team A/Team B/#players ✓, player path overlay ✓, switch timings 41–125 ms (visible tab) ✓; `YOUTUBE_BLOCKED` banner + "Upload the file instead" ✓; **A2** header-only MP4 → server 422 → "We couldn't read this video — it may be corrupted…" under the form ✓; **A3** Bob on Alice's job → "Job not found", empty list ✓; URL submit → navigates to the new queued job ✓; logout with a failing server call → `/app/login` ✓ (after the fix). No console errors.
**AI mistakes caught:** logout didn't survive a failing request; muddy heatmap colours and an over-tall canvas; my preview script first forgot `static_dir` (SPA not served). Two false alarms disproved with server logs / `document.hidden` (AI_USAGE #11).
**Explain-it-in-review:** "The heatmap is a canvas: a neutral pitch, then each grid cell coloured by how much time was spent there. Team maps are already in the stats, so switching is instant; a player's map is fetched once and cached — under 130 ms in my test."
**Next:** S8 complete → stage summary; then S9 T-090 Rate limiting + active-job cap (auth-security)

---

## 2026-10-02 14:03 IST — T-085 Sport + title on submissions (agents: database + backend-api)
**What changed:** migration `0002_video_sport_title_thumbnail` (expand-only: `videos.sport` NOT NULL default 'football' + `ck_videos_sport_valid`, `videos.title` + `ck_videos_title_length` ≤120, `videos.thumbnail_key`), `db_tables.py` mirror, `core/submit_rules.py` (`clean_title`, `check_sport`), `ValidationError` + `InvalidSportError`, `NewVideo`/`Video` fields, repo insert, `submit_upload_job`/`submit_url_job` keyword args, upload `Form` fields + `UrlSubmit.sport/title`; tests `test_submit_rules.py`, `test_submit_sport_title.py`, migration CHECK test; S8b tickets added (D-030).
**Why:** owner's UI brief needs a sport (pitch vs court outline) and a human title per analysis; real columns instead of faked UI data.
**Decisions:** D-030 (scope + budget). Expand-only migration so rollback-by-image stays safe; sport defaults to football so the brief's curl examples and old clients keep working; cheap field checks before ffprobe.
**Verification:** 18 new local tests; full unit suite 506 passed, 1 failed (pre-existing Windows-only chmod); ruff, format, design checker ✓. **Not run locally:** migration up/down/up + CHECK tests (CI first run).
**AI mistakes caught:** title test expected control characters to be deleted, code replaces them with a space (safer — no glued words) → test expectation fixed; shared test container lacked a prober → upload test crashed before validation → fixed in the fakes.
**Explain-it-in-review:** "Sport and title are just two more video columns, added with a migration that only adds — the old app version keeps working against the new schema, which keeps rollback safe. Both are cleaned and checked in pure functions before we even look at the file."
**Next:** T-086 Job read model with video info + thumbnail

---

## 2026-10-02 14:09 IST — T-086 Job read model with video info + thumbnail (agents: backend-api + cv-pipeline)
**What changed:** `JobWithVideo` model; `JobRepo.get_with_video` / `list_with_videos` (labelled-column JOIN, `user_id` on both tables); `VideoRepo.set_thumbnail_for_worker`; `FrameAnnotator.thumbnail_jpeg` (OpenCV resize ≤320 px + JPEG q80); `core/blob_keys.thumbnail_key`; worker saves frame 0 in `services/process.py`; `read_job.get_job` now returns `JobWithVideo`, new `get_thumbnail`; response schemas carry title/sport/source/duration/size/`thumbnail_url`; `GET /api/jobs/{id}/thumbnail` (+ alias) via a small `blob_response`; tests extended (read API, A3 matrix, process_job thumbnail, repo JOIN scoping, Postgres thumbnail round-trip).
**Why:** the redesigned list/processing pages show title, sport, duration, size and a thumbnail; without this the UI would have to fake them (D-030). Closes F-009.
**Decisions:** one JOIN instead of N+1 lookups; repeat the `user_id` filter on the joined table (defence in depth); the thumbnail is readable as soon as the worker has decoded the first frame (any status), ownership checked first like everything else.
**Verification:** touched-file tests 74 passed locally; full unit suite 515 passed, 1 failed (pre-existing Windows-only chmod); ruff, format, design checker ✓; 106 Postgres tests collect. **Not run locally:** JOIN/scoping + thumbnail SQL tests (CI).
**AI mistakes caught:** none.
**Explain-it-in-review:** "The job list is one query that joins each job with its video, filtered by your user id on both sides. The worker saves the first frame as a small JPEG; it's served through the same ownership check as the video, so another user gets 404 for it too."
**Next:** T-087 Two-pass render: team-coloured boxes + honest stages `[review-plan]` (covered by the approved S8b plan)

---

## 2026-10-02 14:25 IST — T-087 Two-pass render: team-coloured boxes + honest stages (agent: cv-pipeline)
**What changed:** `services/process.py` split into `_analyse` (pass 1: detect/track/record + thumbnail + jersey samples) and `_rendered_frames` (pass 2: decode again, draw recorded boxes by team, stream to the encoder); new `computing` and `rendering` heartbeats; `core/pipeline.py` stage list + bands (`band_pct`, `render_pct`); `adapters/opencv_annotator.py` team colours (brief's hex in BGR), id label contrast, legend; `FrameAnnotator.draw(..., teams)` port; tests `test_opencv_annotator.py`, new process_job/pipeline tests.
**Why:** the brief's video legend (Team A / Team B / Ball) and processing stepper must be true, not decorative (D-030).
**Decisions:** D-031 (decode twice instead of buffering frames; deterministic decoder aligns pass 2 with pass 1).
**Verification:** 29 local tests in touched files; real-detector timing on a 12 s clip: analysing 10.34 s, computing 0.09 s, rendering 0.23 s, saving 0.02 s.
**AI mistakes caught:** none.
**Explain-it-in-review:** "We can only know the teams after watching the whole clip, so we watch it twice: first pass finds and tracks players (the expensive part), then we split teams, then a second, cheap pass redraws the boxes in team colours. Measured, the second pass is about 2 % of the time."
**Next:** T-088 Design system + app shell (frontend)

---

## 2026-10-02 14:30 IST — T-088 Design system + app shell (agent: frontend)
**What changed:** `frontend/src/styles/tokens.css`, rewritten `index.css`, `components/{icons,Logo,AppShell,UserMenu}.tsx`, `components/shell.css`, `pages/SettingsPage.tsx`, `logic/user.ts` + test, routes in `App.tsx` (`/login`, `/app/new`, `/app/settings`, redirects from old paths), Inter font links; old `Layout.tsx` removed; temporary `.button` alias in `App.css` for not-yet-redesigned pages.
**Why:** the owner's UI brief (D-030): light app shell, indigo primary, sidebar collapsing under 900 px, user menu, dark mode via CSS variables.
**Decisions:** all colours are tokens so dark mode is one override block; Google's G mark used only on the Google sign-in button (their branding rule); Inter from Google Fonts (CSP allow-list in T-091).
**Verification:** lint, typecheck, `npm test` (46 passed), build ✓. Visual check in the S8b walkthrough (end of T-097).
**AI mistakes caught:** one batch edit ran from the repo root instead of `frontend/` and failed without changing anything — re-run from the right directory.
**Explain-it-in-review:** "Every colour is a CSS variable, so dark mode is one block of overrides. On small screens the sidebar becomes a drawer you open from the top bar; Escape or a tap outside closes it."
**Next:** T-089 Landing + sign-in pages

---

## 2026-10-02 14:32 IST — T-089 Landing + sign-in pages (agent: frontend)
**What changed:** `frontend/src/pages/LandingPage.tsx`, rewritten `pages/LoginPage.tsx`, `components/HeroArt.tsx`, `pages/public.css`, `/` route now the landing page.
**Why:** owner's brief screens 1–2 (public landing + sign-in).
**Decisions:** hero art is an original SVG (no crests, players or footage); signed-in visitors skip the landing; sign-in copy says exactly what we read from Google (name, email).
**Verification:** lint, typecheck, `npm test` (46), build ✓; visual check in the S8b walkthrough.
**AI mistakes caught:** none.
**Explain-it-in-review:** "The landing and sign-in pages are static; the only action is a full-page link to /auth/login, because the OAuth flow runs on the server."
**Next:** T-094 New analysis redesign

---

## 2026-10-02 14:34 IST — T-094 New analysis redesign (agent: frontend)
**What changed:** `frontend/src/pages/NewAnalysisPage.tsx` + `new-analysis.css` (replaces `SubmitPage`), `src/media.ts` (local duration + thumbnail), `logic/format.ts` + tests, `types.ts` (sport, stage list, job video fields), `api.ts` sport/title on both submissions + tests.
**Why:** brief screen 4; sport/title are real fields since T-085.
**Decisions:** drop zone is a label around a hidden file input (keyboard and screen readers keep the native control); thumbnail and duration are read locally and never uploaded; pre-checks stay UX-only.
**Verification:** lint, typecheck, `npm test` (53), build ✓; drag-drop + thumbnail checked in the S8b walkthrough.
**AI mistakes caught:** none.
**Explain-it-in-review:** "Dropping a file reads its length and a preview frame in the browser, so you see mistakes before uploading 100 MB; the server still re-checks everything."
**Next:** T-095 My videos redesign

---

## 2026-10-02 14:37 IST — T-095 My videos redesign (agent: frontend)
**What changed:** `frontend/src/pages/MyVideosPage.tsx` + `videos.css` (replaces `JobsPage`), `components/{StatusChip,RowMenu}.tsx` + `status.css`, `logic/videos.ts` + tests, status label "Completed".
**Why:** brief screen 5; the list can show real titles, durations, sports and thumbnails since T-086.
**Decisions:** counts are computed client-side from the one list request; queued counts as Processing; Resubmit never invents a file — uploads go back to New analysis, links are re-posted.
**Verification:** lint, typecheck, `npm test` (59), build ✓; walkthrough at the end of S8b.
**AI mistakes caught:** none.
**Explain-it-in-review:** "The list is one request; filters and counts are just grouping on the client. It refreshes every two seconds only while something is still running."
**Next:** T-096 Processing view (stepper)

---

## 2026-10-02 14:39 IST — T-096 Processing view (stepper) (agent: frontend)
**What changed:** `frontend/src/components/ProcessingView.tsx` + `processing.css`, `logic/stepper.ts` + tests, `logic/jobs.ts` stage labels from the brief, `JobDetailPage` routes non-succeeded jobs to the processing view; `ErrorBanner`/`ProgressBar` removed.
**Why:** brief screen 6; the steps are real worker stages since T-087 (D-031).
**Decisions:** step states are derived only from `status` + `stage` (never guessed from time); failed jobs mark the failing step when the backend kept the stage.
**Verification:** lint, typecheck, `npm test` (66), build ✓.
**AI mistakes caught:** none.
**Explain-it-in-review:** "The stepper is a pure function of the job's status and stage, so it shows exactly what the worker reports — Fetching only appears for YouTube links."
**Next:** T-097 Results tabs + smooth heatmaps

---

## 2026-10-02 14:54 IST — T-097 Results tabs + smooth heatmaps, and the S8b walkthrough (agent: frontend)
**What changed:** `frontend/src/components/{ResultsView,SmoothHeatmap,PlayerStatsTable}.tsx` + `results.css`, `logic/{insights,smoothHeatmap}.ts` + tests, `JobDetailPage` → Processing or Results; removed `StatsCards`, `HeatmapPanel`, `HeatmapCanvas`, `PlayerSelector`, `logic/heatmap.ts`, `App.css`; polish: processing chip, toggle, heat fade-in, tab scrollbar; backend fix commit moves the video time stamp bottom-left.
**Why:** brief screen 7 (results tabs, legend, key metrics, smooth heatmaps, pitch vs court by sport).
**Decisions:** every number on the page comes from the stats JSON or the player row (no derived metrics); legend/toggles list only teams that exist; with no ball detected the possession card says so instead of showing zeros; heat rendered small and scaled by the browser for fast switching.
**Verification:** lint, typecheck, `npm test` (72), build ✓. **Browser walkthrough** (scratchpad preview server, real YOLOX-S + two-pass pipeline, 8 s panning clip of `tests/fixtures/people.jpg`): processing page live (thumbnail, stepper, 53 %); results header/tabs/legend/metrics/footnote; annotated frame extracted: orange-kit player in Team A blue, grey-kit players in Team B red, legend top-right; team + player heatmaps with path; My videos; A2 corrupt upload → server message; A3 Bob → Job not found; landing; three 390 px iframes (no horizontal overflow, cards, menu button). Background-tab media/polling pauses observed and confirmed as Chrome throttling (`document.hidden`), not app bugs.
**AI mistakes caught:** chained `&&` assertions silently skipped (lint + tsc caught it, AI_USAGE #12); six visual issues found and fixed in the walkthrough (AI_USAGE #13).
**Explain-it-in-review:** "The results page only shows what the backend computed: the legend lists teams that exist, and if the ball was never seen it says so instead of a 0 % split. Heatmaps are the backend's grid, smoothed in the browser and drawn over a pitch or court depending on the sport the coach picked."
**Next:** S8b stage summary; then S9 T-090 Rate limiting + active-job cap

---

## 2026-10-02 15:10 IST — T-090 Rate limiting + active-job cap (agent: auth-security)
**What changed:** `core/rate_limit.py`, `adapters/memory_rate_limiter.py`, `RateLimits` model, `RateLimiter` port + `JobRepo.count_active` (Postgres + fakes), `services/submit.check_submit_allowed`, `RateLimitedError`/`TooManyActiveJobsError`, `Retry-After` in the error envelope response, limiter built in `wiring.py`, three settings (+ `.env.example`, README); tests `test_rate_limit.py`, `test_rate_limit_api.py`, `count_active` repo test.
**Why:** "Rate limiting on submit endpoints"; protect the single worker from one user's queue.
**Decisions:** D-032 (in-memory sliding window per user, every attempt counts but refusals don't extend the block, active-job cap 3, checks before any validation/storage).
**Verification:** `pytest -q -k rate` → 19 passed; unit suite 539 passed, 1 failed (pre-existing Windows-only chmod); ruff, format, design checker ✓. **Not run locally:** `count_active` against Postgres (CI).
**AI mistakes caught:** the window-boundary test expected a hit exactly 60 s old to still count; the code (and `Retry-After`) treat it as expired — test expectation corrected.
**Explain-it-in-review:** "Each user gets 10 submissions a minute and 30 an hour; the 11th gets a 429 with Retry-After telling them how long to wait. On top of that, nobody can have more than 3 videos queued or processing, so one person can't starve the worker."
**Next:** T-091 Security headers + CORS + error audit

---

## 2026-10-02 15:55 IST — T-091 Security headers + CORS + error audit (agent: auth-security)
**What changed:** new `core/security_headers.py` (pure CSP/headers/no-store rules); `api.py`: outermost `harden_responses` middleware (headers + last-resort 500 with ref id), optional `CORSMiddleware`, `RequestValidationError` and framework 404/405 → envelope, `serve_spa` realpath containment; `errors.py` `InternalError`, `MethodNotAllowedError`; `config.py` `CORS_ORIGINS`, `CSP_MEDIA_ORIGINS` + validation; `.env.example`, README env rows; tests `test_security_headers.py` (7), `test_headers_api.py` (14).
**Why:** "restricted CORS, security headers"; closes F-001 (path traversal) and F-006 (validation errors outside the envelope).
**Decisions:** D-033 (pure header builder + one function middleware, HSTS prod-only, fonts + S3 media origins in CSP, CORS off by default, catch crashes in the outermost middleware so 500s keep their headers).
**Verification:** `pytest -q -k headers` → 21 passed; unit suite 560 passed, 1 failed (pre-existing Windows-only chmod); ruff, format, design checker ✓. Browser on the preview server under the real CSP: Inter fonts load, annotated video plays (readyState 4), canvas heatmap draws, thumbnail loads, 0 CSP console errors.
**AI mistakes caught:** F-001 traversal in the original SPA route (regression test proven to read the secret without the fix); `/jobs` aliases missing from no-store; `caplog` assumption — see AI_USAGE #14.
**Explain-it-in-review:** "Every response gets a strict CSP — only our own scripts, Google Fonts and our storage host for video — plus nosniff, frame-deny and HSTS in production. CORS is off because the SPA is same-origin. Every error, even a crash, comes back in the same JSON shape with no internals; a crash gives the user a reference id we can find in the logs."
**Next:** T-092 Secret scanning in CI
---

## 2026-10-02 15:57 IST — T-092 Secret scanning in CI (agent: devops)
**What changed:** `.github/workflows/ci.yml` new `secrets` job (pinned checkout, full history, gitleaks v8.30.1 downloaded + sha256-verified, `gitleaks git --redact --exit-code 1`). Only this job was staged — the local `.agent` → `.claude` path edit in the same file stays uncommitted.
**Why:** "Nothing sensitive in git history".
**Decisions:** D-034 (plain pinned binary instead of gitleaks-action; full history; redacted output; no allowlist needed).
**Verification:** same gitleaks version locally (Windows zip, hash matched the checksums file): 54 commits scanned, no leaks, exit 0. Staged workflow parses (jobs: backend, secrets, frontend, docker). **Not yet run in CI** — first run on the S9 PR.
**AI mistakes caught:** none in this ticket (the T-091 test string that could have tripped gitleaks was changed before committing).
**Explain-it-in-review:** "Every push scans the whole git history with gitleaks, a pinned version whose checksum we verify, so even a secret deleted later fails the build. Findings are redacted in the log."
**Next:** S9 stage summary, then S10 deploy (T-014 / T-100)
---

## 2026-10-02 16:07 IST — T-090 follow-up: CI integration failure (agent: qa)
**What changed:** `tests/integration/test_url_submit.py` — the latency test lifts `max_active_jobs_per_user` to 10 via fixture override.
**Why:** CI on the S9 PR: the test's 6 queued submits hit the new 3-active-job cap → 429.
**Verification:** test collects with the override; ruff clean. Postgres run = CI re-run on the PR.
**AI mistakes caught:** integration tests not checked against the new cap (AI_USAGE #15).
**Next:** CI green on S9 PR → merge → S10.
---

## 2026-10-02 16:24 IST — Fix: login errors shown as raw JSON (agent: auth-security)
**What changed:** `entrypoints/api.py` — `/auth/login` and `/auth/callback` never return JSON: not configured → 303 `/login?error=login_unavailable` (+ startup warning naming the missing settings), Google "Cancel" (`error=access_denied`) → `cancelled`, provider failure → `oauth_failed` (unchanged), failure while creating the user/session → `server_error` (logged with traceback, no cookie); success now goes straight to `/app`. `frontend/src/logic/login.ts` messages for the new codes (+ test). README: one-time Google Cloud setup.
**Why:** owner saw `{"error":{"code":"SERVICE_UNAVAILABLE",…}}` after clicking "Continue with Google" (server had no Google credentials).
**Similar issues checked:** every browser navigation (`href`/`location`) in the SPA — only `/auth/login` (fixed) and the "Download annotated video" link (`<a download>` to `/api/jobs/{id}/video`; only shown for a finished job of the logged-in user, and a failed download shows in the browser's download bar, not as a page). All other errors go through `fetch` → envelope → shown as text.
**Verification:** unit 563 passed (+ known Windows-only failure); integration 107 collect (CI); ruff, format, design ✓; frontend lint/typecheck/73 tests/build ✓; browser on the preview server (no Google config): "Continue with Google" → login page with "Google sign-in is not available…" message.
**AI mistakes caught:** AI_USAGE #16.
**Next:** owner sets up the Google OAuth client + `.env` → Docker pass → deploy (Render).
---

## 2026-10-02 13:32 IST — T-014 / F-005 first deploy on Google Cloud + T-100/T-101 workflows (agent: devops)
**What changed:** Google Cloud project `sports-play-analyzer` (`asia-south1`): Artifact Registry `sports-analyzer`; Cloud SQL Postgres 16 `sports-analyzer-db` (Enterprise, db-custom-1-3840) with DB `sports_analyzer` / user `app`; private bucket `sports-play-analyzer-media` (uniform access, public access prevention); runtime SA `sports-analyzer-run` (bucket objectAdmin, cloudsql.client, secretAccessor per secret); 7 Secret Manager secrets; Workload Identity pool `github-actions` limited to this repo → `github-deployer` SA. Image built with Cloud Build (`web:348b9fa`), migration job ran 0001+0002, web service `sports-analyzer-web` (min 1) and worker pool `sports-analyzer-worker` (1×2 vCPU/2 GiB) deployed. Repo: `cd.yml`, `rollback.yml`, D-035, ADR/README storage + host notes.
**Why:** live URL is mandatory (T-014); CD/rollback (T-100/T-101).
**Decisions:** D-035 (Google Cloud), S3_REGION=auto + storage.googleapis.com per Google's boto3 sample.
**Verification:** `/health` → `{"status":"ok","db":"ok","version":"348b9fa"}`; GET / 200 with CSP, X-Frame-Options DENY, HSTS; `/auth/login` → Google with the run.app callback; worker log "worker started". Not yet: Google sign-in on prod (redirect URI to add), a full job (storage path), CD run on main.
**AI mistakes caught:** AI_USAGE #17 (mislabeled action SHA), #18 (CR in DB password; port 8080 vs 8000). Also found and revoked: a GitHub token embedded in the local git remote URL → remote switched to SSH with a dedicated key.
**Next:** owner adds prod redirect URI → sign-in + full job on prod → T-102.

---

## 2026-10-02 14:12 IST — Fix: live Google login invalid_client; secret hygiene (agent: auth-security)
**What changed:** `backend/app/config.py` reads every setting through `env()` (strips surrounding whitespace); `tests/unit/test_config_env.py` (3 tests). Ops (no repo files): clean versions of `google-client-id`, `google-client-secret`, `session-secret` (old ones disabled); DB password rotated after a stray local file held it; web rev 00004 + worker rev 00003 restarted. Merge conflict dev→main resolved with `git merge -s ours` on `chore/sync-main-into-dev` (tree identical to dev).
**Why:** live sign-in failed with Google `Error 401: invalid_client`; the stored client ID ended in \r\n.
**Verification:** all 7 secrets have 0 CR/LF bytes; live `client_id` clean; `/health` ok with the rotated password; worker started. Tests: 3 new pass (2 fail without the strip); unit 566 passed (+ known Windows-only failure); ruff, format, design ✓.
**AI mistakes caught:** AI_USAGE #19.
**Next:** owner signs in on prod + runs a job; merge dev→main (first CD run); T-102.

---

## 2026-10-02 14:26 IST — Fix: uploads failed on Google Cloud Storage (agent: backend-api)
**What changed:** `adapters/blob_s3.py`: boto3 client sends/validates checksums only when required; `S3UploadFailedError` mapped to `ExternalServiceError` (502 envelope, not a 500). Tests: `test_blob_s3_failed_upload_is_a_storage_error_not_a_crash`, `test_s3_client_sends_checksums_only_when_required`.
**Why:** live upload → "Something went wrong (ref 51c856ae)": GCS answered `SignatureDoesNotMatch` to boto3 1.43's default CRC upload checksums.
**Verification:** direct probe on the real bucket — default config fails, fixed config passes upload / presigned GET / range / delete; blob tests 9 passed (2 new fail on the old code); unit 568 passed (+ known Windows-only failure); ruff, format, design ✓.
**AI mistakes caught:** AI_USAGE #20.
**Next:** hot-deploy this image, owner re-uploads; PR → dev → main.

---

## 2026-10-02 15:20 IST — Fix: first CD run failed at the migration step (agent: devops)
**What changed:** `.github/workflows/cd.yml` migration job uses `--set-cloudsql-instances` (jobs have no `--add-` form).
**Why:** first run on `main` (Actions run 37020616640): WIF auth, build and push to Artifact Registry passed; `gcloud run jobs deploy` failed with `unrecognized arguments`; later steps skipped, production untouched (still 67f2dda).
**Verification:** every flag in `cd.yml` and `rollback.yml` checked against `gcloud <command> --help` (no missing flags; checker flags the old one). Real proof = next CD run.
**AI mistakes caught:** AI_USAGE #21.
**Next:** PR → dev → main; watch CD go green end to end.

---

## 2026-10-03 05:29 IST — YouTube URLs on Cloud Run: cookies (agent: auth-security)
**What changed:** Secret `ytdlp-cookies-b64` (runtime SA access only); worker deploy in `cd.yml`/`rollback.yml` gets `YTDLP_COOKIES_B64`; live worker updated (rev 00006, same image abc4e7b); README refresh runbook; D-036; ADR row; `scripts/fetch_check.py` prints UTF-8.
**Why:** every URL job failed `YOUTUBE_BLOCKED` in production; scenario 1 depends on it.
**Verification:** cause reproduced from Cloud Run without cookies (bot check), video fetched fine locally (and is 981 s → would be DURATION_EXCEEDED anyway). With cookies, from Cloud Run: metadata OK; full fetch metadata → download → ffprobe OK (mp4, 18.9 s). Cookies file checked by names/counts only, never printed. Pending: owner submits a ≤60 s YouTube clip in the app.
**AI mistakes caught:** none new (fetch_check emoji crash fixed).
**Next:** owner test in app; T-102.

---

## 2026-10-03 05:56 IST — T-B07 "AI look" for the annotated video and results UI (agents: cv-pipeline, frontend)
**What changed:** `adapters/opencv_annotator.py` redesigned (feet spotlights, corner brackets, id badges, ball glow + connected trail, HUD "AI TRACKING · N players · ball · time", watermark on a panel, legend of the clip's teams); `core/overlay.ball_trail` (pure); `FrameAnnotator.draw` takes `ball_trail`; `services/process.py` passes it. Frontend: `logic/aiSummary.ts` (+ test), "AI analysis complete" strip, `VideoPlayer` badge + one-time scan sweep, processing thumbnail scan line (reduced-motion respected), `SparkleIcon`, `frames_analysed` in `Stats`. Tickets: T-B07 done, T-B08 (SAM 2, post-submission) added; D-037.
**Why:** owner request; SAM 2 deferred (no GPU, required tickets open).
**Verification:** annotator tests 9 (trail chain, jump break, no dangling trail, legend stability, HUD, spotlight blend); unit 575 passed (+ known Windows-only failure); ruff, format, design ✓; frontend lint/typecheck/75 tests/build ✓. Real pipeline on the owner's football clip (YOLOX, 13 players, 11.4 s) and three rendered frames inspected; fixed from that inspection: ghost watermark shadow, zig-zag/detached trail from false ball detections, per-frame legend flicker, "1 players". **Not checked visually:** the new web UI (browser tool disconnected) — owner to review after deploy.
**AI mistakes caught:** two test expectations of mine were wrong (sampled row, trail beyond the end); the code was right.
**Next:** PR → dev → main; then T-102 (publish consent screen) and acceptance; T-B08 after submission.
