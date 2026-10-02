"""Request-size enforcement for upload routes (ASGI middleware + chunked copy helper).

Starlette parses (and spools to disk) the whole multipart body before a route runs, so a
check inside the route is too late for huge or length-less uploads. This middleware rejects
an oversized Content-Length up front and counts the bytes actually received, cutting the
request off with 413 once the cap is passed.
"""

import json
from typing import BinaryIO

from ..errors import PayloadTooLargeError

MULTIPART_OVERHEAD = 1024 * 1024  # boundaries + part headers around the file
COPY_CHUNK = 1024 * 1024


def too_large_body(max_bytes: int) -> bytes:
    message = f"File is too large. The limit is {max_bytes // (1024 * 1024)} MB."
    return json.dumps({"error": {"code": PayloadTooLargeError.code, "message": message}}).encode()


class BodySizeLimitMiddleware:
    def __init__(self, app, paths: frozenset[str], max_file_bytes: int):
        self.app = app
        self.paths = paths
        self.max_file_bytes = max_file_bytes
        self.max_body = max_file_bytes + MULTIPART_OVERHEAD

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] not in self.paths:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_body:
            await self._send_413(send)
            return

        received = 0
        exceeded = False
        started = False

        async def limited_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body:
                    exceeded = True
                    # Stop feeding the parser; whatever the app answers is replaced below.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            nonlocal started
            if exceeded:
                return  # swallow the app's response to the truncated body
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not started:
            await self._send_413(send)

    async def _send_413(self, send) -> None:
        body = too_large_body(self.max_file_bytes)
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def copy_capped(src: BinaryIO, dest_path: str, max_bytes: int) -> int:
    """Copy in chunks, failing as soon as `max_bytes` is exceeded. Returns bytes written."""
    written = 0
    with open(dest_path, "wb") as out:
        while chunk := src.read(COPY_CHUNK):
            written += len(chunk)
            if written > max_bytes:
                raise PayloadTooLargeError(
                    f"File is too large. The limit is {max_bytes // (1024 * 1024)} MB."
                )
            out.write(chunk)
    return written
