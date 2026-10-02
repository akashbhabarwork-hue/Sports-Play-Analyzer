# Stage S02 — Database & job queue

**Dates:** 2026-10-01 → 2026-10-01 · **Tickets:** T-020, T-021, T-022

## What was built (plain English)
- A versioned Postgres schema (Alembic revision `0001`): users, sessions, videos, jobs, job results and player tracks, with the job state machine enforced by CHECK constraints.
- Three indexes, each justified with `EXPLAIN` on 20k seeded jobs (D-011).
- Repositories that make per-user isolation the default: every read of a user's videos, jobs or results takes `user_id` in its SQL; a unit test fails the build on any unscoped read.
- A crash-safe job queue in Postgres: workers claim with `FOR UPDATE SKIP LOCKED`, hold a lease kept alive by heartbeats, write results in one transaction, and a sweep fails jobs that crashed three times.

## How it works now (data flow for this stage)
```mermaid
sequenceDiagram
  participant API as API (later: S4/S7)
  participant R as Repos (pg_repos.py)
  participant DB as Postgres
  participant W as Worker (later: T-063)
  participant Q as Queue (pg_queue.py)
  API->>R: create_with_video(user_id, video, config)
  R->>DB: INSERT video + job (one tx) → status=queued
  W->>Q: sweep_dead()
  W->>Q: claim(worker_id, lease)
  Q->>DB: CTE … FOR UPDATE SKIP LOCKED → processing, attempts+1
  loop while processing
    W->>Q: heartbeat(progress, stage) — guarded by locked_by
  end
  alt success
    W->>Q: finish(outcome) — lock, delete tracks, insert, upsert result, succeeded
  else handled error
    W->>Q: fail(code, message) — final
  else worker dies
    DB-->>Q: lease lapses → reclaimed (≤3 attempts) → sweep → failed/WORKER_CRASHED
  end
  API->>R: get(user_id, job_id) — None if not yours → 404
```

## Key decisions (and why)
| ID | Decision | Why | Alternative rejected |
|---|---|---|---|
| D-011 | Partial `ix_jobs_claimable`, `ix_jobs_user_created (user_id, created_at DESC)`, `ix_sessions_user` | Each serves a hot query; the partial index stays 16 kB vs 1.1 MB because finished jobs drop out | Unindexed / full indexes |
| D-012 | Core tables as source of truth + reviewed autogenerate + `alembic check` test | Model and migrations cannot drift unnoticed | Hand-written DDL only |
| D-013 | `user_id` in every user-data query; cross-user = `None` | Server-side isolation (A3) without leaking existence | Authorization checks in each route |
| D-014 | SKIP LOCKED + lease + ownership-guarded writes; handled errors final, crashes retried ≤3 | No double processing, no stuck jobs, fast clean failures (A2) | Retrying transient errors; external queue (Redis/Celery) |

## How to demo / verify
```bash
service postgresql start   # or: docker compose up -d db
export TEST_DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app_test
cd backend
alembic upgrade head && alembic downgrade base && alembic upgrade head   # with DATABASE_URL set
pytest -q -m integration -k "migration or repo or queue"
```

## Tests added
- `tests/integration/test_migrations.py` (13): migration cycle, drift guard, every constraint, cascades, index definitions.
- `tests/integration/test_repos.py` (7) + `tests/unit/test_ports.py` (3): user scoping, atomic create, sessions.
- `tests/integration/test_queue.py` (11): concurrent claims, lease expiry, sweep, idempotent finish, stale worker.
- Mutation-checked: each safety guard was removed once and a test went red.

## AI corrections during this stage
- Imported a non-existent `sqlalchemy.Real` (it is `REAL`) — caught by the first DDL compile.
- An atomicity test that could not fail (`config=None` is stored as JSON `null`) — replaced with a value Postgres rejects and mutation-checked (AI_USAGE #4).

## Known gaps / tech debt
- No API routes use the repos yet (S4/S7); the worker loop that drives the queue is T-063.
- F-003: `pydantic` still unpinned. F-005: deploy + prod YouTube re-check still open (T-014 partial).
- `videos.user_id` / `jobs.video_id` FKs are deliberately unindexed (only cascading deletes touch them).

## Interview prep — questions you may get about this stage
1. Q: How do two workers avoid processing the same job?
   A: `claim` is a single statement (`backend/app/adapters/pg_queue.py`, `CLAIM_SQL`): a CTE selects the oldest claimable row `FOR UPDATE SKIP LOCKED LIMIT 1` and the outer `UPDATE … RETURNING` takes it. A row locked by one transaction is skipped by the others; `test_concurrent_claims_get_distinct_jobs` runs 8 threads over 20 jobs.
2. Q: What happens if a worker crashes mid-job?
   A: Its lease (`lease_expires_at`) stops being extended, so after `LEASE_SECONDS` the job matches the claim condition again and another worker takes it with `attempts + 1`. After `max_attempts` (3), `sweep_dead` marks it `failed/WORKER_CRASHED`, so nothing stays in `processing`.
3. Q: How is a retry idempotent?
   A: `finish` runs in one transaction: it locks the job only if this worker still owns it, deletes the job's `player_tracks`, inserts the new ones, upserts `job_results` (PK `job_id`) and sets `succeeded`. Natural keys `(job_id, track_id)` and `job_id` make duplicates impossible.
4. Q: How do you stop user B reading user A's job?
   A: Every repository read for user data takes `user_id` and puts it in the WHERE clause (results join `jobs`), returning `None` for "not yours" so the API can 404. `tests/unit/test_ports.py` fails if a method on the Video/Job/Result protocols lacks `user_id` without being named `*_for_worker`.
5. Q: Justify one index.
   A: `ix_jobs_claimable` is partial on `created_at WHERE status IN ('queued','processing')`. The claim runs every poll; EXPLAIN shows `Index Scan using ix_jobs_claimable` with no sort, and it is 16 kB on 20k jobs because finished jobs are excluded (D-011).
