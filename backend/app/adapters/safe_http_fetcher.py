"""SSRF-guarded media download: manual redirects, per-hop host + IP validation, byte cap.

Every hop must be https on an allowed media host whose DNS answers are ALL public. Redirects
are never followed automatically, so a 302 to http://169.254.169.254/ (or to an allowed name
that resolves privately) is refused before any request is sent there.

Residual risk (ADR): DNS could change between our lookup and the connection (rebinding).
The allowed domains are Google-controlled, so an attacker cannot change their records; the
full fix would be connecting to the vetted IP with SNI pinning.
"""

import logging
import socket
import time
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

import httpx2

from ..core.net_rules import is_allowed_media_host, is_public_ip
from ..errors import DownloadFailedError

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
CHUNK_SIZE = 256 * 1024
TOTAL_DEADLINE_S = 120
BLOCKED_MESSAGE = "The video download was redirected to a disallowed address."
FAILED_MESSAGE = "We couldn't download this video. Try again later or upload the file instead."

Resolver = Callable[[str], list[str]]


def resolve_host(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def check_hop(url: str, resolver: Resolver) -> None:
    """Raise unless `url` is https on an allowed host that resolves only to public IPs."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise DownloadFailedError(BLOCKED_MESSAGE) from None
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or parts.username is not None
        or "@" in parts.netloc
        or port not in (None, 443)
        or not is_allowed_media_host(host)
    ):
        logger.warning("download hop refused", extra={"reason": "url", "host": host})
        raise DownloadFailedError(BLOCKED_MESSAGE)
    try:
        addresses = resolver(host)
    except OSError as e:
        raise DownloadFailedError(FAILED_MESSAGE) from e
    if not addresses or not all(is_public_ip(a) for a in addresses):
        logger.warning("download hop refused", extra={"reason": "non-public ip", "host": host})
        raise DownloadFailedError(BLOCKED_MESSAGE)


class SafeHttpDownloader:
    def __init__(
        self,
        resolver: Resolver = resolve_host,
        transport: httpx2.BaseTransport | None = None,
        proxy: str = "",
        clock: Callable[[], float] = time.monotonic,
    ):
        self.resolver = resolver
        self.clock = clock
        # trust_env=False: no ambient HTTP(S)_PROXY or netrc; a proxy is only ever explicit.
        self.client = httpx2.Client(
            follow_redirects=False,
            timeout=httpx2.Timeout(10.0, read=30.0),
            transport=transport,
            proxy=proxy or None,
            trust_env=False,
        )

    def download(self, url: str, headers: dict[str, str], dest_path: str, max_bytes: int) -> int:
        deadline = self.clock() + TOTAL_DEADLINE_S
        for _ in range(MAX_REDIRECTS + 1):
            check_hop(url, self.resolver)
            try:
                with self.client.stream("GET", url, headers=headers) as response:
                    if response.status_code in REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise DownloadFailedError(FAILED_MESSAGE)
                        url = urljoin(url, location)
                        continue
                    if response.status_code != 200:
                        logger.warning("download failed", extra={"status": response.status_code})
                        raise DownloadFailedError(FAILED_MESSAGE)
                    return self._save(response, dest_path, max_bytes, deadline)
            except httpx2.HTTPError as e:
                logger.warning("download error", extra={"error_type": type(e).__name__})
                raise DownloadFailedError(FAILED_MESSAGE) from e
        raise DownloadFailedError("Too many redirects while downloading the video.")

    def _save(self, response, dest_path: str, max_bytes: int, deadline: float) -> int:
        written = 0
        with open(dest_path, "wb") as out:
            for chunk in response.iter_bytes(CHUNK_SIZE):
                written += len(chunk)
                if written > max_bytes:
                    raise DownloadFailedError(
                        f"The video is larger than {max_bytes // (1024 * 1024)} MB."
                    )
                if self.clock() > deadline:
                    raise DownloadFailedError("The video download took too long.")
                out.write(chunk)
        return written
