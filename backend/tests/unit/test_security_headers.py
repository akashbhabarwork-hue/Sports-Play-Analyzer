"""T-091 pure header building: CSP media origins, HSTS only in production, no-store paths."""

from app.core.security_headers import (
    content_security_policy,
    media_origins,
    needs_no_store,
    origin_of,
    security_headers,
)


def test_origin_of_keeps_scheme_host_port_and_drops_path():
    assert origin_of("https://ACC.r2.cloudflarestorage.com/bucket/x") == (
        "https://acc.r2.cloudflarestorage.com"
    )
    assert origin_of("http://localhost:9000") == "http://localhost:9000"
    assert origin_of("ftp://x") is None and origin_of("not a url") is None


def test_media_origins_allow_path_and_virtual_hosted_s3_urls_plus_extras():
    got = media_origins(
        "https://acc.r2.cloudflarestorage.com",
        "clips",
        ("https://cdn.example.com/", "https://acc.r2.cloudflarestorage.com"),
    )
    assert got == (
        "https://acc.r2.cloudflarestorage.com",
        "https://clips.acc.r2.cloudflarestorage.com",
        "https://cdn.example.com",
    )


def test_media_origins_empty_for_local_disk_storage():
    assert media_origins("", "", ()) == ()


def test_csp_is_self_only_except_fonts_and_media_hosts():
    csp = content_security_policy(("https://media.example",))
    assert "default-src 'self'" in csp and "script-src 'self'" in csp
    assert "style-src 'self' https://fonts.googleapis.com" in csp
    assert "font-src https://fonts.gstatic.com" in csp
    assert "media-src 'self' blob: https://media.example" in csp
    assert "img-src 'self' data: blob: https://media.example" in csp
    assert "frame-ancestors 'none'" in csp and "object-src 'none'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp


def test_hsts_header_only_in_production():
    assert "Strict-Transport-Security" not in security_headers(False, ())
    assert security_headers(True, ())["Strict-Transport-Security"].startswith("max-age=31536000")


def test_basic_headers_always_present():
    h = security_headers(False, ())
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in h["Permissions-Policy"]


def test_no_store_on_api_auth_and_job_alias_paths_only():
    for path in ("/api/me", "/auth/login", "/jobs/123", "/jobs", "/api"):
        assert needs_no_store(path), path
    for path in ("/", "/app/videos", "/assets/index.js", "/health", "/jobsite"):
        assert not needs_no_store(path), path
