"""CSRF defence for cookie-authenticated requests, on top of SameSite=Lax (pure, no I/O).

An unsafe request is trusted only if it carries our custom header (which a cross-site HTML
form cannot send, and which forces a CORS preflight for scripts) AND its Origin (or, when
a browser omits Origin, the Referer's origin) is one of ours. Neither present → rejected.
"""

from urllib.parse import urlsplit

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
REQUIRED_HEADER_VALUE = "fetch"


def normalize_origin(value: str | None) -> str | None:
    """scheme://host[:port] in lower case, or None if `value` is not an absolute URL."""
    if not value or value == "null":
        return None
    parts = urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def is_request_trusted(
    method: str,
    origin: str | None,
    referer: str | None,
    x_requested_with: str | None,
    trusted_origins: frozenset[str],
) -> bool:
    if method.upper() in SAFE_METHODS:
        return True
    if (x_requested_with or "").lower() != REQUIRED_HEADER_VALUE:
        return False
    source = normalize_origin(origin) or normalize_origin(referer)
    return source is not None and source in trusted_origins
