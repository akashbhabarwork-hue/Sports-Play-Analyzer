import pytest

from app.core.url_rules import canonicalize_youtube_url
from app.errors import UrlNotAllowedError

ID = "dQw4w9WgXcQ"
CANONICAL = f"https://www.youtube.com/watch?v={ID}"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={ID}",
        f"https://youtube.com/watch?v={ID}",
        f"https://m.youtube.com/watch?v={ID}",
        f"https://www.youtube.com/watch?v={ID}&t=42s&si=abc",
        f"https://www.youtube.com/watch?feature=share&v={ID}",
        f"https://www.youtube.com/watch?v={ID}&v={ID}",  # duplicate but identical
        f"https://www.youtube.com/watch?v={ID}#comments",
        f"https://youtu.be/{ID}",
        f"https://youtu.be/{ID}?si=xyz",
        f"https://www.youtube.com/shorts/{ID}",
        f"https://www.youtube.com/embed/{ID}",
        f"https://www.youtube.com/live/{ID}",
        f"https://WWW.YouTube.COM/watch?v={ID}",  # host case
        f"HTTPS://www.youtube.com/watch?v={ID}",  # scheme case
        f"https://www.youtube.com./watch?v={ID}",  # trailing dot
        f"https://www.youtube.com:443/watch?v={ID}",  # explicit default port
        "https://www.youtube.com/watch?v=a-B_c1D2e3F",  # - and _ are valid id chars
    ],
)
def test_url_rules_accept_youtube_video_links(url):
    ref = canonicalize_youtube_url(url)
    assert ref.url == f"https://www.youtube.com/watch?v={ref.video_id}"
    if "a-B_c1D2e3F" not in url:
        assert (ref.video_id, ref.url) == (ID, CANONICAL)


@pytest.mark.parametrize(
    "url",
    [
        # scheme
        f"http://www.youtube.com/watch?v={ID}",
        f"ftp://www.youtube.com/watch?v={ID}",
        "javascript:alert(1)",
        "file:///etc/passwd",
        f"//www.youtube.com/watch?v={ID}",
        f"www.youtube.com/watch?v={ID}",
        # host tricks
        f"https://youtube.com.evil.io/watch?v={ID}",
        f"https://evil.io/youtube.com/watch?v={ID}",
        f"https://evil.io/?u=https://youtu.be/{ID}",
        f"https://notyoutube.com/watch?v={ID}",
        f"https://www.youtube.co/watch?v={ID}",
        f"https://music.youtube.com/watch?v={ID}",
        f"https://xn--yutube-wqf.com/watch?v={ID}",  # punycode look-alike
        f"https://www.youtube%2ecom/watch?v={ID}",
        # userinfo / backslash parser differentials
        f"https://user:pass@www.youtube.com/watch?v={ID}",
        f"https://www.youtube.com@evil.io/watch?v={ID}",
        f"https://evil.io\\@www.youtube.com/watch?v={ID}",
        f"https://www.youtube.com\\.evil.io/watch?v={ID}",
        # ports
        f"https://www.youtube.com:8080/watch?v={ID}",
        f"https://www.youtube.com:0/watch?v={ID}",
        f"https://www.youtube.com:99999/watch?v={ID}",
        f"https://www.youtube.com:abc/watch?v={ID}",
        # IP hosts
        f"https://127.0.0.1/watch?v={ID}",
        f"https://169.254.169.254/latest/meta-data/?v={ID}",
        f"https://[::1]/watch?v={ID}",
        f"https://0x7f000001/watch?v={ID}",
        f"https://2130706433/watch?v={ID}",
        # not a single video
        "https://www.youtube.com/playlist?list=PL1234567890",
        "https://www.youtube.com/watch?list=PL1234567890",
        "https://www.youtube.com/@somechannel",
        "https://www.youtube.com/channel/UC1234567890",
        "https://www.youtube.com/",
        f"https://www.youtube.com/watch?v={ID}&v=aaaaaaaaaaa",  # conflicting ids
        f"https://youtu.be/{ID}/extra",
        f"https://www.youtube.com/shorts/{ID}/x",
        # malformed ids
        "https://www.youtube.com/watch?v=short",
        "https://www.youtube.com/watch?v=waytoolongvideoid",
        "https://www.youtube.com/watch?v=bad%20chars!",
        "https://youtu.be/",
        # whitespace / control / length
        f" https://www.youtube.com/watch?v={ID}",
        f"https://www.youtube.com/watch?v={ID}\n",
        f"https://www.you tube.com/watch?v={ID}",
        f"https://www.youtube.com/watch?v={ID}\x00",
        f"https://www.youtube.com/watch?v={ID}&pad=" + "a" * 2100,
        "",
    ],
)
def test_url_rules_reject_everything_else(url):
    with pytest.raises(UrlNotAllowedError) as exc:
        canonicalize_youtube_url(url)
    assert exc.value.code == "URL_NOT_ALLOWED"
    assert "youtube" in str(exc.value).lower()
