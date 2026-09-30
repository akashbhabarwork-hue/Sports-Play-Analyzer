---
name: postgres-job-queue
description: Designs and implements the Postgres schema, Alembic migrations, indexes and a crash-safe job queue using SELECT FOR UPDATE SKIP LOCKED with leases, heartbeats, attempt limits and idempotent result writes. Use when working on tables, migrations, job claiming, worker retries, progress updates or persisting results.
---

# Postgres job queue (SKIP LOCKED + leases)

## Why this design (say this in the review)
- Postgres is already required, so the queue lives there: one system, transactional with results.
- `FOR UPDATE SKIP LOCKED` lets many workers pick different rows without blocking each other.
- A **lease** (`lease_expires_at`) + heartbeat solves "worker died mid-job": when the lease
  lapses, the job becomes claimable again. `attempts` caps retries so a poison job ends `failed`.
- Results are written in one transaction with natural primary keys, so a retry replaces rows
  instead of duplicating them.

## Schema (first Alembic revision)
```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid() (built-in on PG13+, harmless)

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL, provider_sub text NOT NULL,
  email text, name text, avatar_url text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_users_provider_sub UNIQUE (provider, provider_sub)
);
CREATE TABLE sessions (
  token_hash bytea PRIMARY KEY,                      -- sha256 of cookie token
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL
);
CREATE INDEX ix_sessions_user ON sessions(user_id);

CREATE TABLE videos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source_type text NOT NULL CHECK (source_type IN ('upload','url')),
  source_url text, original_filename text,
  storage_key text,                                   -- null until fetched (url path)
  size_bytes bigint, duration_s real, width int, height int, fps real,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued','processing','succeeded','failed')),
  progress smallint NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
  stage text,                                         -- fetching|decoding|detecting|saving
  error_code text, error_message text,
  attempts smallint NOT NULL DEFAULT 0, max_attempts smallint NOT NULL DEFAULT 3,
  locked_by text, lease_expires_at timestamptz,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,          -- snapshot of effective settings
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz, finished_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_jobs_claimable ON jobs (created_at)
  WHERE status IN ('queued','processing');
CREATE INDEX ix_jobs_user_created ON jobs (user_id, created_at DESC);

CREATE TABLE job_results (
  job_id uuid PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  stats jsonb NOT NULL, annotated_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE player_tracks (
  job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  track_id int NOT NULL,
  team text, frames_visible int NOT NULL,
  distance_px real NOT NULL, distance_rel real NOT NULL,
  possession_frames int NOT NULL DEFAULT 0,
  heatmap jsonb NOT NULL,                             -- {"w":32,"h":18,"counts":[...]}
  track jsonb NOT NULL,                               -- [[t, x, y], ...] normalised
  PRIMARY KEY (job_id, track_id)
);
```
Write it as SQLAlchemy Core `Table`s + `op.create_table` in Alembic (autogenerate then review).
Use a `MetaData(naming_convention=...)` so constraint names are stable.

## Claim (one statement, atomic)
```sql
WITH c AS (
  SELECT id FROM jobs
  WHERE (status = 'queued'
         OR (status = 'processing' AND lease_expires_at < now()))
    AND attempts < max_attempts
  ORDER BY created_at
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE jobs j
SET status = 'processing', attempts = j.attempts + 1, locked_by = :worker_id,
    lease_expires_at = now() + make_interval(secs => :lease_s),
    started_at = COALESCE(j.started_at, now()), updated_at = now(),
    error_code = NULL, error_message = NULL
FROM c WHERE j.id = c.id
RETURNING j.*;
```
## Dead-letter sweep (run each poll loop, cheap thanks to partial index)
```sql
UPDATE jobs SET status='failed', error_code='WORKER_CRASHED',
  error_message='Processing failed repeatedly. Please resubmit.', finished_at=now(), updated_at=now()
WHERE status='processing' AND lease_expires_at < now() AND attempts >= max_attempts;
```
## Heartbeat / progress (guarded by ownership so a zombie worker can't overwrite)
```sql
UPDATE jobs SET progress=:p, stage=:stage, updated_at=now(),
  lease_expires_at = now() + make_interval(secs => :lease_s)
WHERE id=:id AND locked_by=:worker_id AND status='processing';
```
If rowcount = 0 → this worker lost the lease → stop processing, do not write results.

## Finish (single transaction)
```
BEGIN;
  SELECT 1 FROM jobs WHERE id=:id AND locked_by=:worker_id AND status='processing' FOR UPDATE;
  DELETE FROM player_tracks WHERE job_id=:id;
  INSERT INTO player_tracks ... (bulk);
  INSERT INTO job_results ... ON CONFLICT (job_id) DO UPDATE SET stats=EXCLUDED.stats, annotated_key=EXCLUDED.annotated_key;
  UPDATE jobs SET status='succeeded', progress=100, finished_at=now(), lease_expires_at=NULL WHERE id=:id;
COMMIT;
```
Upload the annotated video to the deterministic key `jobs/{job_id}/annotated.mp4` BEFORE the
transaction (overwrite is idempotent). Failures: set `failed` + code + message in one UPDATE
guarded by `locked_by`.

## Worker loop
```
while not stopping:
    sweep_dead_jobs()
    job = claim()
    if not job: sleep(POLL_INTERVAL_S with jitter); continue
    try: process_job(job)            # heartbeats inside
    except AppError as e: fail(job, e.code, e.message)
    except Exception: log.exception(...); fail(job, "INTERNAL", "Unexpected error")
```
Handle SIGTERM: stop claiming; let the lease expire (or re-queue explicitly) for in-flight job.
Use `LEASE_SECONDS` ≈ 60 and heartbeat every ≈10 s (both env-configurable).

## Tests to write
- Two connections claim concurrently → different ids (or one gets none).
- Simulate crash: claim, don't heartbeat, move `lease_expires_at` into the past → reclaimed,
  attempts incremented; after `max_attempts` → `failed/WORKER_CRASHED`.
- Run finish twice for the same job → identical `player_tracks` row count.
- Stale worker heartbeat after reclaim → rowcount 0.

## Index justification lines for ADR
- `ix_jobs_claimable` partial: claim query filters on status and orders by `created_at`; partial
  keeps the index to only live jobs so it stays tiny as history grows.
- `ix_jobs_user_created`: `GET /api/jobs` = `WHERE user_id=? ORDER BY created_at DESC LIMIT 50`.
