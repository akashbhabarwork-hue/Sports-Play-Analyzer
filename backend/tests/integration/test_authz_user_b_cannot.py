"""Required authorization test (T-071, scenario A3) against real Postgres: user B gets 404 on
every one of user A's job endpoints — canonical /api/jobs… and the /jobs… aliases — and A's
jobs never appear in B's list. Ownership is enforced in SQL (`WHERE user_id = :uid`).
"""

import uuid

import pytest

from app.core.models import NewVideo
from tests.integration.test_api_read import seed_succeeded_job

pytestmark = pytest.mark.integration

PREFIXES = ("/api/jobs", "/jobs")
SUFFIXES = ("", "/stats", "/players/1", "/heatmap", "/heatmap?team=A", "/video")


@pytest.fixture
def alice_and_bob(make_client, login_as, container):
    alice_browser, bob_browser = make_client(), make_client()
    alice = login_as(alice_browser, "alice")
    login_as(bob_browser, "bob")
    done = seed_succeeded_job(container, alice.id)
    queued = container.jobs.create_with_video(
        alice.id, NewVideo(source_type="url", source_url="https://youtu.be/x"), {}
    )
    return alice_browser, bob_browser, done, queued


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("suffix", SUFFIXES)
def test_user_b_cannot_read_user_a_job(alice_and_bob, prefix, suffix):
    alice, bob, done, _ = alice_and_bob
    path = f"{prefix}/{done.id}{suffix}"

    assert alice.get(path, follow_redirects=False).status_code == 200, path
    r = bob.get(path, follow_redirects=False)
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND", path


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("suffix", SUFFIXES)
def test_user_b_cannot_tell_user_a_queued_job_from_a_missing_one(alice_and_bob, prefix, suffix):
    _, bob, _, queued = alice_and_bob
    mine = bob.get(f"{prefix}/{queued.id}{suffix}")
    missing = bob.get(f"{prefix}/{uuid.uuid4()}{suffix}")
    assert mine.status_code == missing.status_code == 404
    assert mine.json() == missing.json()


@pytest.mark.parametrize("prefix", PREFIXES)
def test_user_b_cannot_see_user_a_jobs_in_list(alice_and_bob, prefix):
    alice, bob, done, queued = alice_and_bob
    assert {j["id"] for j in alice.get(prefix).json()["jobs"]} == {str(done.id), str(queued.id)}
    assert bob.get(prefix).json()["jobs"] == []
