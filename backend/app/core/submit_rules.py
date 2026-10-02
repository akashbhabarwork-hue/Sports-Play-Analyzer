"""What a submission may carry besides the video: its sport and an optional title (T-085)."""

import re

from ..errors import InvalidSportError, ValidationError

SPORTS = ("football", "basketball")  # mirrors the videos.sport CHECK constraint
DEFAULT_SPORT = "football"  # curl users and old clients that send no sport
MAX_TITLE_LENGTH = 120  # mirrors the videos.title CHECK constraint

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SPACES = re.compile(r"\s+")


def clean_title(raw: str | None) -> str | None:
    """Trim, drop control characters, collapse whitespace; empty → None (UI shows the filename)."""
    if raw is None:
        return None
    title = _SPACES.sub(" ", _CONTROL.sub(" ", raw)).strip()
    if not title:
        return None
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"Title is too long (max {MAX_TITLE_LENGTH} characters).")
    return title


def check_sport(raw: str | None) -> str:
    sport = (raw or "").strip().lower() or DEFAULT_SPORT
    if sport not in SPORTS:
        raise InvalidSportError("Sport must be football or basketball.")
    return sport
