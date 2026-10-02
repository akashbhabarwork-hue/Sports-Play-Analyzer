import pytest

from app.entrypoints.csrf import is_request_trusted, normalize_origin

TRUSTED = frozenset({"https://app.example", "http://localhost:5173"})


@pytest.mark.parametrize(
    ("method", "origin", "referer", "xrw", "expected"),
    [
        ("GET", None, None, None, True),  # safe methods are never blocked
        ("HEAD", "https://evil.example", None, None, True),
        ("POST", "https://app.example", None, "fetch", True),
        ("DELETE", "https://APP.example", None, "Fetch", True),  # case-insensitive
        ("POST", "http://localhost:5173", None, "fetch", True),  # trusted dev origin
        ("POST", "https://evil.example", None, "fetch", False),  # foreign origin
        ("POST", "https://app.example", None, None, False),  # header missing
        ("POST", "https://app.example", None, "XMLHttpRequest", False),  # wrong header value
        ("POST", None, "https://app.example/jobs/1", "fetch", True),  # Referer fallback
        ("POST", None, "https://evil.example/x", "fetch", False),
        ("POST", None, None, "fetch", False),  # neither Origin nor Referer
        ("POST", "null", None, "fetch", False),  # sandboxed/opaque origin
        ("PUT", "https://app.example.evil.com", None, "fetch", False),  # suffix trick
        ("PATCH", "http://app.example", None, "fetch", False),  # scheme matters
    ],
)
def test_csrf_decision(method, origin, referer, xrw, expected):
    assert is_request_trusted(method, origin, referer, xrw, TRUSTED) is expected


def test_normalize_origin():
    assert normalize_origin("https://App.Example:8443/path?q=1") == "https://app.example:8443"
    assert normalize_origin("javascript:alert(1)") is None
    assert normalize_origin("") is None
