---
trigger: model_decision
description: Apply when creating or editing database tables, Alembic migrations, SQL queries, indexes, the Postgres job queue, job claiming, leases, retries or result persistence.
---

# Database & job queue rules

Deep guide: skill `postgres-job-queue`.

## Migrations
- Every schema change is a new Alembic revision in `backend/migrations/versions/`. Never edit an
  applied revision; never run DDL by hand; never `metadata.create_all()` in app code.
- Every revision has a working `downgrade()`.
- Prefer expand → migrate → contract so the previous app image still runs after `upgrade`
  (this is what makes rollback-by-image safe; see ADR).
- Name constraints explicitly (naming convention on `MetaData`).

## Schema essentials
- `users`, `sessions`, `videos`, `jobs`, `job_results`, `player_tracks`.
- UUID primary keys (`gen_random_uuid()`), `timestamptz` everywhere, `created_at default now()`.
- Foreign keys with explicit `ON DELETE` (children `CASCADE` to their job/user).
- `jobs.user_id NOT NULL` — every job belongs to a user.
- `jobs.status` constrained by CHECK: `queued | processing | succeeded | failed`.
- Idempotency keys: `player_tracks PRIMARY KEY (job_id, track_id)`, `job_results PRIMARY KEY (job_id)`.

## Indexes (each must be justified in ADR with the query it serves)
- `ix_jobs_claimable` partial index on `jobs (created_at) WHERE status IN ('queued','processing')`
  → serves the worker claim query, stays tiny because finished jobs drop out.
- `ix_jobs_user_created` on `jobs (user_id, created_at DESC)` → serves "my jobs" list.
- `ix_sessions_user` on `sessions(user_id)` → logout-all / cleanup.

## Queue semantics
- Claim with one statement: CTE `SELECT id … FOR UPDATE SKIP LOCKED LIMIT 1` + `UPDATE … RETURNING`.
- Claimable = `queued` OR (`processing` AND `lease_expires_at < now()`) AND `attempts < max_attempts`.
- Worker heartbeats every few seconds: extends `lease_expires_at`, writes `progress`, `stage`.
- Exhausted attempts → `failed` with `error_code = 'WORKER_CRASHED'`. No job can stay `processing`
  past its lease.
- Results are written in ONE transaction: delete-existing-for-job + insert + mark `succeeded`.
  Blob keys are deterministic (`jobs/{job_id}/annotated.mp4`) so a retry overwrites, not duplicates.

## Access pattern rule
Every repository method that reads user data takes `user_id` and puts it in the WHERE clause.
There is no `get_job(job_id)` without `user_id` outside the worker.
