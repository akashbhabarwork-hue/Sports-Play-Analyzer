"""Postgres job queue: SKIP LOCKED claim, lease + heartbeat, idempotent finish, dead-letter sweep.

All timestamps come from the database clock (now()), so worker clocks never matter.
Worker-only: nothing here filters by user_id, so it must never be reachable from a route.
"""

from uuid import UUID

from sqlalchemy import Engine, delete, insert, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..core.models import Job, JobOutcome
from .db_tables import job_results, player_tracks
from .pg_repos import db_errors, row_to

WORKER_CRASHED = "WORKER_CRASHED"
WORKER_CRASHED_MESSAGE = "Processing failed repeatedly. Please resubmit."

# One statement: pick the oldest claimable job, skipping rows other workers hold locks on,
# and take it. Served by the partial index ix_jobs_claimable.
CLAIM_SQL = text(
    """
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
    RETURNING j.*
    """
)

HEARTBEAT_SQL = text(
    """
    UPDATE jobs SET progress = :progress, stage = :stage, updated_at = now(),
      lease_expires_at = now() + make_interval(secs => :lease_s)
    WHERE id = :job_id AND locked_by = :worker_id AND status = 'processing'
    """
)

LOCK_OWNED_SQL = text(
    """
    SELECT 1 FROM jobs
    WHERE id = :job_id AND locked_by = :worker_id AND status = 'processing'
    FOR UPDATE
    """
)

SUCCEED_SQL = text(
    """
    UPDATE jobs SET status = 'succeeded', progress = 100, stage = NULL,
      finished_at = now(), updated_at = now(), lease_expires_at = NULL
    WHERE id = :job_id
    """
)

FAIL_SQL = text(
    """
    UPDATE jobs SET status = 'failed', error_code = :code, error_message = :message,
      finished_at = now(), updated_at = now(), lease_expires_at = NULL
    WHERE id = :job_id AND locked_by = :worker_id AND status = 'processing'
    """
)

SWEEP_SQL = text(
    """
    UPDATE jobs SET status = 'failed', error_code = :code, error_message = :message,
      finished_at = now(), updated_at = now(), lease_expires_at = NULL
    WHERE status = 'processing' AND lease_expires_at < now() AND attempts >= max_attempts
    """
)


class PostgresJobQueue:
    def __init__(self, engine: Engine):
        self.engine = engine

    @db_errors
    def claim(self, worker_id: str, lease_s: int) -> Job | None:
        with self.engine.begin() as conn:
            row = (
                conn.execute(CLAIM_SQL, {"worker_id": worker_id, "lease_s": lease_s})
                .mappings()
                .first()
            )
        return row_to(Job, row)

    @db_errors
    def heartbeat(
        self, job_id: UUID, worker_id: str, progress: int, stage: str, lease_s: int
    ) -> bool:
        params = {
            "job_id": job_id,
            "worker_id": worker_id,
            "progress": progress,
            "stage": stage,
            "lease_s": lease_s,
        }
        with self.engine.begin() as conn:
            return conn.execute(HEARTBEAT_SQL, params).rowcount == 1

    @db_errors
    def finish(self, job_id: UUID, worker_id: str, outcome: JobOutcome) -> bool:
        # Single transaction: lock our job, replace its rows, mark succeeded. A retry
        # replaces instead of duplicating; a worker that lost its lease writes nothing.
        with self.engine.begin() as conn:
            owned = conn.execute(LOCK_OWNED_SQL, {"job_id": job_id, "worker_id": worker_id})
            if owned.first() is None:
                return False
            conn.execute(delete(player_tracks).where(player_tracks.c.job_id == job_id))
            if outcome.tracks:
                conn.execute(
                    insert(player_tracks),
                    [
                        {
                            "job_id": job_id,
                            "track_id": t.track_id,
                            "team": t.team,
                            "frames_visible": t.frames_visible,
                            "distance_px": t.distance_px,
                            "distance_rel": t.distance_rel,
                            "possession_frames": t.possession_frames,
                            "heatmap": t.heatmap,
                            "track": t.track,
                        }
                        for t in outcome.tracks
                    ],
                )
            result = {"stats": outcome.stats, "annotated_key": outcome.annotated_key}
            conn.execute(
                pg_insert(job_results)
                .values(job_id=job_id, **result)
                .on_conflict_do_update(index_elements=[job_results.c.job_id], set_=result)
            )
            conn.execute(SUCCEED_SQL, {"job_id": job_id})
        return True

    @db_errors
    def fail(self, job_id: UUID, worker_id: str, error_code: str, message: str) -> bool:
        params = {"job_id": job_id, "worker_id": worker_id, "code": error_code, "message": message}
        with self.engine.begin() as conn:
            return conn.execute(FAIL_SQL, params).rowcount == 1

    @db_errors
    def sweep_dead(self) -> int:
        params = {"code": WORKER_CRASHED, "message": WORKER_CRASHED_MESSAGE}
        with self.engine.begin() as conn:
            return conn.execute(SWEEP_SQL, params).rowcount
