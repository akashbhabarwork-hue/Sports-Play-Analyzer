"""Required A-vs-B authorization test (T-071), over user-scoped in-memory repos (runs locally).

The same matrix against real Postgres is tests/integration/test_authz_user_b_cannot.py.
"""

import uuid

import pytest

from app.adapters.blob_local import LocalBlobStore
from tests.api_fakes import World, add_job, add_user, browser, make_app

PREFIXES = ("/api/jobs", "/jobs")  # canonical + D-004 aliases: both must be locked down
SUFFIXES = ("", "/stats", "/players/1", "/heatmap", "/heatmap?team=A", "/video")


@pytest.fixture
def two_users(tmp_path):
    w = World()
    blobs = LocalBlobStore(str(tmp_path / "blobs"))
    alice, alice_token = add_user(w, "alice")
    _, bob_token = add_user(w, "bob")
    done = add_job(w, blobs, alice, "succeeded", minute=1)
    queued = add_job(w, blobs, alice, "queued", minute=2)
    app = make_app(w, blobs)
    return browser(app, alice_token), browser(app, bob_token), done, queued


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("suffix", SUFFIXES)
def test_user_b_cannot_read_user_a_finished_job(two_users, prefix, suffix):
    alice, bob, done, _ = two_users
    path = f"{prefix}/{done.id}{suffix}"

    assert alice.get(path, follow_redirects=False).status_code == 200, path
    r = bob.get(path, follow_redirects=False)
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND", path


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("suffix", SUFFIXES)
def test_user_b_cannot_learn_user_a_unfinished_job_exists(two_users, prefix, suffix):
    alice, bob, _, queued = two_users
    path = f"{prefix}/{queued.id}{suffix}"
    missing = f"{prefix}/{uuid.uuid4()}{suffix}"

    assert alice.get(path).status_code == (200 if suffix == "" else 409), path
    # Not 409: Bob must not be able to tell "someone else's job" from "no such job".
    assert bob.get(path).json() == bob.get(missing).json()
    assert bob.get(path).status_code == 404, path


@pytest.mark.parametrize("prefix", PREFIXES)
def test_user_b_cannot_see_user_a_jobs_in_list(two_users, prefix):
    alice, bob, done, queued = two_users
    assert {j["id"] for j in alice.get(prefix).json()["jobs"]} == {str(done.id), str(queued.id)}
    assert bob.get(prefix).json()["jobs"] == []


def test_user_b_cannot_range_read_user_a_video(two_users):
    _, bob, done, _ = two_users
    r = bob.get(f"/api/jobs/{done.id}/video", headers={"Range": "bytes=0-99"})
    assert r.status_code == 404 and not r.content.startswith(b"\x00\x01")
