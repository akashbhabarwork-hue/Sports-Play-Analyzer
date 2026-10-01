"""Map yt-dlp failures to user-facing errors (pure)."""

from ..errors import DownloadFailedError, YouTubeBlockedError

BLOCKED_MESSAGE = (
    "YouTube blocked our server from downloading this video. "
    "Please download the clip and upload it instead."
)
UNAVAILABLE_MESSAGE = "This video is private, removed or unavailable."
GENERIC_MESSAGE = "We couldn't download this video. Try again later or upload the file instead."

# Checked in order; the first match wins. Lower-cased substrings of yt-dlp's stderr.
BLOCKED_MARKERS = (
    "confirm you’re not a bot",
    "confirm you're not a bot",
    "sign in to confirm",
    "http error 403",
    "http error 429",
    "too many requests",
    "age-restricted",
    "inappropriate for some users",
    "sign in to view",
)
UNAVAILABLE_MARKERS = (
    "private video",
    "video unavailable",
    "has been removed",
    "this video is not available",
    "does not exist",
    "account associated with this video has been terminated",
)


def classify_ytdlp_failure(stderr: str) -> DownloadFailedError | YouTubeBlockedError:
    text = stderr.lower()
    if any(marker in text for marker in BLOCKED_MARKERS):
        return YouTubeBlockedError(BLOCKED_MESSAGE)
    if any(marker in text for marker in UNAVAILABLE_MARKERS):
        return DownloadFailedError(UNAVAILABLE_MESSAGE)
    return DownloadFailedError(GENERIC_MESSAGE)
