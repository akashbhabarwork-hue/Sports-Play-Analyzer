"""T-085: sport + title travel from both submit endpoints to the stored video (in-memory repos)."""

import pytest

from app.adapters.blob_local import LocalBlobStore
from tests.api_fakes import World, add_user, browser, make_app
from tests.pipeline_helpers import make_clip

CSRF = {"Origin": "http://localhost:8000", "X-Requested-With": "fetch"}
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def setup(tmp_path):
    w = World()
    _, token = add_user(w, "alice")
    blobs = LocalBlobStore(str(tmp_path / "blobs"))
    return w, browser(make_app(w, blobs), token)


def only_video(w):
    (video,) = w.videos.values()
    return video


@pytest.mark.parametrize("prefix", ["/api", ""])
def test_url_submit_stores_sport_and_clean_title(setup, prefix):
    w, client = setup
    body = {"url": URL, "sport": "Basketball", "title": "  Semi   final "}
    r = client.post(f"{prefix}/jobs/url", headers=CSRF, json=body)
    assert r.status_code == 202
    video = only_video(w)
    assert (video.sport, video.title) == ("basketball", "Semi final")


def test_url_submit_defaults_to_football_without_title(setup):
    w, client = setup
    assert client.post("/api/jobs/url", headers=CSRF, json={"url": URL}).status_code == 202
    assert (only_video(w).sport, only_video(w).title) == ("football", None)


def test_url_submit_rejects_unknown_sport_in_the_envelope(setup):
    w, client = setup
    r = client.post("/api/jobs/url", headers=CSRF, json={"url": URL, "sport": "cricket"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_SPORT"
    assert w.jobs == {}


def test_url_submit_rejects_title_over_120(setup):
    _, client = setup
    r = client.post("/api/jobs/url", headers=CSRF, json={"url": URL, "title": "x" * 121})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.ffmpeg
def test_upload_carries_sport_and_title_form_fields(setup, tmp_path):
    w, client = setup
    clip = make_clip(tmp_path / "clip.mp4")
    with open(clip, "rb") as f:
        r = client.post("/api/jobs/upload", headers=CSRF,
                        files={"file": ("clip.mp4", f, "video/mp4")},
                        data={"sport": "basketball", "title": "Drill 3"})  # fmt: skip
    assert r.status_code == 202, r.text
    video = only_video(w)
    assert (video.sport, video.title, video.original_filename) == (
        "basketball",
        "Drill 3",
        "clip.mp4",
    )


@pytest.mark.ffmpeg
def test_upload_with_bad_sport_is_rejected_before_storing_anything(setup, tmp_path):
    w, client = setup
    clip = make_clip(tmp_path / "clip.mp4")
    with open(clip, "rb") as f:
        files = {"file": ("clip.mp4", f, "video/mp4")}
        r = client.post("/api/jobs/upload", headers=CSRF, files=files, data={"sport": "golf"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_SPORT"
    assert w.jobs == {}
