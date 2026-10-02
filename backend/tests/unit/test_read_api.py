"""Job read API over in-memory repos (T-070): shapes, 404/409 order, Range video, aliases."""

import pytest

from app.adapters.blob_local import LocalBlobStore
from tests.api_fakes import (
    VIDEO_BYTES,
    PresigningBlobs,
    World,
    add_job,
    add_user,
    browser,
    make_app,
)

SIZE = len(VIDEO_BYTES)


@pytest.fixture
def world():
    return World()


@pytest.fixture
def blobs(tmp_path):
    return LocalBlobStore(str(tmp_path / "blobs"))


@pytest.fixture
def setup(world, blobs):
    alice, token = add_user(world, "alice")
    done = add_job(world, blobs, alice, "succeeded", minute=1)
    queued = add_job(world, blobs, alice, "queued", minute=2)
    failed = add_job(world, blobs, alice, "failed", minute=3)
    client = browser(make_app(world, blobs), token)
    return client, done, queued, failed


@pytest.mark.parametrize("prefix", ["/api", ""])  # canonical and the D-004 /jobs… aliases
def test_read_api_list_is_newest_first_with_status_and_errors(setup, prefix):
    client, done, queued, failed = setup
    jobs = client.get(f"{prefix}/jobs").json()["jobs"]

    assert [j["id"] for j in jobs] == [str(failed.id), str(queued.id), str(done.id)]
    assert jobs[0]["error"] == {"code": "DECODE_ERROR", "message": "We couldn't decode frames."}
    assert jobs[1]["status"] == "queued" and jobs[1]["error"] is None
    assert {"progress", "stage", "created_at", "finished_at"} <= jobs[1].keys()


def test_read_api_detail_includes_video_info(setup):
    client, done, _, _ = setup
    body = client.get(f"/api/jobs/{done.id}").json()

    assert body["status"] == "succeeded" and body["progress"] == 100 and body["attempts"] == 1
    assert body["video"] == {"source_type": "upload", "original_filename": "match.mp4",
                             "source_url": None, "duration_s": 12.5}  # fmt: skip


def test_read_api_stats_returned_as_stored(setup):
    client, done, _, _ = setup
    stats = client.get(f"/api/jobs/{done.id}/stats").json()
    assert stats["players_tracked"] == 1 and "heatmaps" in stats


@pytest.mark.parametrize("suffix", ["/stats", "/players/1", "/heatmap", "/video"])
def test_read_api_results_before_success_are_409(setup, suffix):
    client, _, queued, failed = setup
    for job in (queued, failed):
        r = client.get(f"/api/jobs/{job.id}{suffix}")
        assert r.status_code == 409 and r.json()["error"]["code"] == "JOB_NOT_READY"


@pytest.mark.parametrize("suffix", ["", "/stats", "/players/1", "/heatmap", "/video"])
def test_read_api_unknown_job_is_404_in_the_error_envelope(setup, suffix):
    client, *_ = setup
    r = client.get(f"/api/jobs/00000000-0000-0000-0000-000000000000{suffix}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"


def test_read_api_player_detail_shape(setup):
    client, done, _, _ = setup
    body = client.get(f"/api/jobs/{done.id}/players/1").json()
    assert body == {
        "player_id": 1, "team": "A", "distance_px": 50.0, "distance_rel": 0.25,
        "frames_visible": 10, "possession_pct": 40.0,
        "track": [[0.0, 0.1, 0.9], [0.2, 0.2, 0.9]],
        "heatmap": {"w": 2, "h": 1, "counts": [3, 1], "max": 3},
    }  # fmt: skip
    assert client.get(f"/api/jobs/{done.id}/players/99").status_code == 404


def test_read_api_heatmap_by_team(setup):
    client, done, _, _ = setup
    assert client.get(f"/api/jobs/{done.id}/heatmap").json()["counts"] == [3, 1]
    assert client.get(f"/api/jobs/{done.id}/heatmap?team=B").json()["max"] == 0
    assert client.get(f"/api/jobs/{done.id}/heatmap?team=C").status_code == 422


def test_read_api_video_full_download(setup):
    client, done, _, _ = setup
    r = client.get(f"/api/jobs/{done.id}/video")

    assert r.status_code == 200 and r.content == VIDEO_BYTES
    assert r.headers["content-type"] == "video/mp4"
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["content-length"] == str(SIZE)
    assert r.headers["cache-control"].startswith("private")


@pytest.mark.parametrize(
    "header,start,end",
    [("bytes=0-99", 0, 99), ("bytes=5000-", 5000, SIZE - 1), ("bytes=-10", SIZE - 10, SIZE - 1)],
)
def test_read_api_video_range_lets_the_browser_seek(setup, header, start, end):
    client, done, _, _ = setup
    r = client.get(f"/api/jobs/{done.id}/video", headers={"Range": header})

    assert r.status_code == 206
    assert r.content == VIDEO_BYTES[start : end + 1]
    assert r.headers["content-range"] == f"bytes {start}-{end}/{SIZE}"
    assert r.headers["content-length"] == str(end - start + 1)


def test_read_api_video_unsatisfiable_range_is_416(setup):
    client, done, _, _ = setup
    r = client.get(f"/api/jobs/{done.id}/video", headers={"Range": f"bytes={SIZE}-"})
    assert r.status_code == 416 and r.headers["content-range"] == f"bytes */{SIZE}"


def test_read_api_video_redirects_to_short_lived_url_on_s3(world, tmp_path):
    blobs = PresigningBlobs(str(tmp_path / "blobs"))
    alice, token = add_user(world, "alice")
    done = add_job(world, blobs, alice)
    client = browser(make_app(world, blobs), token)

    r = client.get(f"/api/jobs/{done.id}/video", follow_redirects=False)

    assert r.status_code == 302 and r.headers["cache-control"] == "no-store"
    assert r.headers["location"].endswith("X-Amz-Expires=300")  # ≤ 5 min


@pytest.mark.parametrize("path", ["/api/jobs", "/jobs", "/api/jobs/{id}/video", "/jobs/{id}/stats"])
def test_read_api_requires_login(setup, world, blobs, path):
    _, done, _, _ = setup
    anonymous = browser(make_app(world, blobs), None)
    assert anonymous.get(path.format(id=done.id)).status_code == 401


def test_read_api_aliases_are_hidden_from_openapi(setup):
    client, *_ = setup
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/jobs/{job_id}/stats" in paths
    assert not any(p.startswith("/jobs") for p in paths)
