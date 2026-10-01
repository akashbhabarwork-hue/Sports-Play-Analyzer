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
