import base64
import json
import os
import stat
import subprocess

import pytest

from app.adapters.ytdlp_fetcher import YtDlpMetadataFetcher, build_ytdlp_command
from app.errors import DownloadFailedError, ExternalServiceError, YouTubeBlockedError

URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
INFO = {
    "duration": 19,
    "is_live": False,
    "url": "https://rr1---sn-abc.googlevideo.com/videoplayback?id=1",
    "http_headers": {"User-Agent": "UA", "Accept": "*/*", "Cookie": "SID=secret"},
    "title": "Me at the zoo",
}


class FakeRunner:
    def __init__(self, returncode=0, stdout="", stderr="", raise_timeout=False):
        self.result = subprocess.CompletedProcess([], returncode, stdout, stderr)
        self.raise_timeout = raise_timeout
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if self.raise_timeout:
            raise subprocess.TimeoutExpired(cmd, 45)
        cookie = cmd[cmd.index("--cookies") + 1] if "--cookies" in cmd else None
        if cookie:
            self.cookie_mode = stat.S_IMODE(os.stat(cookie).st_mode)
            self.cookie_text = open(cookie).read()
        return self.result


def test_fetch_ytdlp_command_is_an_argument_list_with_url_last():
    cmd = build_ytdlp_command("yt-dlp", URL)
    assert cmd[:5] == ["yt-dlp", "--dump-single-json", "--no-playlist", "--no-warnings",
                       "--use-extractors"]  # fmt: skip
    assert cmd[5] == "youtube"
    assert cmd[-2:] == ["--", URL]
    assert "--cookies" not in cmd and "--proxy" not in cmd


def test_fetch_ytdlp_runs_without_shell_and_parses_info():
    runner = FakeRunner(stdout=json.dumps(INFO))
    info = YtDlpMetadataFetcher(runner=runner).fetch_info(URL)

    ((cmd, kwargs),) = runner.calls
    assert kwargs["shell"] is False and kwargs["timeout"] == 45
    assert (info.duration_s, info.is_live, info.media_url) == (19.0, False, INFO["url"])
    assert info.http_headers == {"User-Agent": "UA", "Accept": "*/*"}  # Cookie never forwarded


def test_fetch_ytdlp_cookies_file_is_private_and_deleted():
    runner = FakeRunner(stdout=json.dumps(INFO))
    cookies = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tabc\n"
    fetcher = YtDlpMetadataFetcher(
        cookies_b64=base64.b64encode(cookies.encode()).decode(),
        proxy="http://proxy:3128",
        runner=runner,
    )

    fetcher.fetch_info(URL)

    ((cmd, _),) = runner.calls
    path = cmd[cmd.index("--cookies") + 1]
    assert runner.cookie_mode == 0o600 and runner.cookie_text == cookies
    assert not os.path.exists(path)  # removed after the call
    assert cmd[cmd.index("--proxy") + 1] == "http://proxy:3128"
    assert cmd[-2:] == ["--", URL]


def test_fetch_ytdlp_cookie_file_removed_even_on_failure():
    runner = FakeRunner(returncode=1, stderr="ERROR: Sign in to confirm you're not a bot")
    fetcher = YtDlpMetadataFetcher(cookies_b64=base64.b64encode(b"x").decode(), runner=runner)
    with pytest.raises(YouTubeBlockedError):
        fetcher.fetch_info(URL)
    ((cmd, _),) = runner.calls
    assert not os.path.exists(cmd[cmd.index("--cookies") + 1])


def test_fetch_ytdlp_bad_cookies_config():
    with pytest.raises(ExternalServiceError):
        YtDlpMetadataFetcher(cookies_b64="not base64!!", runner=FakeRunner()).fetch_info(URL)


def test_fetch_ytdlp_timeout_and_garbage_output():
    with pytest.raises(DownloadFailedError):
        YtDlpMetadataFetcher(runner=FakeRunner(raise_timeout=True)).fetch_info(URL)
    with pytest.raises(DownloadFailedError):
        YtDlpMetadataFetcher(runner=FakeRunner(stdout="not json")).fetch_info(URL)


def test_fetch_ytdlp_live_and_unmerged_formats_parse_safely():
    live = YtDlpMetadataFetcher(
        runner=FakeRunner(stdout=json.dumps({"live_status": "is_live", "duration": None}))
    ).fetch_info(URL)
    assert live.is_live and live.duration_s is None and live.media_url is None
