# Decisions log

Running log of every meaningful choice (feeds docs/ADR.md). Format:

### D-xxx <title> (<date>, T-xxx)
Context: … | Options: A / B / C | Chosen: B | Because: … | Consequences: …

---

### D-001 Object detection model selection (2026-09-30, T-002)
Context: Need pretrained COCO detector for players and ball running on CPU worker.
Options: A (Ultralytics YOLO - AGPL-3.0) / B (YOLOX-S ONNX - Apache-2.0)
Chosen: B (YOLOX-S ONNX)
Because: Apache-2.0 licence is clean and permissive for distribution; ONNX Runtime has excellent CPU performance without PyTorch overhead; zero model training required.
Consequences: Pre-download model during Docker build; write custom letterbox and NMS post-processing in pure Python/NumPy.

### D-002 Hosting and deployment topology (2026-09-30, T-002)
Context: Need cheap/free, reliable hosting with separated web and worker processes and persistent storage.
Options: A (Render / Railway) / B (Fly.io + Neon Postgres + S3/Tigris) / C (Single VPS)
Chosen: B (Fly.io + Neon Postgres + Tigris / Cloudflare R2)
Because: Fly.io allows running separate `web` and `worker` process groups from a single multi-stage Dockerfile; Neon provides managed serverless Postgres 16; S3-compatible storage decouples video blobs from ephemeral container disks.
Consequences: Multi-region config must align DB and worker latency; presigned URLs used for video playback.

### D-003 Session and authentication strategy (2026-09-30, T-002)
Context: Secure user authentication with per-user data isolation.
Options: A (Stateless JWT in cookie/localStorage) / B (Server-side sessions in Postgres `sessions` table with `__Host-sid` cookie)
Chosen: B (Server-side sessions in Postgres)
Because: Immediate revocation on logout, avoids client-side token leakage, simplifies single-source-of-truth user lookup.
Consequences: DB lookup per authenticated request (cached per-request cycle in FastAPI dependency).

### D-004 API routing structure and legacy compatibility (2026-09-30, T-002)
Context: Brief specifies endpoints like `POST /jobs/upload` and `GET /jobs/{id}`, while SPA architectures typically namespace to `/api/`.
Options: A (`/api/...` only) / B (`/jobs/...` only) / C (`/api/jobs/...` canonical with `/jobs/...` rewrite/alias)
Chosen: C (`/api/jobs/...` canonical with `/jobs/...` aliases)
Because: Satisfies reviewer curl commands hitting `/jobs/...` while maintaining clean dev proxy separation for Vite SPA under `/api/`.
Consequences: Route definitions in FastAPI map both `/api/jobs` and `/jobs`.

### D-005 OAuth provider and PKCE protocol (2026-09-30, T-002)
Context: Authentication requirement for login.
Options: A (Custom username/password) / B (Google OAuth 2.0 Authorization Code Flow + PKCE)
Chosen: B (Google OAuth 2.0 + PKCE via Authlib)
Because: Satisfies assignment requirement using a vetted standard library; PKCE prevents authorization code interception attacks.
Consequences: Requires Google Client ID and Secret in environment; ephemeral session cookie for OAuth state handshake.

### D-006 Live job status polling mechanism (2026-09-30, T-002)
Context: Frontend needs to show real-time progress as jobs process.
Options: A (WebSockets) / B (Server-Sent Events) / C (Client-side polling every 2s while active)
Chosen: C (Client-side polling)
Because: Stateless, simplest to implement and debug, resilient across worker restarts and proxy dropouts, automatically pauses when tab is hidden.
Consequences: Slightly higher request count while jobs run; SSE deferred to bonus ticket T-B03.

### D-007 Stop ignoring `*.ts` in .gitignore (2026-10-01, T-013)
Context: `.gitignore` listed `*.ts` (meant for MPEG transport-stream video), which silently excluded every TypeScript source (`vite.config.ts`, `vite-env.d.ts`, `api.ts`) from the repo, so a fresh clone could not typecheck or build.
Options: A (keep `*.ts`, add `!frontend/**/*.ts` negations) / B (drop `*.ts`; ignore only `*.m2ts`/`*.mts`, rely on `/data/`, `blobs/`, `storage/` dir ignores for stray media)
Chosen: B
Because: video only ever lands in the already-ignored blob/data dirs; a wildcard that collides with a source extension is a trap for every future `.ts` file.
Consequences: recreated the three lost frontend files; CI frontend job now proves a fresh clone builds.

### D-008 SPA directory from `STATIC_DIR` env var (2026-10-01, T-013)
Context: `api.py` hard-coded `<repo>/frontend/dist`, but the Docker image copies the build to `/app/backend/static`, so production never served the UI; the SPA test also depended on a local build existing.
Options: A (change the Docker copy path) / B (`STATIC_DIR` setting, default `<repo>/frontend/dist`, Dockerfile sets `/app/backend/static`)
Chosen: B
Because: follows "all configuration via env vars" and lets tests point at a temp dir with a fake `index.html`.
Consequences: `Settings.static_dir`; unit tests no longer need `npm run build` first.

### D-009 CI shape (2026-10-01, T-013)
Context: Brief requires CI on every push and PR (lint, test, build), least privilege and pinned actions.
Chosen: three jobs — backend (ruff lint+format, design checker, unit, integration with Postgres 16 service), frontend (eslint, `tsc -b`, build on Node 20 to match the Dockerfile), docker (buildx build with GHA cache, no push, then run the image against Postgres and smoke `/health` + SPA root). Top-level `permissions: {}`, `contents: read` per job, `persist-credentials: false`, every action pinned to a 40-char commit SHA resolved with `git ls-remote` (checkout v7.0.1, setup-python v7.0.0, setup-node v7.0.0, setup-buildx v4.4.1, build-push v7.4.0); per-ref concurrency cancels superseded runs.
Because: the docker smoke run catches image/entrypoint breakage that a build-only job misses (it did: the `app.entrypoints.api:app` target did not exist).
Consequences: integration step treats pytest exit 5 ("no tests collected") as success until T-020 adds integration tests — remove that allowance then.

### D-010 YouTube from cloud IPs: blocked (2026-10-01, T-014 spike)
Context: Brief warns YouTube blocks cloud IPs; acceptance A1 submits a YouTube URL. Deploy is deferred until the app is complete locally, so the spike ran from GitHub-hosted runners (Azure datacenter IPs) as a stand-in for the prod host — `.github/workflows/youtube-spike.yml`, run https://github.com/akashbhabarwork-hue/Sports-Play-Analyzer/actions/runs/36859379841.
Result: yt-dlp 2026.8.19 on `jNQXAC9IVRw` (19 s), with and without the deno JS runtime → metadata **and** download both fail with `Sign in to confirm you're not a bot`. Without a JS runtime yt-dlp also warns that YouTube extraction without one is deprecated.
Options: A (no mitigation: clean `YOUTUBE_BLOCKED` error suggesting upload) / B (cookies file from a dedicated throwaway Google account via `YOUTUBE_COOKIE_FILE` secret) / C (residential/rotating proxy via `YOUTUBE_PROXY`, paid) / D (B or C layered on A)
Chosen: A as the guaranteed baseline now (already in ADR §3); B vs C vs none is **pending the owner's choice** before T-043/T-102.
Because: the failure is IP-reputation based, so it will very likely reproduce on Fly; A keeps A1's failure readable, but A1 itself needs B or C to pass on the live URL.
Consequences: worker image must ship a JS runtime (yt-dlp `deno` extra) regardless; `YOUTUBE_COOKIE_FILE`/`YOUTUBE_PROXY` stay in `.env.example`; re-run the spike from the real prod machine at deploy (F-005).

### D-011 Index justification (2026-10-01, T-020)
Measured on local Postgres 16 with 200 users, 20 000 jobs (99.5 % succeeded, 101 queued), 2 000 sessions, after `ANALYZE`:
- `ix_jobs_claimable` — `jobs (created_at) WHERE status IN ('queued','processing')`. Serves the worker claim `… WHERE status='queued' OR (status='processing' AND lease_expires_at < now()) … ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1`. EXPLAIN: `Limit → LockRows → Index Scan using ix_jobs_claimable` (no sort, no seq scan). Size **16 kB** vs 1 168 kB for a full index on 20k rows, because finished jobs drop out — it stays small as history grows, and the claim runs every poll.
- `ix_jobs_user_created` — `jobs (user_id, created_at DESC)`. Serves "my jobs": `WHERE user_id = :u ORDER BY created_at DESC LIMIT 20`. EXPLAIN: `Index Scan using ix_jobs_user_created`, `Index Cond: user_id = …` — rows come pre-sorted, no sort node. Also the first column makes per-user authorization filters cheap.
- `ix_sessions_user` — `sessions (user_id)`. Serves logout-everywhere / per-user cleanup `DELETE FROM sessions WHERE user_id = :u`. EXPLAIN: `Bitmap Index Scan on ix_sessions_user`. Session lookup itself uses the `token_hash` PK.
Not indexed on purpose: `videos.user_id`, `jobs.video_id` FKs — only touched by cascading deletes of a single user/video, rare and small; add if delete latency shows up.

### D-012 Schema conventions (2026-10-01, T-020)
Context: first migration. Chosen: SQLAlchemy Core tables in `db_tables.py` as the source of truth with a `MetaData` naming convention; revision `0001` is autogenerated then hand-reviewed; an integration test runs `alembic check` so model and migrations cannot drift. Column names follow the queue skill (`lease_expires_at`, `locked_by`); ADR §4 updated. Extra CHECKs beyond the ticket: `url` source ⇔ `source_url` present, and `failed` ⇒ `error_code` present (A2 needs a readable failure). `gen_random_uuid()` is built into PG13+, so no `pgcrypto` extension (works on Neon). Pinned `sqlalchemy==2.1.1`, `alembic==1.20.0`. Compose `migrate` now fails loudly instead of `|| echo`.

### D-013 User-scoped repositories (2026-10-01, T-021)
Context: "Users can only access their own jobs… enforced server-side" (A3).
Chosen: Protocols in `core/ports.py`, Postgres adapters in `adapters/pg_repos.py` (Core SQL, one transaction per method), frozen dataclasses in `core/models.py`. Every Video/Job/Result read takes `user_id` and filters in SQL (results/tracks join `jobs` on `user_id`); worker-only methods are suffixed `_for_worker`. "Not found" and "not yours" both return `None`, so the API can answer 404 for both and never confirm another user's job exists. A unit test (`test_ports.py`) inspects the protocols and fails on any unscoped read, so the rule is mechanical, not a convention.
Also: `JobRepo.create_with_video` inserts the video and its job in one transaction (no orphan videos); one shared SQLAlchemy engine (`pool_pre_ping`) for all repos and `/health`; adapter DB failures are wrapped as `ExternalServiceError` (HTTP 502, details only in logs) — `AppError.status_code` now drives the error handler.
Deferred: queue methods (claim/heartbeat/finish/fail/sweep) → T-022; active-job count for the cap → T-090.

### D-014 Postgres job queue semantics (2026-10-01, T-022)
Context: "Workers claim jobs safely (SELECT … FOR UPDATE SKIP LOCKED)"; "idempotent retry… no jobs stuck in processing".
Chosen: `adapters/pg_queue.py` (`JobQueue` protocol, worker-only). `claim` is one CTE + `UPDATE … RETURNING` with `FOR UPDATE SKIP LOCKED`, oldest first via `ix_jobs_claimable`; claimable = `queued`, or `processing` with an expired lease, and `attempts < max_attempts` (3). Lease = `LEASE_SECONDS` (60, env), extended by `heartbeat`. Every post-claim write (`heartbeat`, `finish`, `fail`) is guarded by `locked_by = worker AND status = 'processing'`, so a worker that lost its lease writes nothing. `finish` is one transaction: lock → delete tracks → insert tracks → upsert result → `succeeded`. `sweep_dead` turns expired, exhausted jobs into `failed/WORKER_CRASHED`. All times come from the DB clock.
Retry policy (owner's choice, option a): handled errors (`CORRUPT_FILE`, `YOUTUBE_BLOCKED`, `DURATION_EXCEEDED`, …) fail immediately and are final; only crashes are retried, via lease expiry. Rejected: retrying transient errors like `DOWNLOAD_FAILED` (needs a retryable flag + requeue; slower failures for A2).
Evidence: 11 queue tests incl. 8-thread concurrent claims (stable over 5 repeats); mutations caught — dropping `FOR UPDATE SKIP LOCKED` (duplicate claims), the heartbeat ownership guard, delete-before-insert in finish, and the `max_attempts` filter each turn a test red.

### D-015 Google login: async OAuth routes, sessions, safe logging (2026-10-01, T-030)
Context: "OAuth 2.0 Authorization Code flow with PKCE, using a vetted library"; "secure session handling"; no secrets in logs.
Chosen: Authlib 1.8 Starlette client (`adapters/oauth_google.py`) with Google endpoints registered explicitly (no discovery fetch; `/auth/login` works offline and is unit-testable), S256 PKCE, state + nonce, ID token validated (signature via JWKS, aud, iss — both Google spellings — nonce, exp); unverified emails are not stored. Transient `oauth_tx` cookie (Starlette `SessionMiddleware`, 10 min, signed with `SESSION_SECRET`) only for the OAuth transaction, cleared after the callback. Our session: `secrets.token_urlsafe(32)` in `__Host-sid` (`HttpOnly; Secure; SameSite=Lax; Path=/`, no Domain; `sid` without Secure for local http), only `sha256(token)` stored, 7-day expiry, rotated on every login. Redirect URI comes from `APP_ORIGIN`, never request headers. Logout is `POST` → 204 (a cross-site `<img>` cannot log users out). Callback failures redirect to `/login?error=oauth_failed` without detail.
**Async exception:** `/auth/login` and `/auth/callback` are `async def` because Authlib's Starlette client is async; they only call Authlib, then the sync `services/auth.login_user` via `run_in_threadpool`. Everything else stays sync (rule 10).
**Logging:** uvicorn's access log prints full query strings, which would leak the OAuth `code`/`state`; uvicorn now runs with `--no-access-log` and an app middleware logs method, path (no query), status and duration. `httpx`/`httpx2`/`httpcore` loggers are set to WARNING.
Config: production refuses to start without `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET` (names reported, values never); dev without them answers 503 "not configured". Deps: `authlib==1.8.0`, `httpx2==2.13.1` (Authlib 1.8's preferred client; plain httpx is its deprecated fallback), `itsdangerous==2.2.0`.

### D-016 Authentication on /api, CSRF check, error codes (2026-10-01, T-031)
Context: server-side authz on every route; defence in depth for cookie auth.
Chosen: `current_user` dependency (cookie → `sha256` → unexpired session → `User`, else 401 `UNAUTHORIZED`) applied at the `/api` `APIRouter` level so no route can skip it; `tests/unit/test_api_routes.py` fails if any `/api` route lacks it. `GET /api/me` → `{id, email, name, avatar_url}` (Pydantic only in `entrypoints/schemas.py`).
CSRF (owner chose strict): unsafe methods (everything but GET/HEAD/OPTIONS) need `X-Requested-With: fetch` **and** an `Origin` — or, if absent, the `Referer`'s origin — in `APP_ORIGIN ∪ TRUSTED_ORIGINS`; neither present → 403 `CSRF_REJECTED`. The custom header forces a CORS preflight that cross-site forms cannot send. Pure decision function in `entrypoints/csrf.py` (moved out of `core/` because the design checker treats `urllib` as I/O; it is an HTTP-boundary concern anyway), applied by middleware. `TRUSTED_ORIGINS` replaces the unused `CORS_ORIGINS` and lets the Vite dev server (:5173) post through its proxy. The frontend client sends the header on every request.
Errors: each `AppError` subclass has a stable UPPER_SNAKE `code` (`UNAUTHORIZED`, `CSRF_REJECTED`, `SERVICE_UNAVAILABLE`, `EXTERNAL_SERVICE_ERROR`, `OAUTH_FAILED`, `BAD_REQUEST`) instead of the Python class name.

### D-017 BlobStore: local + S3, safe keys, short-lived links (2026-10-01, T-040)
Context: uploads and annotated videos must be shared between web and worker, which run on different machines in production.
Chosen: `BlobStore` protocol (`put_file`, `get_to_path`, `size`, `open_range`, `presigned_get_url`, `delete`) with `LocalBlobStore` (compose/dev) and `S3BlobStore` (boto3, SigV4, endpoint from env — Tigris, R2 or AWS), selected by a `BLOB_STORES` dict registry on `BLOB_BACKEND`. Keys: `core/blob_keys.py` validates every key (segments of `[A-Za-z0-9._-]`, none starting with `.`, no `..`/absolute/empty/backslash, ≤512 chars) and builds deterministic keys (`uploads/{video_id}/source.{ext}`, `jobs/{job_id}/annotated.mp4`) so retries overwrite. Local adapter also resolves the path and requires it to stay under the root (blocks symlink escapes) and writes atomically (temp file + `os.replace`). Presigned URLs are capped at 300 s; local returns `None` so the API streams with Range (T-070). Missing keys → `BlobNotFoundError`; other backend failures → `ExternalServiceError`, logged without credentials or exception text.
Config: production refuses `BLOB_BACKEND=local`; `s3` requires bucket + keys (names reported, never values).
Testing: S3 adapter tested in-process with `moto` (dev-only dependency) through the same `make_s3_client` factory production uses.

### D-018 Upload validation pipeline (2026-10-02, T-041)
Context: "Max 60 s and 100 MB"; "check content by inspecting the file, not the extension… clean up temp files"; "returns a job_id immediately".
Chosen: `POST /api/jobs/upload` (multipart `file`, login + CSRF) → checks cheapest first:
1. `BodySizeLimitMiddleware` (pure ASGI, upload path only): `Content-Length` > limit + 1 MB → 413 before the app runs; otherwise counts received bytes and, once past the cap, stops feeding the parser and replaces whatever the app answers with 413. Needed because Starlette spools the whole multipart body to disk before the route runs, and FastAPI turns any parse-time exception into its own 400.
2. Chunked copy (1 MB) into a per-request `TemporaryDirectory` with a second byte cap; the directory is removed in every outcome.
3. Magic-byte sniff (`core/file_sniff.py`): ISO-BMFF `ftyp` (MP4/MOV), EBML (MKV/WebM), `RIFF…AVI `; extension and Content-Type ignored → else 415 `UNSUPPORTED_FORMAT`.
4. `ffprobe` (argument list, `--` before the path, no shell, 15 s timeout): failure/no video stream → 422 `CORRUPT_FILE`; `core/video_rules.py`: duration > 60 s (+0.5 s) → 422 `DURATION_EXCEEDED`; side > 4096 px → 422.
5. App-generated `video_id` → blob `uploads/{video_id}/source.{ext}` stored **before** the video+job rows (one transaction, probe metadata + config snapshot); if the insert fails the blob is deleted, so the worker never sees a job without its file.
6. 202 `{job_id, status}`.
Also: `python-multipart` was used by FastAPI but missing from requirements — pinned; CI backend job installs ffmpeg again. `/jobs/...` aliases (D-004) deferred to T-070.

### D-019 URL submit: syntactic SSRF rules, canonical URLs only (2026-10-02, T-042)
Context: "YouTube URL: fetched server-side"; host allowlist; both input paths feed one pipeline.
Chosen: `core/url_rules.py: canonicalize_youtube_url` (pure). Rejects empty/over-2048/whitespace/control/backslash input; requires `https`, no userinfo (or `@` in the authority), port absent or 443, and host **exactly** in {youtube.com, www.youtube.com, m.youtube.com, youtu.be} after lower-casing and stripping one trailing dot — which also rules out IP hosts (incl. integer/hex forms), look-alike suffixes, punycode homoglyphs, percent-encoding and other subdomains (music.). Extracts the 11-char id from `/watch?v=` (conflicting `v` values rejected), `youtu.be/<id>`, `/shorts|embed|live/<id>` and rebuilds `https://www.youtube.com/watch?v=<id>`; only this canonical URL is stored or ever handed to yt-dlp. `POST /api/jobs/url` (JSON, ≤2048 chars) → 202 with no network I/O; failures → 422 `URL_NOT_ALLOWED`.
Network-level SSRF (DNS → public IPs only, redirect re-validation, byte/duration caps) stays in the worker (T-043).
Tooling: the design checker treated every `urllib` import as I/O, which would have forced this pure parser out of `core/`; it now allows `urllib.parse` specifically (still flags `urllib.request` and bare `import urllib`).
Measured: live 202 in ~8 ms warm (48 ms cold); CI asserts median of 5 < 100 ms.

### D-020 Worker fetch stage: yt-dlp metadata + SSRF-guarded download (2026-10-02, T-043)
Context: "Block private and internal IPs, including redirects"; hard duration cap; no shell interpolation; YouTube blocking handled gracefully.
Chosen:
- `adapters/ytdlp_fetcher.py`: yt-dlp only for **metadata** — argument list, `shell=False`, 45 s timeout, `--use-extractors youtube` (yt-dlp itself refuses non-YouTube URLs), `--` before the canonical URL; flags verified against yt-dlp 2026.08.19 `--help`/`--list-extractors`. Format `bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]`: video-only single stream (audio not analysed, nothing to merge). Only `User-Agent`/`Accept`/`Accept-Language` headers are forwarded (never cookies). Optional `YTDLP_COOKIES_B64` (0600 temp file, deleted in every outcome) and `YTDLP_PROXY`; neither logged; stderr never logged, only its classification.
- `core/ytdlp_errors.py`: bot check / 403 / 429 / age gate → `YOUTUBE_BLOCKED` ("…upload it instead"); private/removed/unavailable → `DOWNLOAD_FAILED`.
- `core/video_rules.check_remote_media`: live / unknown length / > 60 s / no single-stream URL rejected **before any bytes**.
- `adapters/safe_http_fetcher.py`: httpx2, `follow_redirects=False`, `trust_env=False`, ≤5 hops; each hop must be https, no userinfo, port 443, host `*.googlevideo.com` or exact YouTube hosts, and **all** DNS answers public (`core/net_rules.is_public_ip`, which also unwraps `::ffff:`/6to4/Teredo); 100 MB byte cap, 10 s connect / 30 s read / 120 s total.
- `services/fetch.fetch_url_video`: metadata → download → the **same** sniff + ffprobe + limits as uploads (`validate_video_file`) → blob `uploads/{video_id}/source.{ext}` → `set_media_for_worker`; blob removed if recording fails; temp dir always removed.
Mitigation (owner's choice): baseline clean failure + optional cookies/proxy by env, decided at deploy (F-005). With a proxy, googlevideo URLs are bound to the proxy's IP, so the download uses the same proxy; host allowlist still applies, IP check is best-effort (proxy resolves DNS).
Residual risk: DNS rebinding between our lookup and connect — allowed domains are Google-controlled; full fix (connect to vetted IP with SNI pinning) listed under "with more time".
Image: `yt-dlp[default,deno]` ships the JS runtime YouTube now requires (+~40–80 MB).
