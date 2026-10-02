"""Manual check for T-043: fetch one real YouTube video through the production code path.

Edit the variables below, then from backend/:  python scripts/fetch_check.py
Runs yt-dlp metadata → SSRF-guarded download → ffprobe + limits, with no database.
Optional YouTube mitigations are read from the environment like in production:
YTDLP_COOKIES_B64 and YTDLP_PROXY (never printed).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.ffprobe import FfprobeVideoProber  # noqa: E402
from app.adapters.safe_http_fetcher import SafeHttpDownloader  # noqa: E402
from app.adapters.ytdlp_fetcher import YtDlpMetadataFetcher  # noqa: E402
from app.config import YTDLP_COOKIES_B64, YTDLP_PROXY  # noqa: E402
from app.core.url_rules import canonicalize_youtube_url  # noqa: E402
from app.core.video_rules import check_remote_media  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.services.submit import validate_video_file  # noqa: E402

# ---- inputs -------------------------------------------------------------------------
URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo", 19 s
OUTPUT_PATH = "fetch_check_out.mp4"
MAX_DURATION_S = 60
MAX_BYTES = 100 * 1024 * 1024
# --------------------------------------------------------------------------------------


def main() -> int:
    try:
        ref = canonicalize_youtube_url(URL)
        print(f"canonical url : {ref.url}")
        info = YtDlpMetadataFetcher(cookies_b64=YTDLP_COOKIES_B64, proxy=YTDLP_PROXY).fetch_info(
            ref.url
        )
        print(f"metadata      : {info.title!r}, {info.duration_s} s, live={info.is_live}")
        media_url = check_remote_media(info, MAX_DURATION_S)
        size = SafeHttpDownloader(proxy=YTDLP_PROXY).download(
            media_url, info.http_headers, OUTPUT_PATH, MAX_BYTES
        )
        container, probe = validate_video_file(OUTPUT_PATH, FfprobeVideoProber(), MAX_DURATION_S)
        print(f"downloaded    : {size} bytes → {OUTPUT_PATH}")
        print(
            f"ffprobe       : {container.name}, {probe.duration_s:.1f} s, "
            f"{probe.width}x{probe.height}, {probe.fps or 0:.1f} fps"
        )
        print("RESULT        : OK")
        return 0
    except AppError as e:
        print(f"RESULT        : {e.code} — {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
