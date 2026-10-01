import asyncio
from uuid import UUID

import pytest

from app.adapters.blob_local import LocalBlobStore
from app.core.models import VideoProbe
from app.entrypoints.limits import MULTIPART_OVERHEAD, BodySizeLimitMiddleware
from app.services.submit import UploadLimits, submit_upload_job

LIMIT = 1000


class RecordingApp:
    """Inner ASGI app that drains the body like a form parser, then answers 200."""

    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        while True:
            message = await receive()
            if message["type"] == "http.disconnect" or not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


def run(middleware, headers, chunks):
    sent, pulled = [], []
    queue = [
        {"type": "http.request", "body": c, "more_body": i < len(chunks) - 1}
        for i, c in enumerate(chunks)
    ]

    async def receive():
        pulled.append(1)
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "path": "/api/jobs/upload", "headers": headers}
    asyncio.run(middleware(scope, receive, send))
    return sent[0]["status"], len(pulled)


def test_upload_middleware_rejects_big_content_length_without_calling_the_app():
    app = RecordingApp()
    mw = BodySizeLimitMiddleware(app, frozenset({"/api/jobs/upload"}), LIMIT)

    status, pulled = run(
        mw, [(b"content-length", str(LIMIT + MULTIPART_OVERHEAD + 1).encode())], []
    )

    assert status == 413 and not app.called and pulled == 0


def test_upload_middleware_cuts_off_streams_past_the_cap():
    app = RecordingApp()
    mw = BodySizeLimitMiddleware(app, frozenset({"/api/jobs/upload"}), LIMIT)
    chunks = [b"x" * 300_000] * 10  # 3 MB, no content-length

    status, pulled = run(mw, [], chunks)

    assert status == 413
    assert pulled < 10  # stopped reading once past LIMIT + overhead


def test_upload_middleware_passes_small_bodies_and_other_paths():
    app = RecordingApp()
    mw = BodySizeLimitMiddleware(app, frozenset({"/api/jobs/upload"}), LIMIT)
    assert run(mw, [(b"content-length", b"10")], [b"x" * 10])[0] == 200


class FixedProber:
    def probe(self, path):
        return VideoProbe("mov,mp4", 2.0, 160, 120, 5.0)


class BrokenJobs:
    def create_with_video(self, user_id, new_video, config):
        raise RuntimeError("database down")


def test_upload_blob_is_removed_when_the_db_insert_fails(tmp_path):
    blobs = LocalBlobStore(str(tmp_path / "blobs"))
    src = tmp_path / "clip"
    src.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100)

    with pytest.raises(RuntimeError):
        submit_upload_job(
            BrokenJobs(), blobs, FixedProber(), UUID(int=1), str(src), "c.mp4",
            UploadLimits(max_bytes=10_000, max_duration_s=60), {},
        )  # fmt: skip

    assert [p for p in blobs.root.rglob("*") if p.is_file()] == []
