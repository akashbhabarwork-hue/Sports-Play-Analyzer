"""process_job against real Postgres: submit → claim → process → rows + blob (T-062).

FakeDetector stands in for the model; ffmpeg, the queue, repositories and blobs are real.
"""

import os

import pytest
from sqlalchemy import text

from app.adapters.ffprobe import FfprobeVideoProber
from app.adapters.pg_repos import PostgresUserRepo
from app.services.process import process_job
from app.services.submit import UploadLimits, submit_upload_job
from app.wiring import build_pipeline_ports, process_config
from tests.pipeline_helpers import make_clip, make_undecodable_clip, two_players

pytestmark = [pytest.mark.integration, pytest.mark.ffmpeg]

WORKER = "worker-it"
LIMITS = UploadLimits(max_bytes=10_000_000, max_duration_s=60)


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    return {"tiny": make_clip(d / "tiny.mp4"), "undecodable": make_undecodable_clip(d)}


@pytest.fixture
def run_job(engine, container):
    """Submit `clip` as a real upload, claim it like the worker does, then process it."""
    user = PostgresUserRepo(engine).upsert_from_oauth("google", "p-user", None, None, None)
    ports = build_pipeline_ports(container, two_players())
    cfg = process_config(container.settings)

    def run(clip: str):
        job = submit_upload_job(
            container.jobs, container.blobs, FfprobeVideoProber(), user.id, clip, "clip.mp4",
            LIMITS, {},
        )  # fmt: skip
        claimed = container.queue.claim(WORKER, cfg.lease_s)
        assert claimed is not None and claimed.id == job.id
        return job.id, process_job(claimed, ports, cfg, WORKER)

    return run


def row(engine, sql: str, job_id):
    with engine.connect() as conn:
        return conn.execute(text(sql), {"j": job_id}).mappings().one()


def test_process_job_writes_results_tracks_and_video(engine, container, clips, run_job, tmp_path):
    job_id, status = run_job(clips["tiny"])

    assert status == "succeeded"
    job = row(engine, "SELECT status, progress, error_code FROM jobs WHERE id = :j", job_id)
    assert (job["status"], job["progress"], job["error_code"]) == ("succeeded", 100, None)

    result = row(engine, "SELECT stats, annotated_key FROM job_results WHERE job_id = :j", job_id)
    stats = result["stats"]
    assert stats["players_tracked"] == 2 and stats["video"]["frames_analysed"] == 10
    assert {"players", "possession", "heatmaps", "teams", "config"} <= stats.keys()
    tracks = row(engine, "SELECT count(*) AS n FROM player_tracks WHERE job_id = :j", job_id)
    assert tracks["n"] == 2

    out = tmp_path / "annotated.mp4"
    container.blobs.get_to_path(result["annotated_key"], str(out))
    assert os.path.getsize(out) > 0
    assert FfprobeVideoProber().probe(str(out)).width == 160


def test_process_job_corrupt_but_sniffable_file_fails_with_decode_error(engine, clips, run_job):
    job_id, status = run_job(clips["undecodable"])

    assert status == "failed"
    job = row(engine, "SELECT status, error_code, error_message FROM jobs WHERE id = :j", job_id)
    assert (job["status"], job["error_code"]) == ("failed", "DECODE_ERROR")
    assert "re-exporting" in job["error_message"]
    results = row(engine, "SELECT count(*) AS n FROM job_results WHERE job_id = :j", job_id)
    assert results["n"] == 0
