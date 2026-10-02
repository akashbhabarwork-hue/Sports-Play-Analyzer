"""Security response headers, built once from settings (T-091, D-033). Pure: no I/O."""

from urllib.parse import urlsplit

HSTS = "max-age=31536000; includeSubDomains"
# Google Fonts: the stylesheet comes from fonts.googleapis.com, the font files from gstatic.
FONT_STYLES = "https://fonts.googleapis.com"
FONT_FILES = "https://fonts.gstatic.com"


def origin_of(url: str) -> str | None:
    """`scheme://host[:port]` of an http(s) URL, lowercased; None if it isn't one."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname.lower()}{port}"


def media_origins(s3_endpoint_url: str, s3_bucket: str, extra: tuple[str, ...]) -> tuple[str, ...]:
    """Where presigned 302s for video/thumbnails can point (S3 backend only).

    boto3 may sign path-style (`endpoint/bucket/key`) or virtual-hosted (`bucket.endpoint/key`)
    URLs, so both are allowed; `extra` (CSP_MEDIA_ORIGINS) covers anything else, e.g. a CDN.
    """
    found: list[str] = []
    base = origin_of(s3_endpoint_url) if s3_endpoint_url else None
    if base:
        found.append(base)
        if s3_bucket:
            scheme, host = base.split("://", 1)
            found.append(f"{scheme}://{s3_bucket.lower()}.{host}")
    found.extend(o for o in map(origin_of, extra) if o)
    return tuple(dict.fromkeys(found))  # de-duplicated, order kept


def content_security_policy(media: tuple[str, ...]) -> str:
    extra = "".join(f" {o}" for o in media)
    directives = (
        "default-src 'self'",
        "script-src 'self'",
        f"style-src 'self' {FONT_STYLES}",
        f"font-src {FONT_FILES}",
        f"img-src 'self' data: blob:{extra}",
        f"media-src 'self' blob:{extra}",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    )
    return "; ".join(directives)


def security_headers(production: bool, media: tuple[str, ...]) -> dict[str, str]:
    """Headers added to every response. HSTS only in production: it pins the browser to
    HTTPS for a year, which would break plain-http localhost."""
    headers = {
        "Content-Security-Policy": content_security_policy(media),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
    if production:
        headers["Strict-Transport-Security"] = HSTS
    return headers


def needs_no_store(path: str) -> bool:
    """API (incl. the /jobs aliases, D-004) and auth responses carry user data or login
    state: never cache them unless the route chose its own Cache-Control."""
    return path.startswith(("/api/", "/auth/", "/jobs/")) or path in ("/api", "/auth", "/jobs")
