import shutil
import subprocess
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.adapters.blob_local import LocalBlobStore
from app.adapters.ffprobe import FfprobeVideoProber
from app.core.models import MediaInfo, Video
from app.errors import CorruptFileError, DownloadFailedError, DurationExceededError
from app.services.fetch import fetch_url_video
from app.services.submit import UploadLimits

VIDEO_ID = UUID(int=7)
LIMITS = UploadLimits(max_bytes=10_000_000, max_duration_s=60)
MEDIA_URL = "https://rr1---sn-abc.googlevideo.com/videoplayback"


@pytest.fixture(scope="module")
def tiny_clip(tmp_path_factory):
    path = tmp_path_factory.mktemp("clip") / "tiny.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=160x120:rate=5:duration=2", "-pix_fmt", "yuv420p", str(path)],
        check=True, timeout=60,
    )  # fmt: skip
    return str(path)


def video(source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ") -> Video:
    return Video(VIDEO_ID, UUID(int=1), "url", source_url, None, None, None, None, None,
                 None, None, datetime.now(UTC))  # fmt: skip


class FakeMeta:
    def __init__(self, info):
        self.info = info

    def fetch_info(self, url):
        return self.info


class FakeDownloader:
    def __init__(self, src):
        self.src, self.calls = src, []

    def download(self, url, headers, dest, max_bytes):
        self.calls.append(url)
        shutil.copyfile(self.src, dest)
        return len(open(dest, "rb").read())


class FakeVideos:
    def __init__(self, fail=False):
        self.fail, self.media = fail, None

    def set_media_for_worker(self, *args):
        if self.fail:
            raise RuntimeError("db down")
        self.media = args


def ok_info(duration=2.0, live=False, url=MEDIA_URL):
    return MediaInfo(duration, live, url, {"User-Agent": "UA"})


def blob_files(blobs):
    return [p for p in blobs.root.rglob("*") if p.is_file()]


def run(tmp_path, info, src, videos=None):
    blobs = LocalBlobStore(str(tmp_path / "blobs"))
    downloader = FakeDownloader(src)
    videos = videos or FakeVideos()
    tmp_root = tmp_path / "tmp"
    tmp_root.mkdir(exist_ok=True)
    key = None
    try:
        key = fetch_url_video(videos, blobs, FakeMeta(info), downloader, FfprobeVideoProber(),
                              video(), LIMITS, str(tmp_root))  # fmt: skip
    finally:
        assert list(tmp_root.iterdir()) == []  # temp dir removed in every outcome
    return key, blobs, downloader, videos


def test_fetch_service_stores_blob_and_records_media(tmp_path, tiny_clip):
    key, blobs, downloader, videos = run(tmp_path, ok_info(), tiny_clip)

    assert key == f"uploads/{VIDEO_ID}/source.mp4"
    assert blobs.size(key) > 0
    vid, stored_key, size, duration, width, height, fps = videos.media
    assert (vid, stored_key, width, height) == (VIDEO_ID, key, 160, 120)
    assert 1.5 < duration < 2.5 and size == blobs.size(key)
    assert downloader.calls == [MEDIA_URL]


@pytest.mark.parametrize(
    ("info", "error"),
    [
        (ok_info(duration=61), DurationExceededError),
        (ok_info(live=True), DownloadFailedError),
        (ok_info(duration=None), DownloadFailedError),
        (ok_info(url=None), DownloadFailedError),
    ],
)
def test_fetch_service_rejects_before_downloading(tmp_path, tiny_clip, info, error):
    blobs = LocalBlobStore(str(tmp_path / "b"))
    downloader = FakeDownloader(tiny_clip)
    with pytest.raises(error):
        fetch_url_video(FakeVideos(), blobs, FakeMeta(info), downloader, FfprobeVideoProber(),
                        video(), LIMITS)  # fmt: skip
    assert downloader.calls == [] and blob_files(blobs) == []


def test_fetch_service_rechecks_downloaded_bytes(tmp_path):
    garbage = tmp_path / "garbage"
    garbage.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x01" * 4096)  # claims MP4, isn't
    with pytest.raises(CorruptFileError):
        run(tmp_path, ok_info(), str(garbage))
    assert blob_files(LocalBlobStore(str(tmp_path / "blobs"))) == []


def test_fetch_service_removes_blob_if_recording_fails(tmp_path, tiny_clip):
    with pytest.raises(RuntimeError):
        run(tmp_path, ok_info(), tiny_clip, videos=FakeVideos(fail=True))
    assert blob_files(LocalBlobStore(str(tmp_path / "blobs"))) == []
