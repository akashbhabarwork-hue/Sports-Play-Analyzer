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

### [x] T-022 · Queue: claim, heartbeat, finish, fail, sweep — `MUST` `20m` `[review-plan]`
- **Agent:** database
- **Depends on:** T-021
- **Why:** "Workers claim jobs safely (SELECT … FOR UPDATE SKIP LOCKED)"; "Idempotent retry… no jobs stuck in processing".
- **Scope:** queries from skill `postgres-job-queue`; lease + attempts; `finish_job` single transaction (delete→insert→succeeded); `fail_job`; dead-letter sweep.
- **Acceptance:** tests: concurrent claim gives distinct jobs; expired lease reclaimed; attempts exhausted → `failed/WORKER_CRASHED`; double finish → same row counts; stale heartbeat → rowcount 0.
- **Verify:** `pytest -q backend/tests -m integration -k queue`
- **Done notes:** `adapters/pg_queue.py` (`PostgresJobQueue`: claim / heartbeat / finish / fail / sweep_dead), `JobQueue` protocol + `JobOutcome`, `LEASE_SECONDS`/`WORKER_ID` config, wired into `Container`. 11 queue tests: distinct concurrent claims (8 threads, 20 jobs) and single-job race, expired lease reclaimed (attempts 2), exhausted → `failed/WORKER_CRASHED`, double finish refused with same counts, retried finish replaces rows, stale worker heartbeat/finish/fail → False and no writes, handled failures final. 4 mutations caught. See D-014.

## S3 · Authentication & authorization (45 m)

### [ ] T-030 · Google OAuth (Authorization Code + PKCE) + sessions — `MUST` `30m` `[review-plan]`
- **Agent:** auth-security
- **Depends on:** T-021
- **Why:** "OAuth 2.0 login… Authorization Code flow with PKCE, using a vetted library"; "Secure session handling".
- **Scope:** Authlib Starlette client (S256), `/auth/login`, `/auth/callback`, `/auth/logout`; transient SessionMiddleware cookie for OAuth state only; our `__Host-sid` httpOnly Secure SameSite=Lax cookie; hashed session tokens; decision entry for the async-route exception.
- **Acceptance:** local login with a real Google test account works; cookie flags verified in devtools; logout invalidates the session row; no token/secret in logs.
- **Verify:** manual login; `pytest -q -k auth`
- **Done notes:** **Code complete; waiting on the owner's manual Google login + devtools cookie check** (needs a real OAuth client; cannot be done by the agent). Authlib S256 PKCE + state + nonce, `/auth/login`, `/auth/callback`, `POST /auth/logout`, hashed rotated sessions in `__Host-sid`/`sid`, transient `oauth_tx` cookie, D-015 async exception. Tests: 6 unit (real Authlib redirect offline, config, 503, access log) + 7 integration (fake provider: cookie flags secure/dev, hash-only storage, rotation, logout, POST-only, failure redirect, nothing secret logged); mutations on rotation and hashing caught. Found and fixed: uvicorn access log leaked OAuth `code`/`state`.

### [x] T-031 · current_user, /api/me, CSRF origin check — `MUST` `10m`
- **Agent:** auth-security
- **Depends on:** T-030
- **Why:** server-side authz on every route; defence in depth for cookie auth.
- **Scope:** `current_user` dependency, `/api/me`, Origin + `X-Requested-With` check on unsafe methods.
- **Acceptance:** no cookie → 401 envelope; foreign Origin POST → 403; `/api/me` returns id/email/name.
- **Verify:** `pytest -q -k "me or csrf"`
- **Done notes:** `current_user` on an `/api` router (structural test guards it), `GET /api/me`, strict CSRF middleware (`X-Requested-With: fetch` + trusted Origin/Referer; `TRUSTED_ORIGINS` for Vite dev), UPPER_SNAKE error codes, frontend client sends the header. 32 tests for `-k "me or csrf"` (76 total): no/garbage/expired cookie → 401 envelope, `/api/me` fields, foreign Origin / missing header → 403, logout needs headers. Live: `/api/me` 401, plain curl POST 403, same-origin POST 204. See D-016.

### [x] T-032 · Test harness: login_as + two-user clients — `MUST` `5m`
- **Agent:** qa
- **Depends on:** T-031
- **Why:** "At least one authorization test (user A cannot read user B's job)".
- **Scope:** conftest fixtures (`settings`, `migrated_db`, `container`, `client`, `login_as`), truncate between tests.
- **Acceptance:** a placeholder test creates two users with separate cookie jars and hits `/api/me` as each.
- **Verify:** `pytest -q -m integration -k two_users`
- **Done notes:** Shared fixtures in `tests/integration/conftest.py`: `engine` (= migrated_db), `settings`/`settings_factory`, `container`/`container_factory` (real repos + `FakeGoogle`), `make_client` (one cookie jar per client), `client`, `login_as` (via the real `login_user` service), `csrf_headers`, autouse `clean_db` (TRUNCATE after every test — proven load-bearing: disabling it fails 5 tests). `test_me.py` / `test_auth_flow.py` refactored onto them; per-file truncates removed. `test_two_users.py`: separate identities, per-session logout, identity only from the cookie. 79 tests pass.

## S4 · Ingestion (1 h 10 m)

### [x] T-040 · BlobStore (local + S3) — `MUST` `15m`
- **Agent:** backend-api
- **Depends on:** T-010
- **Why:** "Annotated video… saved to storage"; web and worker on different machines in prod.
- **Scope:** `BlobStore` Protocol (`put_file`, `get_to_path`, `open_range`/`presigned_url`, `delete`), `LocalBlobStore` (path-traversal safe keys), `S3BlobStore` (boto3, endpoint from env); registry in wiring by `BLOB_BACKEND`.
- **Acceptance:** unit test for key validation (`..` rejected); local adapter round-trip test.
- **Verify:** `pytest -q -k blob`
- **Done notes:** `BlobStore` protocol, `core/blob_keys.py` (validation + deterministic keys + 300 s presign cap), `LocalBlobStore` (atomic writes, root containment), `S3BlobStore` (boto3; tested with moto), `BLOB_STORES` registry, production requires `s3`. 41 blob tests (key table incl. `..`/abs/backslash/%2e/hidden/NUL, local round trip/overwrite/range/missing/delete/symlink escape, S3 round trip/range/missing/presign expiry/bad bucket, config + registry); symlink-guard mutation caught. 120 tests total. See D-017.

### [x] T-041 · Upload endpoint with content validation — `MUST` `20m`
- **Agent:** backend-api (with auth-security review)
- **Depends on:** T-022, T-031, T-040
- **Why:** "File upload: Max 60 s and 100 MB"; "Check content by inspecting the file, not the extension… clean up temp files"; "returns a job_id immediately".
- **Scope:** `POST /api/jobs/upload`: Content-Length precheck, chunked copy with byte cap, magic-byte sniff (`core/file_sniff.py`), ffprobe check, store blob, insert video+job (config snapshot), 202 `{job_id}`; temp dir cleanup in `finally`.
- **Acceptance:** tiny.mp4 → 202; fake.mp4 → 415 UNSUPPORTED_FORMAT; corrupt.mp4 → 422 CORRUPT_FILE; oversize (test limit) → 413; long clip → 422 DURATION_EXCEEDED; temp dir empty after each.
- **Verify:** `pytest -q -k upload`
- **Done notes:** `POST /api/jobs/upload`: ASGI body-size cap (Content-Length + received bytes), chunked capped copy, magic-byte sniff, ffprobe + duration/size rules, blob-before-insert with cleanup on failure, 202 `{job_id}`; temp dir always removed. 31 upload tests (fixtures generated with ffmpeg: tiny → 202; fake → 415; corrupt and truncated → 422 CORRUPT_FILE; 61 s → 422 DURATION_EXCEEDED; oversize via Content-Length and chunked → 413; 401/403; nothing left in temp dir, blobs or DB after rejections). Mutations on temp cleanup and sniffing caught. Live: valid 202, fake 415, no CSRF 403. Pinned missing `python-multipart`; CI installs ffmpeg. See D-018.

### [x] T-042 · URL submit endpoint (syntactic SSRF rules) — `MUST` `10m`
- **Agent:** auth-security
- **Depends on:** T-041
- **Why:** "YouTube URL: fetched server-side"; "Host allowlist"; "Both paths must feed the same pipeline".
- **Scope:** `core/url_rules.py` normalise to canonical watch URL; `POST /api/jobs/url` inserts video(source_type=url)+job, 202. No network call in the request.
- **Acceptance:** unit table tests (accepted forms, rejected tricks incl. `youtube.com.evil.io`, userinfo, ports, http); endpoint returns 202 < 100 ms.
- **Verify:** `pytest -q -k url_rules`
- **Done notes:** `core/url_rules.py` (exact host allowlist, https, no userinfo/odd ports/IPs, id extraction for watch/youtu.be/shorts/embed/live, canonical rebuild) + `POST /api/jobs/url` → 202, canonical URL stored, no network. 63 url_rules cases + 9 endpoint tests (canonical stored, 422 without inserts, body shape, 401/403, median-of-5 < 100 ms). 4 mutations caught (suffix host match, no userinfo check, any port, storing raw input). Live: ~8 ms warm. Design checker narrowed to allow `urllib.parse` in core. See D-019.

### [x] T-043 · Worker fetch stage: yt-dlp + SSRF-safe download — `MUST` `25m` `[review-plan]`
- **Agent:** auth-security
- **Depends on:** T-042
- **Why:** "Block private and internal IPs, including redirects"; "Hard duration cap"; "No shell string interpolation"; YouTube blocking handled gracefully.
- **Scope:** `core/net_rules.py` (`is_public_ip`), `adapters/ytdlp_fetcher.py` (arg list, `--use-extractors youtube`, verified flags, optional cookies/proxy from env), `adapters/safe_http_fetcher.py` (manual redirects ≤5, per-hop host+IP validation, byte cap), stderr → `YOUTUBE_BLOCKED` classifier, duration check → `DURATION_EXCEEDED`.
- **Acceptance:** IP table tests; redirect-to-metadata-IP test blocked; classifier test; manual run on a real short YouTube URL locally downloads ≤60 s file.
- **Verify:** `pytest -q -k "net_rules or fetch or classifier"`
- **Done notes:** `core/net_rules.py`, `core/ytdlp_errors.py`, `check_remote_media`, `adapters/ytdlp_fetcher.py` (flags verified on 2026.08.19), `adapters/safe_http_fetcher.py`, `services/fetch.py`, shared `validate_video_file`, optional cookies/proxy config, `scripts/fetch_check.py`. 103 tests for this ticket (313 total): IP table incl. mapped/6to4/Teredo, media-host allowlist, classifier with the real T-014 stderr, downloader (redirect to 169.254.169.254 / http / private-resolving allowlisted host / mixed DNS / odd port / userinfo all blocked before contact, 5-hop limit, byte cap, statuses), yt-dlp adapter (arg list, `--` last, no shell, cookies 0600 + deleted even on failure, Cookie header never forwarded), service (store + record, reject long/live before download, re-probe downloaded bytes, cleanup). 7 mutations caught. **Manual real-URL run pending on the owner's machine** (this session cannot reach YouTube; the script fails cleanly here with DOWNLOAD_FAILED). See D-020.

## S5 · Tracking & metrics core — pure, no model (55 m)

### [x] T-050 · Tracker (ByteTrack-style) + fixture tests — `MUST` `25m`
- **Agent:** cv-pipeline
- **Depends on:** T-010
- **Why:** "Track players across frames with stable IDs (IoU or ByteTrack-style)"; "Unit tests for the tracking… using fixture detections".
- **Scope:** `core/models.py` types, `core/tracking.py` (`iou_matrix`, `associate`, `update`), fixtures `tracks_*.json`, the 8 tests listed in skill `player-tracking`.
- **Acceptance:** all 8 tests pass in < 1 s; params come from `TrackerParams` built from Settings.
- **Verify:** `pytest -q backend/tests/unit -k track`
- **Done notes:** `Box`/`Detection`/`Track`/`TrackerParams`/`TrackerState` in `core/models.py`; `core/tracking.py` (`iou_matrix`, `associate` via Hungarian, `predict`, `update`, `player_detections`, `pick_ball`); tracker settings + range validation in `config.py`, `wiring.tracker_params`. 7 fixtures from `tests/fixtures/make_track_fixtures.py`. 33 tests in ~0.1 s (the 8 from the skill + exact-max-age boundary, low boxes can't start or grow tracks, optimal-vs-greedy matching, min_hits=1, tiny-box filter, settings flow + 8 bad-setting cases). 7 mutations caught (no stage 2, no prediction, tentative kept on miss, max-age off-by-one, tentative in stage 2, minimised IoU, no IoU floor). `TRACKER_MAX_AGE` default 30 → 10. numpy + scipy pinned. See D-021.

### [x] T-051 · Metrics: distance, heatmaps, ball %, possession — `MUST` `20m`
- **Agent:** cv-pipeline
- **Depends on:** T-050
- **Why:** Metrics list in brief §6; "Unit tests for… metric maths".
- **Scope:** `core/metrics.py`, `core/heatmap.py`, `core/possession.py`; stats JSON builder matching the contract in skill `sports-metrics`.
- **Acceptance:** tests from skill (line distance, jitter, gap, heatmap edges, ball 25 %, possession hysteresis) pass.
- **Verify:** `pytest -q backend/tests/unit -k "metric or heatmap or possession"`
- **Done notes:** `FrameObservation`/`MetricsParams`/`MatchMetrics` models; `core/heatmap.py` (`heatmap_cell`, `build_heatmap`, `sum_heatmaps`), `core/possession.py` (candidate, hysteresis owners, counts), `core/metrics.py` (`path_distance`, `ball_visible_pct`, `build_stats` → stats JSON + `player_tracks` rows); metrics settings + validation, `wiring.metrics_params`. 33 tests in < 1 s (skill cases: 100 px line, ±1 px jitter, gap, heatmap edges + totals, 3/12 = 25.0, P1-1-frame/P2-5-frames hysteresis; plus standing wobble = 0, slow walker, short pass, ball gaps, stats contract, rows, team heatmap sums, empty video, settings). 9 mutations caught. See D-022.

### [x] T-052 · Team split by jersey colour — `MUST` `10m`
- **Agent:** cv-pipeline
- **Depends on:** T-051
- **Why:** "Per-player and team position heatmaps".
- **Scope:** pure k-means (k=2, fixed seed) on per-track colour features + `unknown` fallback; team heatmap aggregation.
- **Acceptance:** synthetic two-colour test → 2 teams; identical colours → `unknown`; team heatmap = sum of members.
- **Verify:** `pytest -q -k team`
- **Done notes:** `core/teams.py`: `torso_region`/`torso_pixels`, numpy `rgb_to_hsv` (matches `colorsys`), `colour_feature` (HSV cone, median), `kmeans_two` (farthest-point start, 20 iterations), `assign_teams` (A = lowest id, `unknown` fallbacks); `TEAM_MIN_SEPARATION` setting. 15 tests on synthetic frames: red/blue → 2 teams, identical → unknown, white vs black, red hue wrap, deterministic + order-independent, too few players, separation threshold, minority pixels, garbage sample, torso crop clamping, team heatmap = sum of members. 7 mutations caught (2 survived at first → robustness tests added). See D-023.

## S6 · Worker pipeline (1 h 25 m)

### [x] T-060 · ffmpeg frame reader/writer — `MUST` `15m`
- **Agent:** cv-pipeline
- **Depends on:** T-012
- **Why:** "Sample frames at a configurable FPS"; "Frames are streamed. The full video is never loaded into RAM"; arg arrays only.
- **Scope:** `adapters/ffmpeg_video.py`: probe, output size calc, streaming reader generator, encoder writer, stderr to temp files, kill/wait in finally.
- **Acceptance:** testsrc 2 s at fps 5 → 10 frames; encoded output probe-able; unit tests for size calc/read_exact.
- **Verify:** `pytest -q -m ffmpeg`
- **Done notes:** `adapters/ffmpeg_video.py` (`read_exact`, `FfmpegFrameReader.frames` generator, `FfmpegVideoEncoder.encode(frames)` → H.264 yuv420p +faststart); pure `core/video_frames.py` (`output_size` with even-floor + rotation swap, `expected_frames`); `VideoProbe.rotation`; `DecodeError`; `SAMPLE_FPS`/`MAX_FRAME_SIDE`/`ENCODE_CRF`/`ENCODE_PRESET`. testsrc 2 s @5 fps → 10 frames ✓, encoded output probes at 160×120 / 5 fps / 2 s ✓, rotated phone clip → portrait ✓, garbage → `DECODE_ERROR` ✓, early close kills ffmpeg (mutation-checked) ✓. 29 tests. See D-024.

### [x] T-061 · ONNX detector adapter + model in image — `MUST` `25m`
- **Agent:** cv-pipeline
- **Depends on:** T-060
- **Why:** "Detect players and the ball"; "Use pretrained models only"; licence justification.
- **Scope:** Dockerfile model download with verified URL + sha256; `adapters/onnx_detector.py` (letterbox, decode, NMS, class filter, one ball; keep player boxes down to `TRACKER_LOW_THRESH` for tracker stage 2, see D-021); output-shape assert; `FakeDetector`; pure NMS/decode tests.
- **Acceptance:** sample frame → persons detected (manual/`model` marker test); unit tests pass without the model.
- **Verify:** `pytest -q -k "nms or decode"`; `pytest -q -m model` locally
- **Done notes:** YOLOX-S `0.1.1rc0` (URL via GitHub API, sha256 `c5c2d13e…8063`, checked in Dockerfile → `/models/yolox_s.onnx`). Real model inspected: `[1,3,640,640]` → `[1,8400,85]` raw. Pure `core/detection.py` (decode, NMS, per-class person/ball scores, players ≥ `TRACKER_LOW_THRESH`, top-K, one ball, rescale + clip); `OnnxYoloxDetector` (letterbox, startup shape check → `MODEL_ERROR`); `FakeDetector`. 26 tests incl. `model` smoke on `tests/fixtures/people.jpg` (≥3 players ≥0.5); ~160 ms/frame locally. Pinned onnxruntime 1.30.0 + opencv-python-headless 5.0.0.93. See D-025.

### [x] T-062 · process_job service end-to-end — `MUST` `25m` `[review-plan]`
- **Agent:** cv-pipeline
- **Depends on:** T-022, T-043, T-051, T-052, T-061
- **Why:** Worker + Outputs sections of the brief; progress %.
- **Scope:** fetch (url) or load (upload) → probe → stream → detect → track → accumulate → draw → encode → upload `jobs/{id}/annotated.mp4` → `finish_job`; heartbeats with progress/stage; error-code mapping; temp cleanup.
- **Acceptance:** integration test with FakeDetector + tiny.mp4 → succeeded, stats JSON valid, player_tracks rows, blob exists; corrupt-but-sniffable file → failed/DECODE_ERROR.
- **Verify:** `pytest -q -m integration -k process_job`
- **Done notes:** Plan approved. `services/process.py` (`process_job`, `PipelinePorts`, `ProcessConfig`, streamed `_annotated_frames` generator feeding the encoder), pure `core/pipeline.py` (progress bands, team sampling, config snapshot), `adapters/opencv_annotator.py`, `FrameAnnotator` port, `LeaseLostError`, settings `HEARTBEAT_EVERY_FRAMES`/`TEAM_SAMPLE_EVERY`/`TEAM_MAX_SAMPLES`, wiring `process_config`/`build_pipeline_ports`/`build_detector`. Final input errors → `failed` + code; transient → re-raised for retry; lost lease → stop, no writes. Locally (real ffmpeg, fakes): success with stats/tracks/playable video, progress rises fetching→analysing→saving <100, temp dir cleaned, truncated-but-sniffable MP4 → `DECODE_ERROR`, `MODEL_ERROR` final, lost lease writes nothing, storage outage re-raised, URL source fetched first — 9 tests, 2 mutations caught. `tests/integration/test_process_job_pg.py` (submit → claim → process against Postgres) **not run locally — CI-only while Docker is deferred**. See D-026.

### [x] T-063 · Worker loop + crash-retry idempotency — `MUST` `15m`
- **Agent:** database
- **Depends on:** T-062
- **Why:** "Idempotent retry after a worker crash mid-job (no duplicate rows, no jobs stuck in processing)".
- **Scope:** `entrypoints/worker.py` (`run_once`, `run_forever`, SIGTERM handling, jittered polling); compose/Fly worker command.
- **Acceptance:** tests: crash simulation then retry → same row counts; exhausted attempts → failed; `docker compose up` processes a real upload end-to-end.
- **Verify:** `pytest -q -m integration -k "retry or idempot"`; manual compose run
- **Done notes:** `entrypoints/worker.py` (`WorkerContext`, `run_once`, `run_forever`, `install_stop_handlers`, `main`), shared `entrypoints/log_config.py`, `core/pipeline.poll_delay`, `WORKER_POLL_SECONDS`; compose worker: healthcheck disabled, 60 s stop grace, `restart: unless-stopped`. Unit (local): 13 tests — empty queue, claim→process, transient error and bug survive, DB outage while polling survives, drains then stops on signal, finishes current job, real SIGINT handler; missing model → exit 1 checked by hand. Integration (`tests/integration/test_worker_retry.py`, **CI-only while Docker is deferred**): crash mid-job → retry by another worker → same rows as a clean run (1 result, 2 tracks, attempts 2); rerun overwrites the same `jobs/{id}/annotated.mp4`; attempts exhausted → `failed/WORKER_CRASHED`, nothing written. **Queued for the final Docker pass:** `docker compose up` processing a real upload end-to-end. See D-027.

### [ ] T-064 · Performance check & default tuning — `SHOULD` `5m`
- **Agent:** cv-pipeline
- **Depends on:** T-063
- **Why:** reviewers wait for the job live; ADR needs speed numbers.
- **Scope:** time a 60 s sample on prod worker size; adjust `SAMPLE_FPS`/`DETECT_INPUT_SIZE`/threads; record fps + wall time.
- **Acceptance:** decision entry with measured numbers; 60 s clip < ~3 min on prod.
- **Verify:** worker logs timing line
- **Done notes:** _

## S7 · Read API (25 m)

### [x] T-070 · Job read endpoints — `MUST` `20m`
- **Agent:** backend-api
- **Depends on:** T-062
- **Why:** API list in brief: `GET /jobs/{id}`, `/stats`, `/players/{pid}`; UI needs list, video, heatmap.
- **Scope:** `GET /api/jobs`, `/api/jobs/{id}` (status, progress, stage, error), `/stats` (409 if not done), `/players/{pid}`, `/heatmap?team=`, `/video` (Range stream locally or 302 presigned ≤5 min); `/jobs/...` alias if decided in T-002; all user-scoped → 404.
- **Acceptance:** response shapes match skill `sports-metrics` contract; video seeks in browser.
- **Verify:** `pytest -q -m integration -k api_read`
- **Done notes:** Plan approved (owner chose: keep `/jobs…` aliases, SPA pages under `/app/…`). `GET /api/jobs`, `/{id}`, `/stats`, `/players/{pid}`, `/heatmap?team=`, `/video` (+ `/jobs…` aliases, hidden from OpenAPI; `POST /jobs/upload|url` aliases). 404 for missing/foreign before 409 for not-succeeded; video = presigned 302 (S3, ≤300 s) or Range streaming (200/206/416). 45 local tests (Range parser + API over user-scoped fakes); `tests/integration/test_api_read.py` (3, **CI-only**). Browser seek → T-083. See D-028.

### [x] T-071 · Required authorization test (A vs B) — `MUST` `5m`
- **Agent:** qa
- **Depends on:** T-070, T-032
- **Why:** "At least one authorization test (user A cannot read user B's job)".
- **Scope:** the test from skill `testing-strategy` covering every job-scoped endpoint + list.
- **Acceptance:** passes; fails if any repository `user_id` filter is removed (try it once, revert).
- **Verify:** `pytest -q -m integration -k user_b_cannot`
- **Done notes:** `tests/integration/test_authz_user_b_cannot.py` (26 cases, **CI-only**) + `tests/unit/test_authz_matrix.py` (27, local): every job endpoint × `/api/jobs` and `/jobs` aliases; B gets 404 (identical to a random id, even where A gets 409); A's jobs absent from B's list. Mutation-checked locally: removing `user_id` from job lookup (14 fail) or list (2 fail) is caught; a results-only filter removal is masked by the job-ownership check (defence in depth) and covered by T-021's repo test. SQL-level mutation re-run queued for the Docker pass.

## S8 · Frontend (1 h 10 m)

### [x] T-080 · Login page + auth guard + layout — `MUST` `10m`
- **Agent:** frontend
- **Depends on:** T-031, T-011
- **Scope:** Login page, `/api/me` guard, header with user + logout.
- **Acceptance:** logged-out user redirected to login; logout returns to login.
- **Verify:** manual + `npm run build`
- **Done notes:** S8 plan approved (Vitest + CI step). Routes under `/app/…` (`/`→`/app`, `/login`→`/app/login`); `AuthProvider` (GET /api/me), `RequireAuth` → `/app/login`, `Layout` header (Jobs, New analysis, user, Log out = POST /auth/logout → login); `LoginPage` ("Continue with Google" → `/auth/login`, known `?error=` codes only); typed `api` client + `types.ts`; app styles with light/dark tokens; Vitest 3.2.7 + `npm test` in CI. lint, typecheck, 10 tests, build ✓. Browser walkthrough with the S8 preview server after T-084. See D-029.

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
- [ ] **F-006** (T-070) ~~Add the `/jobs/...` aliases from D-004 alongside the read endpoints~~ (done in T-070, D-028); still open: return validation errors (e.g. missing `file` field, bad `?team=`) in the `{error:{code,message}}` envelope (T-091).
- [ ] **F-005** (devops, before T-100) Finish T-014: Fly app (web+worker), Neon, bucket, first deploy, `/health` live; re-run the YouTube spike from the prod worker (`fly ssh console`) and update D-010. Pick the mitigation (none / cookies / proxy) for A1.
- [x] **F-004** (T-020) Remove the "exit 5 = ok" allowance from the CI integration step once integration tests exist.
- [ ] **F-007** (backend-api) Snapshot the full pipeline config into `jobs.config` at submit time (today only `max_video_seconds`; `stats.config` already records the effective values per result — D-026).
- [ ] **F-008** (frontend, with F-002) Upgrade Vite 5 → current and Vitest 3 → matching major together: `npm audit` reports 1 high + 3 moderate advisories, all in dev-server/test tooling (`npm audit --omit=dev` = 0). Also pin the remaining `^` ranges in `package.json`.
