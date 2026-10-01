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
