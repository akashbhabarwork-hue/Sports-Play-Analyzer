import dataclasses
import os
import subprocess

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.entrypoints.api import create_app

pytestmark = pytest.mark.integration

URL = "/api/jobs/upload"


def ffmpeg_clip(path, seconds: int) -> str:
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=160x120:rate=5:duration={seconds}",
            "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast",
            str(path),
        ],
        check=True,
        timeout=60,
    )  # fmt: skip
    return str(path)


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    tiny = ffmpeg_clip(d / "tiny.mp4", 2)
    data = open(tiny, "rb").read()
    corrupt = d / "corrupt.mp4"  # valid MP4 magic, garbage after
    corrupt.write_bytes(b"\x00\x00\x00\x18ftypmp42" + os.urandom(4096))
    truncated = d / "truncated.mp4"
    truncated.write_bytes(data[: len(data) * 3 // 10])
    fake = d / "fake.mp4"
    fake.write_text("this is a text file pretending to be a video\n" * 10)
    return {
        "tiny": tiny,
        "long": ffmpeg_clip(d / "long.mp4", 61),
        "corrupt": str(corrupt),
        "truncated": str(truncated),
        "fake": str(fake),
    }


@pytest.fixture
def upload_tmp(tmp_path):
    path = tmp_path / "upload-tmp"
    path.mkdir()
    return path


@pytest.fixture
def settings(settings_factory, upload_tmp):
    return dataclasses.replace(settings_factory(), upload_tmp_dir=str(upload_tmp))


def post_file(client, path, headers, name="clip.mp4"):
    with open(path, "rb") as f:
        return client.post(URL, files={"file": (name, f, "video/mp4")}, headers=headers)


def count(engine, table):
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def blob_files(blobs):
    return [p for p in blobs.root.rglob("*") if p.is_file()]


def test_upload_valid_clip_is_queued(
    engine, client, login_as, csrf_headers, clips, container, upload_tmp
):
    user = login_as(client, "ann")

    response = post_file(client, clips["tiny"], csrf_headers)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    job = container.jobs.get(user.id, body["job_id"])
    video = container.videos.get(user.id, job.video_id)
    assert video.source_type == "upload" and video.original_filename == "clip.mp4"
    assert video.storage_key == f"uploads/{video.id}/source.mp4"
    assert 1.5 < video.duration_s < 2.5 and (video.width, video.height) == (160, 120)
    assert container.blobs.size(video.storage_key) == os.path.getsize(clips["tiny"])
    assert job.config == {"max_video_seconds": 60}
    assert list(upload_tmp.iterdir()) == []


@pytest.mark.parametrize(
    ("clip", "status", "code"),
    [
        ("fake", 415, "UNSUPPORTED_FORMAT"),
        ("corrupt", 422, "CORRUPT_FILE"),
        ("truncated", 422, "CORRUPT_FILE"),
        ("long", 422, "DURATION_EXCEEDED"),
    ],
)
def test_upload_rejections_leave_nothing_behind(
    engine, client, login_as, csrf_headers, clips, container, upload_tmp, clip, status, code
):
    login_as(client, "ann")

    response = post_file(client, clips[clip], csrf_headers)

    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["message"]
    assert (count(engine, "videos"), count(engine, "jobs")) == (0, 0)
    assert blob_files(container.blobs) == []
    assert list(upload_tmp.iterdir()) == []


@pytest.fixture
def small_limit_client(container, upload_tmp):
    small = dataclasses.replace(container.settings, max_upload_bytes=20_000)
    return TestClient(create_app(dataclasses.replace(container, settings=small)))


def test_upload_oversize_by_content_length_is_413(
    small_limit_client, login_as, csrf_headers, upload_tmp
):
    login_as(small_limit_client, "ann")
    big = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2_000_000

    response = small_limit_client.post(
        URL, files={"file": ("big.mp4", big, "video/mp4")}, headers=csrf_headers
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert list(upload_tmp.iterdir()) == []


def test_upload_oversize_without_content_length_is_cut_off(
    small_limit_client, login_as, csrf_headers, engine
):
    login_as(small_limit_client, "ann")
    boundary = "xyzboundary"

    def body():  # a generator → chunked transfer, no Content-Length to trust
        yield (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="big.mp4"\r\nContent-Type: video/mp4\r\n\r\n'
        ).encode()
        for _ in range(40):
            yield b"\x00" * 65_536  # 2.6 MB total, far past the 20 KB + 1 MB cap
        yield f"\r\n--{boundary}--\r\n".encode()

    response = small_limit_client.post(
        URL,
        content=body(),
        headers={**csrf_headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert count(engine, "jobs") == 0
    # TestClient buffers the request body before calling the app, so how early reading
    # stops is asserted at the ASGI level in tests/unit/test_upload_limits.py.


def test_upload_just_over_file_limit_is_rejected_in_route(
    small_limit_client, login_as, csrf_headers
):
    # Under the body cap (limit + multipart overhead) but over the file limit itself.
    login_as(small_limit_client, "ann")
    data = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 30_000

    response = small_limit_client.post(
        URL, files={"file": ("big.mp4", data, "video/mp4")}, headers=csrf_headers
    )

    assert response.status_code == 413


def test_upload_requires_login_and_csrf_headers(client, login_as, csrf_headers, clips):
    assert post_file(client, clips["tiny"], csrf_headers).status_code == 401
    login_as(client, "ann")
    assert post_file(client, clips["tiny"], {}).status_code == 403
