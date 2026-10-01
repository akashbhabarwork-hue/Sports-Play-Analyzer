from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.adapters.pg_repos import (
    PostgresJobRepo,
    PostgresResultRepo,
    PostgresSessionRepo,
    PostgresUserRepo,
    PostgresVideoRepo,
)
from app.core.models import NewVideo
from app.errors import ExternalServiceError

pytestmark = pytest.mark.integration

UPLOAD = NewVideo(source_type="upload", original_filename="clip.mp4", storage_key="u/clip.mp4")


@pytest.fixture
def repos(engine):
    # Tables are wiped after each test by the autouse `clean_db` fixture (conftest).
    return {
        "users": PostgresUserRepo(engine),
        "sessions": PostgresSessionRepo(engine),
        "videos": PostgresVideoRepo(engine),
        "jobs": PostgresJobRepo(engine),
        "results": PostgresResultRepo(engine),
    }


@pytest.fixture
def two_users(repos):
    a = repos["users"].upsert_from_oauth("google", "sub-a", "a@example.com", "A", None)
    b = repos["users"].upsert_from_oauth("google", "sub-b", "b@example.com", "B", None)
    return a, b


def add_result(engine, job_id, track_ids=(1, 2)):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO job_results (job_id, stats, annotated_key) VALUES (:j, '{}', 'k')"),
            {"j": job_id},
        )
        for t in track_ids:
            conn.execute(
                text(
                    "INSERT INTO player_tracks (job_id, track_id, team, frames_visible, "
                    "distance_px, distance_rel, heatmap, track) "
                    "VALUES (:j, :t, 'A', 10, 5, 0.1, '{\"w\": 1}', '[[0, 0.5, 0.5]]')"
                ),
                {"j": job_id, "t": t},
            )


def test_upsert_user_is_idempotent_and_updates_profile(repos):
    first = repos["users"].upsert_from_oauth("google", "sub-1", "old@example.com", "Old", None)
    second = repos["users"].upsert_from_oauth("google", "sub-1", "new@example.com", "New", "pic")

    assert second.id == first.id
    assert (second.email, second.name, second.avatar_url) == ("new@example.com", "New", "pic")
    assert repos["users"].get(first.id) == second


def test_create_and_list_jobs_newest_first_and_only_own(repos, two_users):
    a, b = two_users
    j1 = repos["jobs"].create_with_video(a.id, UPLOAD, {"sample_fps": 5})
    j2 = repos["jobs"].create_with_video(
        a.id, NewVideo(source_type="url", source_url="https://youtu.be/x"), {}
    )
    repos["jobs"].create_with_video(b.id, UPLOAD, {})

    assert (j1.status, j1.progress, j1.attempts, j1.config) == ("queued", 0, 0, {"sample_fps": 5})
    assert [j.id for j in repos["jobs"].list_for_user(a.id)] == [j2.id, j1.id]
    assert [j.id for j in repos["jobs"].list_for_user(a.id, limit=1)] == [j2.id]
    assert repos["jobs"].get(a.id, j1.id) == j1
    video = repos["videos"].get(a.id, j1.video_id)
    assert (video.source_type, video.storage_key) == ("upload", "u/clip.mp4")


def test_other_user_cannot_read_job_video_or_results(repos, engine, two_users):
    a, b = two_users
    job = repos["jobs"].create_with_video(a.id, UPLOAD, {})
    add_result(engine, job.id)

    assert repos["jobs"].get(b.id, job.id) is None
    assert repos["videos"].get(b.id, job.video_id) is None
    assert repos["results"].get(b.id, job.id) is None
    assert repos["results"].list_tracks(b.id, job.id) == []
    assert repos["results"].get_track(b.id, job.id, 1) is None
    assert repos["jobs"].list_for_user(b.id) == []

    # ...while the owner can.
    assert repos["results"].get(a.id, job.id).annotated_key == "k"
    assert [t.track_id for t in repos["results"].list_tracks(a.id, job.id)] == [1, 2]
    assert repos["results"].get_track(a.id, job.id, 2).track == [[0, 0.5, 0.5]]


def test_unknown_ids_return_none(repos, two_users):
    a, _ = two_users
    assert repos["jobs"].get(a.id, uuid4()) is None
    assert repos["jobs"].get_for_worker(uuid4()) is None
    assert repos["users"].get(uuid4()) is None


def test_worker_methods_are_not_user_scoped(repos, two_users):
    a, _ = two_users
    job = repos["jobs"].create_with_video(
        a.id, NewVideo("url", source_url="https://youtu.be/x"), {}
    )

    assert repos["jobs"].get_for_worker(job.id) == job
    repos["videos"].set_media_for_worker(job.video_id, "v/x.mp4", 1000, 12.5, 640, 360, 25.0)
    video = repos["videos"].get_for_worker(job.video_id)
    assert (video.storage_key, video.duration_s, video.width, video.fps) == (
        "v/x.mp4",
        12.5,
        640,
        25.0,
    )


def test_create_with_video_is_atomic(repos, engine, two_users):
    a, _ = two_users
    # The video insert succeeds, then Postgres rejects the job row (jsonb cannot hold NUL);
    # the video row must be rolled back with it.
    with pytest.raises(ExternalServiceError):
        repos["jobs"].create_with_video(a.id, UPLOAD, {"bad": "\x00"})
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM videos")).scalar_one() == 0


def test_sessions_lookup_expiry_and_logout_all(repos, two_users):
    a, b = two_users
    now = datetime.now(UTC)
    repos["sessions"].create(b"live-1", a.id, now + timedelta(days=7))
    repos["sessions"].create(b"live-2", a.id, now + timedelta(days=7))
    repos["sessions"].create(b"expired", a.id, now - timedelta(seconds=1))
    repos["sessions"].create(b"other", b.id, now + timedelta(days=7))

    assert repos["sessions"].get_user_by_token(b"live-1") == a
    assert repos["sessions"].get_user_by_token(b"expired") is None
    assert repos["sessions"].get_user_by_token(b"missing") is None

    assert repos["sessions"].delete_expired() == 1
    repos["sessions"].delete(b"live-1")
    assert repos["sessions"].get_user_by_token(b"live-1") is None
    assert repos["sessions"].delete_all_for_user(a.id) == 1
    assert repos["sessions"].get_user_by_token(b"live-2") is None
    assert repos["sessions"].get_user_by_token(b"other") == b
