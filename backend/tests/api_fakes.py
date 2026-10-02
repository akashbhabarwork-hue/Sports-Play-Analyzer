"""In-memory repositories for API tests without Postgres.

They honour the same contract as the SQL repos: every user-data read filters on `user_id`,
so "missing" and "someone else's" both come back as None. The Postgres versions of these
tests live in tests/integration/ (CI).
"""

import os
import tempfile
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.adapters.blob_local import LocalBlobStore
from app.adapters.ffprobe import FfprobeVideoProber
from app.config import Settings
from app.core.models import Job, JobResult, JobWithVideo, PlayerTrack, User, Video
from app.core.sessions import hash_token
from app.entrypoints.api import create_app
from app.wiring import Container

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
GRID = {"w": 2, "h": 1, "counts": [3, 1], "max": 3}
VIDEO_BYTES = bytes(range(256)) * 40  # 10,240 bytes: big enough to range over
THUMB_BYTES = b"\xff\xd8\xff\xe0fake-jpeg\xff\xd9"


class OkHealth:
    def check_db(self) -> bool:
        return True


@dataclass
class World:
    users: dict[UUID, User] = field(default_factory=dict)
    sessions: dict[bytes, UUID] = field(default_factory=dict)
    jobs: dict[UUID, Job] = field(default_factory=dict)
    videos: dict[UUID, Video] = field(default_factory=dict)
    results: dict[UUID, JobResult] = field(default_factory=dict)
    tracks: dict[tuple[UUID, int], PlayerTrack] = field(default_factory=dict)


class FakeSessions:
    def __init__(self, w: World):
        self.w = w

    def get_user_by_token(self, token_hash: bytes) -> User | None:
        uid = self.w.sessions.get(token_hash)
        return self.w.users.get(uid) if uid else None


class FakeJobs:
    def __init__(self, w: World):
        self.w = w

    def get(self, user_id, job_id):
        job = self.w.jobs.get(job_id)
        return job if job and job.user_id == user_id else None

    def create_with_video(self, user_id, new_video, config):
        video = Video(new_video.id or uuid4(), user_id, new_video.source_type,
                      new_video.source_url, new_video.original_filename, new_video.storage_key,
                      new_video.size_bytes, new_video.duration_s, new_video.width,
                      new_video.height, new_video.fps, NOW, sport=new_video.sport,
                      title=new_video.title)  # fmt: skip
        job = Job(uuid4(), user_id, video.id, "queued", 0, None, None, None, 0, 3, config, NOW,
                  None, None, NOW)  # fmt: skip
        self.w.videos[video.id] = video
        self.w.jobs[job.id] = job
        return job

    def list_for_user(self, user_id, limit=50):
        mine = [j for j in self.w.jobs.values() if j.user_id == user_id]
        return sorted(mine, key=lambda j: j.created_at, reverse=True)[:limit]

    def _pair(self, job):
        video = self.w.videos.get(job.video_id)
        return JobWithVideo(job, video) if video and video.user_id == job.user_id else None

    def get_with_video(self, user_id, job_id):
        job = self.get(user_id, job_id)
        return self._pair(job) if job else None

    def list_with_videos(self, user_id, limit=50):
        return [p for j in self.list_for_user(user_id, limit) if (p := self._pair(j))]

    def count_active(self, user_id):
        return sum(
            1 for j in self.w.jobs.values()
            if j.user_id == user_id and j.status in ("queued", "processing")
        )  # fmt: skip


class FakeVideos:
    def __init__(self, w: World):
        self.w = w

    def get(self, user_id, video_id):
        v = self.w.videos.get(video_id)
        return v if v and v.user_id == user_id else None


class FakeResults:
    def __init__(self, w: World):
        self.w = w

    def _owner_ok(self, user_id, job_id) -> bool:
        job = self.w.jobs.get(job_id)
        return bool(job and job.user_id == user_id)

    def get(self, user_id, job_id):
        return self.w.results.get(job_id) if self._owner_ok(user_id, job_id) else None

    def list_tracks(self, user_id, job_id):
        if not self._owner_ok(user_id, job_id):
            return []
        return [t for (jid, _), t in self.w.tracks.items() if jid == job_id]

    def get_track(self, user_id, job_id, track_id):
        return self.w.tracks.get((job_id, track_id)) if self._owner_ok(user_id, job_id) else None


class PresigningBlobs(LocalBlobStore):
    """Disk store that behaves like S3: hands out a short-lived URL instead of streaming."""

    def presigned_get_url(self, key, ttl_s):
        return f"https://bucket.example/{key}?X-Amz-Expires={ttl_s}"


def add_user(w: World, name: str) -> tuple[User, str]:
    user = User(uuid4(), "google", f"sub-{name}", f"{name}@example.com", name, None, NOW)
    token = f"token-{name}"
    w.users[user.id] = user
    w.sessions[hash_token(token)] = user.id
    return user, token


def add_job(w: World, blobs, owner: User, status: str = "succeeded", minute: int = 0) -> Job:
    video = Video(uuid4(), owner.id, "upload", None, "match.mp4", "uploads/x/source.mp4", 100,
                  12.5, 160, 120, 25.0, NOW)  # fmt: skip
    job = Job(uuid4(), owner.id, video.id, status, 100 if status == "succeeded" else 40,
              None if status == "succeeded" else "analysing", None, None, 1, 3, {},
              NOW.replace(minute=minute), NOW, NOW if status == "succeeded" else None,
              NOW)  # fmt: skip
    if status == "failed":
        job = replace(job, error_code="DECODE_ERROR", error_message="We couldn't decode frames.")
    if blobs is not None:  # every seeded job has a first-frame thumbnail (T-086)
        thumb = f"videos/{video.id}/thumbnail.jpg"
        _put_blob(blobs, thumb, THUMB_BYTES, "image/jpeg")
        video = replace(video, thumbnail_key=thumb, title=f"Clip {minute}")
    w.videos[video.id] = video
    w.jobs[job.id] = job
    if status == "succeeded":
        key = f"jobs/{job.id}/annotated.mp4"
        stats = {
            "job_id": str(job.id),
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
            ],  # fmt: skip
            "heatmaps": {"all": GRID, "A": GRID, "B": {**GRID, "counts": [0, 0], "max": 0}},
        }
        w.results[job.id] = JobResult(job.id, stats, key, NOW)
        w.tracks[(job.id, 1)] = PlayerTrack(job.id, 1, "A", 10, 50.0, 0.25, 4, GRID,
                                            [[0.0, 0.1, 0.9], [0.2, 0.2, 0.9]])  # fmt: skip
        if blobs is not None:
            _put_blob(blobs, key, VIDEO_BYTES, "video/mp4")
    return job


def _put_blob(blobs, key: str, data: bytes, content_type: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "blob")
        with open(src, "wb") as f:
            f.write(data)
        blobs.put_file(key, src, content_type)


def make_container(w: World, blobs, limiter=None) -> Container:
    settings = Settings(app_env="test", app_origin="http://localhost:8000", database_url="x",
                        git_sha="t", cookie_secure=False)  # fmt: skip
    none = dict.fromkeys(("users", "queue", "media_info", "downloader"))
    return Container(**none, settings=settings, health_check=OkHealth(),
                     prober=FfprobeVideoProber(),
                     sessions=FakeSessions(w), videos=FakeVideos(w), jobs=FakeJobs(w),
                     results=FakeResults(w), blobs=blobs, rate_limiter=limiter)  # fmt: skip


def browser(app, token: str | None) -> TestClient:
    client = TestClient(app, base_url="http://testserver")
    if token:
        client.cookies.set("sid", token)
    return client


def make_app(w: World, blobs, limiter=None):
    return create_app(make_container(w, blobs, limiter))
