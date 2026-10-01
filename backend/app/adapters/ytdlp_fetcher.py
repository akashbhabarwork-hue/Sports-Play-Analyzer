"""yt-dlp metadata adapter. Never downloads: our SSRF-guarded downloader fetches the bytes.

Flags verified against yt-dlp 2026.08.19 (`yt-dlp --help`, `--list-extractors`).
"""

import base64
import binascii
import json
import logging
import os
import subprocess
import tempfile
from collections.abc import Callable
from typing import Any

from ..core.models import MediaInfo
from ..core.ytdlp_errors import GENERIC_MESSAGE, classify_ytdlp_failure
from ..errors import DownloadFailedError, ExternalServiceError

logger = logging.getLogger(__name__)

TIMEOUT_S = 45
# Video-only (audio is not analysed) single streams ≤720p: one URL, nothing to merge.
FORMAT = "bv*[height<=720][ext=mp4]/bv*[height<=720]/b[height<=720]"
FORWARDED_HEADERS = ("user-agent", "accept", "accept-language")


def build_ytdlp_command(
    binary: str, url: str, cookies_path: str | None = None, proxy: str | None = None
) -> list[str]:
    cmd = [
        binary,
        "--dump-single-json", "--no-playlist", "--no-warnings",
        "--use-extractors", "youtube",  # never the generic extractor: no arbitrary URLs
        "-f", FORMAT,
    ]  # fmt: skip
    if cookies_path:
        cmd += ["--cookies", cookies_path]
    if proxy:
        cmd += ["--proxy", proxy]
    return [*cmd, "--", url]  # `--`: the URL can never be read as an option


def parse_media_info(info: dict[str, Any]) -> MediaInfo:
    headers = {
        k: v
        for k, v in (info.get("http_headers") or {}).items()
        if isinstance(v, str) and k.lower() in FORWARDED_HEADERS
    }
    duration = info.get("duration")
    return MediaInfo(
        duration_s=float(duration) if isinstance(duration, int | float) else None,
        is_live=bool(info.get("is_live")) or info.get("live_status") in ("is_live", "is_upcoming"),
        media_url=info.get("url") if isinstance(info.get("url"), str) else None,
        http_headers=headers,
        title=info.get("title"),
    )


class YtDlpMetadataFetcher:
    def __init__(
        self,
        binary: str = "yt-dlp",
        cookies_b64: str = "",
        proxy: str = "",
        runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    ):
        self.binary = binary
        self.cookies_b64 = cookies_b64
        self.proxy = proxy
        self.runner = runner

    def fetch_info(self, url: str) -> MediaInfo:
        cookies_path = self._write_cookies() if self.cookies_b64 else None
        try:
            cmd = build_ytdlp_command(self.binary, url, cookies_path, self.proxy or None)
            try:
                result = self.runner(
                    cmd, capture_output=True, text=True, timeout=TIMEOUT_S, shell=False, check=False
                )
            except subprocess.TimeoutExpired as e:
                logger.warning("yt-dlp timed out")
                raise DownloadFailedError(GENERIC_MESSAGE) from e
        finally:
            if cookies_path:
                os.unlink(cookies_path)

        if result.returncode != 0:
            error = classify_ytdlp_failure(result.stderr or "")
            # Log the classification only: stderr can echo proxy or request details.
            logger.warning("yt-dlp failed", extra={"error_code": error.code})
            raise error
        try:
            return parse_media_info(json.loads(result.stdout))
        except (ValueError, TypeError, AttributeError) as e:
            raise DownloadFailedError(GENERIC_MESSAGE) from e

    def _write_cookies(self) -> str:
        try:
            data = base64.b64decode(self.cookies_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ExternalServiceError("YouTube cookies are misconfigured") from e
        fd, path = tempfile.mkstemp(prefix="ytc-", suffix=".txt")  # created with mode 0600
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return path
