"""T-090 at the API: 11th submit in a minute → 429, per-user, and the active-job cap."""

import pytest

from app.adapters.blob_local import LocalBlobStore
from app.adapters.memory_rate_limiter import InMemoryRateLimiter
from app.core.models import RateLimits
from tests.api_fakes import World, add_user, browser, make_app

CSRF = {"Origin": "http://localhost:8000", "X-Requested-With": "fetch"}
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


class FrozenClock:
    t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def setup(tmp_path):
    w = World()
    _, alice = add_user(w, "alice")
    _, bob = add_user(w, "bob")
    limiter = InMemoryRateLimiter(RateLimits(per_minute=10, per_hour=30), clock=FrozenClock())
    app = make_app(w, LocalBlobStore(str(tmp_path / "b")), limiter)
    return w, browser(app, alice), browser(app, bob)


def finish_all(w):
    """Mark every job done so the active-job cap doesn't interfere with rate tests."""
    from dataclasses import replace

    for jid, job in list(w.jobs.items()):
        w.jobs[jid] = replace(job, status="succeeded")


def submit(client, prefix="/api"):
    return client.post(f"{prefix}/jobs/url", headers=CSRF, json={"url": URL})


def test_rate_limit_eleventh_submit_in_a_minute_is_429_with_retry_after(setup):
    w, alice, _ = setup
    for _ in range(10):
        assert submit(alice).status_code == 202
        finish_all(w)

    r = submit(alice)

    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    assert "try again" in r.json()["error"]["message"]
    assert int(r.headers["retry-after"]) > 0


def test_rate_limit_counts_both_prefixes_together(setup):
    w, alice, _ = setup
    for i in range(10):
        assert submit(alice, "/api" if i % 2 else "").status_code == 202
        finish_all(w)
    assert submit(alice, "").status_code == 429  # the /jobs alias is not a way around it


def test_rate_limit_is_per_user(setup):
    w, alice, bob = setup
    for _ in range(10):
        submit(alice)
        finish_all(w)
    assert submit(alice).status_code == 429
    assert submit(bob).status_code == 202


def test_rate_limit_counts_rejected_submissions_too(setup):
    _, alice, _ = setup
    for _ in range(10):
        r = alice.post("/api/jobs/url", headers=CSRF, json={"url": "https://example.com/x"})
        assert r.status_code == 422  # not a YouTube link
    assert submit(alice).status_code == 429


def test_rate_limit_active_job_cap_refuses_a_fourth_running_job(setup):
    w, alice, bob = setup
    for _ in range(3):
        assert submit(alice).status_code == 202  # queued, never finished
    r = submit(alice)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "TOO_MANY_ACTIVE_JOBS"
    assert "3 videos processing" in r.json()["error"]["message"]
    assert submit(bob).status_code == 202  # other users unaffected
    finish_all(w)
    assert submit(alice).status_code == 202  # cap frees up when jobs finish
