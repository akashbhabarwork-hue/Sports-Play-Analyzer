import statistics
import time
from dataclasses import replace

import pytest
from sqlalchemy import text

from tests.integration.conftest import make_settings

pytestmark = pytest.mark.integration

URL = "/api/jobs/url"
ID = "dQw4w9WgXcQ"


def count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_url_submit_queues_job_with_canonical_url(client, login_as, csrf_headers, container):
    user = login_as(client, "ann")

    response = client.post(
        URL, json={"url": f"https://youtu.be/{ID}?si=tracking"}, headers=csrf_headers
    )

    assert response.status_code == 202, response.text
    job = container.jobs.get(user.id, response.json()["job_id"])
    video = container.videos.get(user.id, job.video_id)
    assert (job.status, video.source_type) == ("queued", "url")
    assert video.source_url == f"https://www.youtube.com/watch?v={ID}"  # raw input not kept
    assert video.storage_key is None  # the worker fetches it later
    assert job.config == {"max_video_seconds": 60}


@pytest.mark.parametrize(
    "url",
    [
        "https://youtube.com.evil.io/watch?v=dQw4w9WgXcQ",
        "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://169.254.169.254/latest/meta-data/",
    ],
)
def test_url_submit_rejects_without_inserting(engine, client, login_as, csrf_headers, url):
    login_as(client, "ann")

    response = client.post(URL, json={"url": url}, headers=csrf_headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "URL_NOT_ALLOWED"
    assert (count(engine, "videos"), count(engine, "jobs")) == (0, 0)


@pytest.mark.parametrize("body", [{}, {"url": 123}, {"url": ""}, {"url": "x" * 2049}])
def test_url_submit_validates_body_shape(client, login_as, csrf_headers, body):
    login_as(client, "ann")
    assert client.post(URL, json=body, headers=csrf_headers).status_code == 422


def test_url_submit_requires_login_and_csrf(client, login_as, csrf_headers):
    body = {"url": f"https://youtu.be/{ID}"}
    assert client.post(URL, json=body, headers=csrf_headers).status_code == 401
    login_as(client, "ann")
    assert client.post(URL, json=body).status_code == 403


# Six submits by one user with no worker running: lift the active-job cap (T-090, default 3)
# so this test measures latency only. The cap itself is covered by test_rate_limit_api.py.
@pytest.mark.parametrize("settings", [replace(make_settings(), max_active_jobs_per_user=10)])
def test_url_submit_answers_within_100ms(client, login_as, csrf_headers):
    login_as(client, "ann")
    body = {"url": f"https://www.youtube.com/watch?v={ID}"}
    client.post(URL, json=body, headers=csrf_headers)  # warm-up (imports, pool)

    timings = []
    for _ in range(5):
        start = time.perf_counter()
        response = client.post(URL, json=body, headers=csrf_headers)
        timings.append(time.perf_counter() - start)
        assert response.status_code == 202

    assert statistics.median(timings) < 0.100, f"median {statistics.median(timings):.3f}s"
