"""Job read API against real Postgres + disk blobs (T-070). Runs in CI."""

import os
import tempfile

import pytest

from app.core.models import JobOutcome, NewVideo, PlayerTrack

pytestmark = pytest.mark.integration

GRID = {"w": 2, "h": 1, "counts": [3, 1], "max": 3}
VIDEO_BYTES = bytes(range(256)) * 40
THUMB_BYTES = b"\xff\xd8\xff\xe0fake-jpeg\xff\xd9"
WORKER = "w-read"


def seed_succeeded_job(container, user_id):
    """A job that went through the real queue: create → claim → finish (+ annotated blob)."""
    job = container.jobs.create_with_video(
        user_id, NewVideo(source_type="upload", storage_key="u/clip.mp4"), {}
    )
    claimed = container.queue.claim(WORKER, 60)
    assert claimed.id == job.id
    key = f"jobs/{job.id}/annotated.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "a.mp4")
        with open(src, "wb") as f:
            f.write(VIDEO_BYTES)
        container.blobs.put_file(key, src, "video/mp4")
    stats = {
        "players_tracked": 1,
        "players": [
            {
                "player_id": 1,
                "team": "A",
                "distance_px": 50.0,
                "distance_rel": 0.25,
                "frames_visible": 10,
                "possession_pct": 40.0,
            }
        ],
        "heatmaps": {"all": GRID, "A": GRID, "B": GRID},
    }
    track = PlayerTrack(None, 1, "A", 10, 50.0, 0.25, 4, GRID, [[0.0, 0.1, 0.9]])
    assert container.queue.finish(job.id, WORKER, JobOutcome(stats, key, (track,)))
    thumb = f"videos/{job.video_id}/thumbnail.jpg"  # what the worker saves from frame 0
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "t.jpg")
        with open(src, "wb") as f:
            f.write(THUMB_BYTES)
        container.blobs.put_file(thumb, src, "image/jpeg")
    container.videos.set_thumbnail_for_worker(job.video_id, thumb)
    return job


def test_api_read_list_and_thumbnail_from_postgres(client, login_as, container):
    alice = login_as(client, "alice")
    job = seed_succeeded_job(container, alice.id)
    (item,) = client.get("/api/jobs").json()["jobs"]
    assert item["sport"] == "football" and item["source_type"] == "upload"
    assert item["thumbnail_url"] == f"/api/jobs/{job.id}/thumbnail"
    r = client.get(item["thumbnail_url"])
    assert r.status_code == 200 and r.content == THUMB_BYTES


def test_api_read_succeeded_job_end_to_end(client, login_as, container):
    alice = login_as(client, "alice")
    job = seed_succeeded_job(container, alice.id)
    base = f"/api/jobs/{job.id}"

    assert [j["id"] for j in client.get("/api/jobs").json()["jobs"]] == [str(job.id)]
    detail = client.get(base).json()
    assert (detail["status"], detail["progress"]) == ("succeeded", 100)
    assert detail["video"]["source_type"] == "upload"
    assert client.get(f"{base}/stats").json()["players_tracked"] == 1
    player = client.get(f"{base}/players/1").json()
    assert player["possession_pct"] == 40.0 and player["heatmap"] == GRID
    assert client.get(f"{base}/heatmap?team=A").json() == GRID

    full = client.get(f"{base}/video")
    assert full.status_code == 200 and full.content == VIDEO_BYTES
    part = client.get(f"{base}/video", headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and part.content == VIDEO_BYTES[10:20]


def test_api_read_aliases_match_canonical_routes(client, login_as, container):
    alice = login_as(client, "alice")
    job = seed_succeeded_job(container, alice.id)
    for suffix in ("", "/stats", "/players/1", "/heatmap"):
        assert (
            client.get(f"/jobs/{job.id}{suffix}").json()
            == client.get(f"/api/jobs/{job.id}{suffix}").json()
        )


def test_api_read_queued_job_results_are_409(client, login_as, container):
    alice = login_as(client, "alice")
    job = container.jobs.create_with_video(alice.id, NewVideo(source_type="url",
                                           source_url="https://youtu.be/x"), {})  # fmt: skip
    assert client.get(f"/api/jobs/{job.id}").json()["status"] == "queued"
    r = client.get(f"/api/jobs/{job.id}/stats")
    assert r.status_code == 409 and r.json()["error"]["code"] == "JOB_NOT_READY"
