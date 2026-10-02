import pytest

from app.core.ytdlp_errors import classify_ytdlp_failure

# Real stderr captured by the T-014 spike on a GitHub runner.
SPIKE_STDERR = (
    "WARNING: [youtube] No title found in player responses; falling back to title from "
    "initial data. Other metadata may also be missing\n"
    "ERROR: [youtube] jNQXAC9IVRw: Sign in to confirm you’re not a bot. Use "
    "--cookies-from-browser or --cookies for the authentication."
)


@pytest.mark.parametrize(
    ("stderr", "code"),
    [
        (SPIKE_STDERR, "YOUTUBE_BLOCKED"),
        ("ERROR: Sign in to confirm you're not a bot", "YOUTUBE_BLOCKED"),  # ASCII quote
        ("ERROR: unable to download video data: HTTP Error 403: Forbidden", "YOUTUBE_BLOCKED"),
        ("ERROR: HTTP Error 429: Too Many Requests", "YOUTUBE_BLOCKED"),
        ("ERROR: [youtube] x: Sign in to confirm your age. This video may be inappropriate "
         "for some users.", "YOUTUBE_BLOCKED"),
        ("ERROR: [youtube] x: Private video. Sign in if you've been granted access",
         "DOWNLOAD_FAILED"),  # the video itself is private, not our server being blocked
        ("ERROR: [youtube] x: Video unavailable", "DOWNLOAD_FAILED"),
        ("ERROR: [youtube] x: This video has been removed by the uploader", "DOWNLOAD_FAILED"),
        ("ERROR: Unable to extract initial player response; please report this issue",
         "DOWNLOAD_FAILED"),
        ("", "DOWNLOAD_FAILED"),
    ],
)  # fmt: skip
def test_classifier_maps_ytdlp_stderr(stderr, code):
    error = classify_ytdlp_failure(stderr)
    assert error.code == code
    assert "upload" in str(error).lower() or "unavailable" in str(error).lower()


def test_classifier_blocked_message_suggests_upload():
    assert "upload it instead" in str(classify_ytdlp_failure(SPIKE_STDERR))
