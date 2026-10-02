import httpx2
import pytest

from app.adapters.safe_http_fetcher import SafeHttpDownloader
from app.errors import DownloadFailedError

MEDIA = "https://rr1---sn-abc.googlevideo.com/videoplayback?id=1"
PUBLIC = {"rr1---sn-abc.googlevideo.com": ["142.250.72.14"],
          "rr2---sn-abc.googlevideo.com": ["142.250.72.15"],
          "evil.googlevideo.com": ["10.0.0.1"],
          "mixed.googlevideo.com": ["142.250.72.16", "127.0.0.1"]}  # fmt: skip


def resolver(table=PUBLIC):
    def resolve(host):
        if host not in table:
            raise OSError("no such host")
        return table[host]

    return resolve


def downloader(handler, **kw):
    calls = []

    def recording(request):
        calls.append(str(request.url))
        return handler(request)

    return SafeHttpDownloader(resolver(), httpx2.MockTransport(recording), **kw), calls


def redirect_to(location):
    return lambda request: httpx2.Response(302, headers={"location": location})


def test_fetch_downloads_allowed_public_media(tmp_path):
    dl, calls = downloader(lambda r: httpx2.Response(200, content=b"x" * 1000))

    size = dl.download(MEDIA, {"user-agent": "ua"}, str(tmp_path / "f"), 10_000)

    assert size == 1000 and (tmp_path / "f").read_bytes() == b"x" * 1000
    assert calls == [MEDIA]


def test_fetch_follows_redirects_within_allowlist(tmp_path):
    second = "https://rr2---sn-abc.googlevideo.com/videoplayback?id=2"

    def handler(request):
        if "rr1" in str(request.url):
            return httpx2.Response(302, headers={"location": second})
        return httpx2.Response(200, content=b"ok")

    dl, calls = downloader(handler)
    assert dl.download(MEDIA, {}, str(tmp_path / "f"), 100) == 2
    assert calls == [MEDIA, second]


@pytest.mark.parametrize(
    "location",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "https://169.254.169.254/latest/meta-data/",
        "http://rr2---sn-abc.googlevideo.com/x",  # downgrade to http
        "https://evil.googlevideo.com/x",  # allowed name, private IP
        "https://mixed.googlevideo.com/x",  # one private answer is enough
        "https://evil.io/x",  # not allowlisted
        "https://user@rr2---sn-abc.googlevideo.com/x",  # userinfo
        "https://rr2---sn-abc.googlevideo.com:8443/x",  # odd port
        "https://localhost/x",
    ],
)
def test_fetch_redirect_to_disallowed_target_is_blocked_before_request(tmp_path, location):
    dl, calls = downloader(redirect_to(location))

    with pytest.raises(DownloadFailedError, match="disallowed address"):
        dl.download(MEDIA, {}, str(tmp_path / "f"), 100)
    assert calls == [MEDIA]  # the disallowed target was never contacted


def test_fetch_initial_url_is_checked_too(tmp_path):
    dl, calls = downloader(lambda r: httpx2.Response(200))
    with pytest.raises(DownloadFailedError):
        dl.download("https://evil.googlevideo.com/x", {}, str(tmp_path / "f"), 100)
    assert calls == []


def test_fetch_too_many_redirects(tmp_path):
    dl, calls = downloader(redirect_to(MEDIA))  # loops on itself
    with pytest.raises(DownloadFailedError, match="Too many redirects"):
        dl.download(MEDIA, {}, str(tmp_path / "f"), 100)
    assert len(calls) == 6  # first request + 5 redirects


def test_fetch_byte_cap(tmp_path):
    dl, _ = downloader(lambda r: httpx2.Response(200, content=b"x" * 5000))
    with pytest.raises(DownloadFailedError, match="larger than"):
        dl.download(MEDIA, {}, str(tmp_path / "f"), 1000)


@pytest.mark.parametrize("status", [403, 404, 500])
def test_fetch_non_success_status(tmp_path, status):
    dl, _ = downloader(lambda r: httpx2.Response(status))
    with pytest.raises(DownloadFailedError):
        dl.download(MEDIA, {}, str(tmp_path / "f"), 100)


def test_fetch_dns_failure(tmp_path):
    dl, _ = downloader(lambda r: httpx2.Response(200))
    with pytest.raises(DownloadFailedError):
        dl.download("https://unknown.googlevideo.com/x", {}, str(tmp_path / "f"), 100)


def test_fetch_ignores_ambient_proxy_env(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://attacker.example:8080")
    dl = SafeHttpDownloader(resolver())
    assert dl.client._trust_env is False
