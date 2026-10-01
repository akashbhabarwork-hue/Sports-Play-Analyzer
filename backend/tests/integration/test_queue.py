import threading
from uuid import UUID

import pytest
from sqlalchemy import text

from app.adapters.pg_queue import PostgresJobQueue
from app.adapters.pg_repos import PostgresJobRepo, PostgresUserRepo
from app.core.models import JobOutcome, NewVideo, PlayerTrack

pytestmark = pytest.mark.integration

LEASE = 60
UPLOAD = NewVideo(source_type="upload", storage_key="u/clip.mp4")


@pytest.fixture
def queue(engine):
    yield PostgresJobQueue(engine)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users CASCADE"))


@pytest.fixture
def make_jobs(engine, queue):
    user = PostgresUserRepo(engine).upsert_from_oauth("google", "q-user", None, None, None)
    repo = PostgresJobRepo(engine)

    def make(n: int = 1) -> list[UUID]:
        return [repo.create_with_video(user.id, UPLOAD, {}).id for _ in range(n)]

    return make


def job_row(engine, job_id: UUID):
    with engine.connect() as conn:
        return (
            conn.execute(text("SELECT * FROM jobs WHERE id = :j"), {"j": job_id}).mappings().one()
        )


def expire_lease(engine, job_id: UUID) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :j"),
            {"j": job_id},
        )


def count(engine, table: str, job_id: UUID) -> int:
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE job_id = :j"), {"j": job_id}
        ).scalar_one()


def outcome(n_tracks: int = 3) -> JobOutcome:
    tracks = tuple(
        PlayerTrack(
            job_id=None,  # ignored on write
            track_id=i,
            team="A" if i % 2 else "B",
            frames_visible=10,
            distance_px=100.0,
            distance_rel=0.1,
            possession_frames=0,
            heatmap={"w": 2, "h": 1, "counts": [1, 0], "max": 1},
            track=[[0.0, 0.5, 0.5]],
        )
        for i in range(1, n_tracks + 1)
    )
    return JobOutcome(
        stats={"players": n_tracks}, annotated_key="jobs/x/annotated.mp4", tracks=tracks
    )


def test_claim_takes_oldest_and_sets_lease(engine, queue, make_jobs):
    first, second = make_jobs(2)

    job = queue.claim("w1", LEASE)

    assert job.id == first
    assert (job.status, job.attempts) == ("processing", 1)
    row = job_row(engine, first)
    assert row["locked_by"] == "w1" and row["lease_expires_at"] > row["started_at"]
    assert queue.claim("w2", LEASE).id == second
    assert queue.claim("w3", LEASE) is None


def test_concurrent_claims_get_distinct_jobs(queue, make_jobs):
    ids = set(make_jobs(20))
    claimed: list[UUID] = []
    lock = threading.Lock()
    start = threading.Barrier(8)

    def worker(n: int) -> None:
        start.wait()
        while (job := queue.claim(f"w{n}", LEASE)) is not None:
            with lock:
                claimed.append(job.id)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(claimed) == len(set(claimed)) == 20
    assert set(claimed) == ids


def test_single_job_race_has_one_winner(queue, make_jobs):
    make_jobs(1)
    results = []
    start = threading.Barrier(8)

    def worker(n: int) -> None:
        start.wait()
        results.append(queue.claim(f"w{n}", LEASE))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(r is not None for r in results) == 1


def test_expired_lease_is_reclaimed_by_another_worker(engine, queue, make_jobs):
    (job_id,) = make_jobs(1)
    queue.claim("w1", LEASE)
    assert queue.claim("w2", LEASE) is None  # lease still held

    expire_lease(engine, job_id)
    job = queue.claim("w2", LEASE)

    assert job.id == job_id and job.attempts == 2
    assert job_row(engine, job_id)["locked_by"] == "w2"


def test_exhausted_attempts_are_swept_to_worker_crashed(engine, queue, make_jobs):
    (job_id,) = make_jobs(1)
    for worker in ("w1", "w2", "w3"):  # max_attempts = 3 crashes
        assert queue.claim(worker, LEASE).id == job_id
        expire_lease(engine, job_id)

    assert queue.claim("w4", LEASE) is None  # attempts exhausted: not claimable
    assert queue.sweep_dead() == 1
    row = job_row(engine, job_id)
    assert (row["status"], row["error_code"]) == ("failed", "WORKER_CRASHED")
    assert row["error_message"] and row["finished_at"] is not None
    assert queue.sweep_dead() == 0


def test_sweep_ignores_live_and_retryable_jobs(engine, queue, make_jobs):
    live, retryable = make_jobs(2)
    queue.claim("w1", LEASE)
    queue.claim("w2", LEASE)
    expire_lease(engine, retryable)  # attempts 1 < 3: retry, not dead

    assert queue.sweep_dead() == 0
    assert job_row(engine, live)["status"] == "processing"


def test_heartbeat_extends_lease_and_records_progress(engine, queue, make_jobs):
    (job_id,) = make_jobs(1)
    queue.claim("w1", LEASE)
    before = job_row(engine, job_id)["lease_expires_at"]

    assert queue.heartbeat(job_id, "w1", 40, "detecting", LEASE * 2) is True
    row = job_row(engine, job_id)
    assert (row["progress"], row["stage"]) == (40, "detecting")
    assert row["lease_expires_at"] > before


def test_finish_writes_results_once_and_is_idempotent(engine, queue, make_jobs):
    (job_id,) = make_jobs(1)
    queue.claim("w1", LEASE)

    assert queue.finish(job_id, "w1", outcome(3)) is True
    row = job_row(engine, job_id)
    assert (row["status"], row["progress"], row["lease_expires_at"]) == ("succeeded", 100, None)
    assert (count(engine, "player_tracks", job_id), count(engine, "job_results", job_id)) == (3, 1)

    # A second finish (e.g. a duplicate call) is refused and changes nothing.
    assert queue.finish(job_id, "w1", outcome(5)) is False
    assert (count(engine, "player_tracks", job_id), count(engine, "job_results", job_id)) == (3, 1)


def test_retried_job_replaces_rows_instead_of_duplicating(engine, queue, make_jobs):
    (job_id,) = make_jobs(1)
    queue.claim("w1", LEASE)
    assert queue.finish(job_id, "w1", outcome(3)) is True
    # Simulate a retry of an already-written job (e.g. results written, then the status
    # was reset by an operator) and finish it again with the same outcome.
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE jobs SET status = 'queued', finished_at = NULL WHERE id = :j"),
            {"j": job_id},
        )
    queue.claim("w2", LEASE)

    assert queue.finish(job_id, "w2", outcome(3)) is True
    assert (count(engine, "player_tracks", job_id), count(engine, "job_results", job_id)) == (3, 1)


def test_stale_worker_cannot_heartbeat_finish_or_fail(engine, queue, make_jobs):
    (job_id,) = make_jobs(1)
    queue.claim("w1", LEASE)
    expire_lease(engine, job_id)
    queue.claim("w2", LEASE)  # w1 lost the lease

    assert queue.heartbeat(job_id, "w1", 90, "saving", LEASE) is False
    assert queue.finish(job_id, "w1", outcome(3)) is False
    assert queue.fail(job_id, "w1", "INTERNAL", "boom") is False
    assert (count(engine, "player_tracks", job_id), count(engine, "job_results", job_id)) == (0, 0)
    row = job_row(engine, job_id)
    assert (row["status"], row["locked_by"], row["progress"]) == ("processing", "w2", 0)


def test_fail_marks_job_failed_with_readable_error(engine, queue, make_jobs):
    (job_id,) = make_jobs(1)
    queue.claim("w1", LEASE)

    assert queue.fail(job_id, "w1", "CORRUPT_FILE", "The file could not be decoded.") is True
    row = job_row(engine, job_id)
    assert (row["status"], row["error_code"]) == ("failed", "CORRUPT_FILE")
    assert queue.claim("w2", LEASE) is None  # handled failures are final, not retried
