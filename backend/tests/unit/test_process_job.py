"""process_job end to end with real ffmpeg + disk blobs, fake queue/repo/detector (no Postgres).

The same flow against real Postgres is tests/integration/test_process_job_pg.py (runs in CI).
"""

import shutil
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.adapters.blob_local import LocalBlobStore
from app.adapters.ffprobe import FfprobeVideoProber
from app.config import Settings
from app.core.models import Job, MediaInfo, Video
from app.errors import BlobNotFoundError, ExternalServiceError, ModelError
from app.services.process import process_job
from app.wiring import build_pipeline_ports, process_config
from tests.pipeline_helpers import make_clip, make_undecodable_clip, two_players

pytestmark = pytest.mark.ffmpeg

JOB_ID, USER_ID, VIDEO_ID = UUID(int=11), UUID(int=1), UUID(int=21)
SOURCE_KEY = f"uploads/{VIDEO_ID}/source.mp4"
NOW = datetime.now(UTC)


@pytest.fixture(scope="module")
def tiny_clip(tmp_path_factory) -> str:
    return make_clip(tmp_path_factory.mktemp("clip") / "tiny.mp4")


@pytest.fixture(scope="module")
def undecodable_clip(tmp_path_factory) -> str:
    return make_undecodable_clip(tmp_path_factory.mktemp("bad"))


# ---- fakes for the database side ----


class FakeQueue:
    def __init__(self, lose_lease_after_beats: int | None = None):
        self.beats: list[tuple[int, str]] = []
        self.finished = None
        self.failed = None
        self.lose_after = lose_lease_after_beats

    def heartbeat(self, job_id, worker_id, progress, stage, lease_s):
        self.beats.append((progress, stage))
        return self.lose_after is None or len(self.beats) <= self.lose_after

    def finish(self, job_id, worker_id, outcome):
        self.finished = outcome
        return True

    def fail(self, job_id, worker_id, code, message):
        self.failed = (code, message)
        return True


class FakeVideos:
    def __init__(self, video: Video):
        self.video = video

    def get_for_worker(self, video_id):
        return self.video

    def set_media_for_worker(self, video_id, key, size, duration_s, width, height, fps):
        self.video = Video(VIDEO_ID, USER_ID, "url", self.video.source_url, None, key, size,
                           duration_s, width, height, fps, NOW)  # fmt: skip

    def set_thumbnail_for_worker(self, video_id, key):
        self.video = replace(self.video, thumbnail_key=key)


class FailingBlobs(LocalBlobStore):
    """Disk store whose upload of the annotated video fails (storage outage)."""

    def put_file(self, key, src_path, content_type):
        if key.endswith("annotated.mp4"):
            raise ExternalServiceError("storage unavailable")
        super().put_file(key, src_path, content_type)


class BrokenDetector:
    def detect(self, frame):
        raise ModelError("The player detector failed. Please try again later.")


def upload_video(storage_key=SOURCE_KEY) -> Video:
    return Video(VIDEO_ID, USER_ID, "upload", None, "clip.mp4", storage_key, 1000, 2.0, 160, 120,
                 25.0, NOW)  # fmt: skip


def job() -> Job:
    return Job(JOB_ID, USER_ID, VIDEO_ID, "processing", 0, None, None, None, 1, 3, {}, NOW, NOW,
               None, NOW)  # fmt: skip


class Harness:
    def __init__(self, tmp_path, clip, detector=None, queue=None, blobs=None, video=None):
        self.work = tmp_path / "work"
        self.work.mkdir()
        self.blobs = blobs or LocalBlobStore(str(tmp_path / "blobs"))
        if clip:
            self.blobs.put_file(SOURCE_KEY, clip, "video/mp4")
        self.queue = queue or FakeQueue()
        self.videos = FakeVideos(video or upload_video())
        settings = Settings("test", "http://x", "unused", "t", heartbeat_every_frames=3,
                            upload_tmp_dir=str(self.work))  # fmt: skip
        self.cfg = process_config(settings)
        self.ports = build_pipeline_ports(_container(settings, self), detector or two_players())

    def run(self) -> str:
        return process_job(job(), self.ports, self.cfg, "worker-1")


def _container(settings, h):
    return SimpleNamespace(
        settings=settings, queue=h.queue, videos=h.videos, blobs=h.blobs,
        prober=FfprobeVideoProber(), media_info=None, downloader=None,
    )  # fmt: skip


# ---- tests ----


def test_job_succeeds_with_stats_tracks_and_playable_video(tmp_path, tiny_clip):
    h = Harness(tmp_path, tiny_clip)

    assert h.run() == "succeeded"

    outcome = h.queue.finished
    stats = outcome.stats
    assert stats["players_tracked"] == 2 == len(outcome.tracks)
    assert {"players", "possession", "heatmaps", "teams", "video", "config"} <= stats.keys()
    assert stats["video"] == {"duration_s": 2.0, "width": 160, "height": 120, "sample_fps": 5.0,
                              "frames_analysed": 10}  # fmt: skip
    assert stats["config"]["sample_fps"] == 5.0 and "tracker" in stats["config"]
    assert stats["ball_visible_pct"] == 100.0
    assert outcome.annotated_key == f"jobs/{JOB_ID}/annotated.mp4"

    played = tmp_path / "played.mp4"
    h.blobs.get_to_path(outcome.annotated_key, str(played))
    probe = FfprobeVideoProber().probe(str(played))
    assert (probe.width, probe.height) == (160, 120) and probe.duration_s == pytest.approx(
        2, abs=0.3
    )
    assert h.queue.failed is None


def test_stages_follow_the_stepper_order_with_two_passes(tmp_path, tiny_clip):
    h = Harness(tmp_path, tiny_clip)
    assert h.run() == "succeeded"

    stages = [s for _, s in h.queue.beats]
    order = [s for i, s in enumerate(stages) if i == 0 or s != stages[i - 1]]  # de-duplicate runs
    assert order == ["fetching", "analysing", "computing", "rendering", "saving"]
    progress = [p for p, _ in h.queue.beats]
    assert progress == sorted(progress) and max(progress) < 100


class SpyAnnotator:
    """Wraps the real annotator and records the team map pass 2 hands it."""

    def __init__(self, real):
        self.real, self.teams_seen = real, []

    def thumbnail_jpeg(self, frame, max_width):
        return self.real.thumbnail_jpeg(frame, max_width)

    def draw(self, frame, tracks, ball, t_s, teams):
        self.teams_seen.append(dict(teams))
        return self.real.draw(frame, tracks, ball, t_s, teams)


def test_rendering_pass_draws_every_frame_with_the_final_team_split(tmp_path, tiny_clip):
    h = Harness(tmp_path, tiny_clip)
    spy = SpyAnnotator(h.ports.annotator)
    h.ports = replace(h.ports, annotator=spy)

    assert h.run() == "succeeded"

    stats_teams = {p["player_id"]: p["team"] for p in h.queue.finished.stats["players"]}
    assert len(spy.teams_seen) == 10  # one draw per sampled frame, all in pass 2
    assert all(seen == stats_teams for seen in spy.teams_seen)  # same split as the stats


def test_lost_lease_during_rendering_writes_nothing(tmp_path, tiny_clip):
    # beats: fetching 1 + analysing 4 (frames 0,3,6,9) + computing 1 = 6; the 7th is rendering
    h = Harness(tmp_path, tiny_clip, queue=FakeQueue(lose_lease_after_beats=6))

    assert h.run() == "lease_lost"

    assert h.queue.beats[-1][1] == "rendering"
    assert h.queue.finished is None and h.queue.failed is None
    with pytest.raises(BlobNotFoundError):
        h.blobs.size(f"jobs/{JOB_ID}/annotated.mp4")


def test_first_frame_thumbnail_is_saved_as_a_small_jpeg(tmp_path, tiny_clip):
    h = Harness(tmp_path, tiny_clip)
    h.run()

    key = h.videos.video.thumbnail_key
    assert key == f"videos/{VIDEO_ID}/thumbnail.jpg"
    out = tmp_path / "thumb.jpg"
    h.blobs.get_to_path(key, str(out))
    data = out.read_bytes()
    assert data[:3] == b"\xff\xd8\xff"  # JPEG magic
    probe = FfprobeVideoProber().probe(str(out))  # ffprobe reads JPEGs as a 1-frame image
    assert probe.width == 160  # the clip is 160 px wide, under the 320 px cap


def test_progress_goes_fetching_analysing_saving_and_only_rises(tmp_path, tiny_clip):
    h = Harness(tmp_path, tiny_clip)
    h.run()

    stages = [s for _, s in h.queue.beats]
    progress = [p for p, _ in h.queue.beats]
    assert stages[0] == "fetching" and stages[-1] == "saving" and "analysing" in stages
    assert progress == sorted(progress) and max(progress) < 100


@pytest.mark.parametrize("clip_name", ["tiny_clip", "undecodable_clip"])
def test_temp_files_are_removed_after_success_and_failure(tmp_path, clip_name, request):
    h = Harness(tmp_path, request.getfixturevalue(clip_name))
    h.run()
    assert list(h.work.iterdir()) == []


def test_corrupt_but_sniffable_file_fails_with_decode_error(tmp_path, undecodable_clip):
    h = Harness(tmp_path, undecodable_clip)

    assert h.run() == "failed"

    code, message = h.queue.failed
    assert code == "DECODE_ERROR" and "re-exporting" in message
    assert h.queue.finished is None


def test_model_error_is_final(tmp_path, tiny_clip):
    h = Harness(tmp_path, tiny_clip, detector=BrokenDetector())
    assert h.run() == "failed"
    assert h.queue.failed[0] == "MODEL_ERROR"


def test_lost_lease_stops_without_writing_results(tmp_path, tiny_clip):
    h = Harness(tmp_path, tiny_clip, queue=FakeQueue(lose_lease_after_beats=2))

    assert h.run() == "lease_lost"

    assert h.queue.finished is None and h.queue.failed is None
    with pytest.raises(BlobNotFoundError):
        h.blobs.size(f"jobs/{JOB_ID}/annotated.mp4")


def test_storage_outage_is_retried_not_failed(tmp_path, tiny_clip):
    h = Harness(tmp_path, tiny_clip, blobs=FailingBlobs(str(tmp_path / "blobs")))

    with pytest.raises(ExternalServiceError):
        h.run()

    assert h.queue.failed is None and h.queue.finished is None  # lease lapses â†’ next attempt


def test_url_source_is_fetched_first(tmp_path, tiny_clip):
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video = Video(VIDEO_ID, USER_ID, "url", url, None, None, None, None, None, None, None, NOW)
    h = Harness(tmp_path, None, video=video)

    class Meta:
        def fetch_info(self, u):
            return MediaInfo(2.0, False, "https://rr1---sn-x.googlevideo.com/videoplayback", {})

    class Downloader:
        def download(self, u, headers, dest, max_bytes):
            shutil.copyfile(tiny_clip, dest)
            return 1000

    h.ports = replace(h.ports, media_info=Meta(), downloader=Downloader())

    assert h.run() == "succeeded"
    assert h.videos.video.storage_key == f"uploads/{VIDEO_ID}/source.mp4"
