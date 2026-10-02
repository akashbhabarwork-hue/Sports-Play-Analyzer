"""Crash mid-job → retry → same rows; attempts exhausted → failed (T-063, real Postgres).

A "crash" is a detector that blows up partway through the video: the worker logs it, writes
nothing, and the job keeps its lease until it lapses — exactly what happens when a worker
process dies.
"""

import pytest
from sqlalchemy import text

from app.adapters.ffprobe import FfprobeVideoProber
from app.adapters.pg_repos import PostgresUserRepo
from app.entrypoints.worker import WorkerContext, run_once
from app.services.submit import UploadLimits, submit_upload_job
from app.wiring import build_pipeline_ports, process_config
from tests.pipeline_helpers import make_clip, two_players

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]

LIMITS = UploadLimits(max_bytes=10_000_000, max_duration_s=60)


class CrashingDetector:
    """Works for a few frames, then dies like a worker killed mid-job."""

    def __init__(self, crash_at: int = 3):
        self.calls, self.crash_at = 0, crash_at

    def detect(self, frame):
        self.calls += 1
        if self.calls > self.crash_at:
            raise RuntimeError("simulated worker crash")
        return []


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    return make_clip(tmp_path_factory.mktemp("clip") / "tiny.mp4")


@pytest.fixture
def submit(engine, container, clip):
    user = PostgresUserRepo(engine).upsert_from_oauth("google", "w-user", None, None, None)

    def make():
        return submit_upload_job(container.jobs, container.blobs, FfprobeVideoProber(), user.id,
                                 clip, "clip.mp4", LIMITS, {}).id  # fmt: skip

    return make


def worker(container, detector, worker_id: str) -> WorkerContext:
    cfg = process_config(container.settings)
    return WorkerContext(container.queue, build_pipeline_ports(container, detector), cfg,
                         worker_id, poll_seconds=0.1)  # fmt: skip


def expire_lease(engine, job_id) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :j"),
            {"j": job_id},
        )


def job_row(engine, job_id):
    with engine.connect() as conn:
        return (
            conn.execute(text("SELECT * FROM jobs WHERE id = :j"), {"j": job_id}).mappings().one()
        )


def counts(engine, job_id) -> tuple[int, int]:
    with engine.connect() as conn:
        results = conn.execute(
            text("SELECT count(*) FROM job_results WHERE job_id = :j"), {"j": job_id}
        ).scalar_one()
        tracks = conn.execute(
            text("SELECT count(*) FROM player_tracks WHERE job_id = :j"), {"j": job_id}
        ).scalar_one()
    return results, tracks


def test_retry_after_crash_mid_job_gives_same_rows_as_a_clean_run(engine, container, submit):
    crashed_id = submit()
    assert run_once(worker(container, CrashingDetector(), "w-dies")) == "error"

    row = job_row(engine, crashed_id)
    assert row["status"] == "processing" and row["locked_by"] == "w-dies"  # held until lease lapses
    assert counts(engine, crashed_id) == (0, 0)  # nothing half-written

    expire_lease(engine, crashed_id)
    assert run_once(worker(container, two_players(), "w-rescuer")) == "succeeded"

    row = job_row(engine, crashed_id)
    assert (row["status"], row["attempts"], row["progress"]) == ("succeeded", 2, 100)

    clean_id = submit()
    assert run_once(worker(container, two_players(), "w-clean")) == "succeeded"
    assert counts(engine, crashed_id) == counts(engine, clean_id) == (1, 2)


def test_idempotent_rerun_overwrites_the_same_annotated_blob(engine, container, submit):
    job_id = submit()
    run_once(worker(container, CrashingDetector(crash_at=8), "w1"))  # dies late in the video
    expire_lease(engine, job_id)
    run_once(worker(container, two_players(), "w2"))

    with engine.connect() as conn:
        key = conn.execute(
            text("SELECT annotated_key FROM job_results WHERE job_id = :j"), {"j": job_id}
        ).scalar_one()
    assert key == f"jobs/{job_id}/annotated.mp4"  # deterministic: retries overwrite, never add
    assert container.blobs.size(key) > 0


def test_retry_attempts_exhausted_marks_job_failed_not_stuck(engine, container, submit):
    job_id = submit()
    max_attempts = job_row(engine, job_id)["max_attempts"]
    for _ in range(max_attempts):
        assert run_once(worker(container, CrashingDetector(), "w-dies")) == "error"
        expire_lease(engine, job_id)

    assert run_once(worker(container, two_players(), "w-next")) is None  # swept, not claimable

    row = job_row(engine, job_id)
    assert (row["status"], row["error_code"]) == ("failed", "WORKER_CRASHED")
    assert row["attempts"] == max_attempts
    assert counts(engine, job_id) == (0, 0)
