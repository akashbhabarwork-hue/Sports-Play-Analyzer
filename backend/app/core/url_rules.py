"""Syntactic SSRF defence for submitted video links (pure, no network).

Only YouTube video links are accepted. The video id is extracted and a canonical URL is
rebuilt from it; the user's raw string is never stored or passed to yt-dlp. Network-level
checks (DNS → public IPs only, redirect re-validation, byte/duration caps) happen at fetch
time in the worker (T-043).
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from ..errors import UrlNotAllowedError

MAX_URL_LENGTH = 2048
ALLOWED_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
PATH_ID_PREFIXES = ("shorts", "embed", "live")
NOT_ALLOWED_MESSAGE = (
    "Only YouTube video links are supported "
    "(youtube.com/watch?v=…, youtu.be/…, youtube.com/shorts/…)."
)


@dataclass(frozen=True, slots=True)
class YouTubeRef:
    video_id: str
    url: str  # canonical https://www.youtube.com/watch?v=<id>


def _reject() -> UrlNotAllowedError:
    return UrlNotAllowedError(NOT_ALLOWED_MESSAGE)


def canonicalize_youtube_url(raw: str) -> YouTubeRef:
    if not isinstance(raw, str) or not raw or len(raw) > MAX_URL_LENGTH:
        raise _reject()
    # No whitespace, control characters or backslashes anywhere: parsers disagree on them.
    if any(c.isspace() or ord(c) < 0x20 or ord(c) == 0x7F or c == "\\" for c in raw):
        raise _reject()

    try:
        parts = urlsplit(raw)
        port = parts.port  # raises ValueError for non-numeric / out-of-range ports
    except ValueError:
        raise _reject() from None
    if parts.scheme.lower() != "https":
        raise _reject()
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise _reject()
    if port not in (None, 443):
        raise _reject()

    host = (parts.hostname or "").rstrip(".")
    # hostname is already lower-cased; exact match rules out IPs, look-alike suffixes,
    # punycode homoglyphs, percent-encoding and other subdomains.
    if host not in ALLOWED_HOSTS:
        raise _reject()

    video_id = _extract_id(host, parts.path, parts.query)
    if video_id is None or not VIDEO_ID.fullmatch(video_id):
        raise _reject()
    return YouTubeRef(video_id, f"https://www.youtube.com/watch?v={video_id}")


def _extract_id(host: str, path: str, query: str) -> str | None:
    segments = [s for s in path.split("/") if s]
    if host == "youtu.be":
        return segments[0] if len(segments) == 1 else None
    if segments == ["watch"]:
        values = set(parse_qs(query, keep_blank_values=True).get("v", []))
        return values.pop() if len(values) == 1 else None  # missing or conflicting → None
    if len(segments) == 2 and segments[0] in PATH_ID_PREFIXES:
        return segments[1]
    return None
